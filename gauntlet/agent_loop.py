"""Agent loop: runs a task through multi-turn tool execution with a loop watchdog.

This is the core of the "measures the model as a subagent" requirement:
- tools actually execute in the sandbox, results feed back as tool messages
- native OpenAI tool_calls AND text-embedded calls from small models are normalized
- watchdog terminates no-progress loops (repeated identical calls / outputs)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from gauntlet.client import ChatResult, GauntletClient
from gauntlet.sandbox import ToolSandbox, parse_tool_call_name


@dataclass
class LoopOutcome:
    final_text: str = ""
    turns: int = 0
    tool_calls: int = 0
    terminated: str = "completed"  # completed | max_turns | looped | error
    usage_prompt: int = 0
    usage_completion: int = 0
    call_log: list[dict] = field(default_factory=list)


class LoopWatchdog:
    """Detects no-progress loops: same tool+args repeated, or near-identical outputs."""

    def __init__(self, max_repeats: int = 3):
        self.max_repeats = max_repeats
        self._calls: dict[str, int] = {}
        self._last_texts: list[str] = []

    def check_call(self, name: str, args: dict) -> bool:
        """True if this call is part of a loop."""
        key = name + ":" + json.dumps(args, sort_keys=True)
        self._calls[key] = self._calls.get(key, 0) + 1
        return self._calls[key] >= self.max_repeats

    def check_text(self, text: str | None) -> bool:
        """True if the model keeps producing near-identical final text."""
        if not text:
            return False
        self._last_texts.append(text.strip())
        if len(self._last_texts) < self.max_repeats:
            return False
        tail = self._last_texts[-self.max_repeats :]
        return len(set(tail)) == 1


async def run_agent_loop(
    client: GauntletClient,
    sandbox: ToolSandbox,
    system: str,
    prompt: str,
    tools: list[dict],
    max_turns: int = 8,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    no_think: bool = True,
) -> LoopOutcome:
    outcome = LoopOutcome()
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    watchdog = LoopWatchdog()

    for turn in range(max_turns):
        try:
            result: ChatResult = await client.chat(
                messages, tools=tools or None, temperature=temperature, max_tokens=max_tokens, no_think=no_think
            )
        except Exception as e:  # noqa: BLE001 — record and fail the task
            outcome.terminated = "error"
            outcome.final_text = f"[client error] {e}"
            return outcome

        outcome.turns = turn + 1
        outcome.usage_prompt += result.usage.prompt_tokens
        outcome.usage_completion += result.usage.completion_tokens

        # --- native tool calls ---
        if result.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": result.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in result.tool_calls
                    ],
                }
            )
            for tc in result.tool_calls:
                outcome.tool_calls += 1
                if watchdog.check_call(tc.name, tc.arguments):
                    outcome.terminated = "looped"
                    return outcome
                resp = sandbox.execute(tc.name, tc.arguments)
                outcome.call_log.append({"tool": tc.name, "args": tc.arguments, "result": resp})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(resp)})
            continue

        # --- text-embedded tool call (common in small models without native TC) ---
        text = result.content or ""
        embedded_name = parse_tool_call_name(text) if text else None
        if embedded_name and embedded_name in {t["function"]["name"] for t in tools} and result.finish_reason != "stop":
            messages.append({"role": "assistant", "content": text})
            args = _extract_args(text)
            outcome.tool_calls += 1
            if watchdog.check_call(embedded_name, args):
                outcome.terminated = "looped"
                return outcome
            resp = sandbox.execute(embedded_name, args)
            outcome.call_log.append({"tool": embedded_name, "args": args, "result": resp})
            messages.append({
                "role": "user",
                "content": f"Tool `{embedded_name}` returned: {json.dumps(resp)}\nContinue.",
            })
            continue

        # --- final text answer ---
        if not (text and text.strip()):
            # empty final answer with no tool calls: distinct failure mode,
            # never a completed task (typically think-mode token exhaustion)
            outcome.terminated = "empty_response"
            return outcome
        if watchdog.check_text(text):
            outcome.terminated = "looped"
            outcome.final_text = text
            return outcome
        outcome.final_text = text
        outcome.terminated = "completed"
        return outcome

    outcome.terminated = "max_turns"
    return outcome


def _extract_args(text: str) -> dict:
    """Best-effort argument extraction from text-embedded calls like name(a=1, b='x')."""
    import re

    m = re.search(r"[A-Za-z_][A-Za-z0-9_]*\s*\((.*)\)", text, re.DOTALL)
    if not m:
        return {}
    body = m.group(1).strip()
    if not body:
        return {}
    # JSON object?
    try:
        obj = json.loads(body if body.startswith("{") else "{" + body + "}")
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    # python kwargs: a=1, b='x'
    args = {}
    for km in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*('(?:[^']*)'|\"(?:[^\"]*)\"|[\w.\-]+)", body):
        raw = km.group(2)
        if raw and raw[0] in "'\"":
            raw = raw[1:-1]
        else:
            try:
                raw = json.loads(raw)
            except ValueError:
                pass
        args[km.group(1)] = raw
    return args or {"_raw": body}
