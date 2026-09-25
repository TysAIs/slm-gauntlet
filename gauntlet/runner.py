"""Runner: executes task suites against an endpoint with pass^k, writes JSON results."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from gauntlet.agent_loop import run_agent_loop, LoopOutcome
from gauntlet.client import GauntletClient
from gauntlet.sandbox import ToolSandbox, tools_for
from gauntlet.scorer import Scorer
from gauntlet.task import Task


async def run_task(client: GauntletClient, task: Task, seed: int = 0) -> dict:
    """Run one task `task.repeats` times; returns per-task record with pass^k."""
    scorer = Scorer()
    attempts = []
    for rep in range(task.repeats):
        sandbox = ToolSandbox(seed=seed + rep)
        try:
            outcome: LoopOutcome = await asyncio.wait_for(
                run_agent_loop(
                    client,
                    sandbox,
                    system=task.system,
                    prompt=task.prompt,
                    tools=tools_for([t.name for t in task.tools]),
                    max_turns=task.max_turns,
                    max_tokens=task.max_tokens,
                ),
                timeout=task.timeout,
            )
        except asyncio.TimeoutError:
            outcome = LoopOutcome(terminated="timeout", final_text="[timeout]")
        score = scorer.score(outcome.final_text, task.to_assert_dicts()) if outcome.final_text else None
        if score is None:
            passed = False
            failed = [f"no final output (terminated={outcome.terminated})"]
        else:
            passed = outcome.terminated == "completed" and score.passed
            failed = score.failed if not passed else []
            if outcome.terminated != "completed":
                failed.append(f"loop_terminated:{outcome.terminated}")
        attempts.append(
            {
                "rep": rep,
                "passed": passed,
                "failed": failed,
                "terminated": outcome.terminated,
                "turns": outcome.turns,
                "tool_calls": outcome.tool_calls,
                "prompt_tokens": outcome.usage_prompt,
                "completion_tokens": outcome.usage_completion,
                "final_text": outcome.final_text[:2000],
                "call_log": outcome.call_log,
            }
        )
        sandbox.cleanup()

    passes = [a["passed"] for a in attempts]
    pass1 = sum(passes) / len(passes)
    pass_k = 1.0 if all(passes) else 0.0  # pass^k: all repeats must succeed
    return {
        "task_id": task.id,
        "suite": task.suite,
        "repeats": task.repeats,
        "pass1": pass1,
        "pass_k": pass_k,
        "attempts": attempts,
    }


async def run_suite(client: GauntletClient, tasks: list[Task], concurrency: int = 4, seed: int = 0) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)

    async def bounded(t: Task) -> dict:
        async with sem:
            return await run_task(client, t, seed=seed)

    return await asyncio.gather(*[bounded(t) for t in tasks])


def write_results(results: list[dict], meta: dict, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = outdir / f"{meta.get('model', 'model').replace('/', '_')}_{stamp}.json"
    payload = {
        "meta": {
            **meta,
            "timestamp": stamp,
            "gauntlet_version": "0.1.0",
        },
        "results": results,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path
