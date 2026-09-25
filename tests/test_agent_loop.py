"""Tests for the agent loop and runner: scripted mock models with real sandbox execution."""

import json

import httpx

from gauntlet.agent_loop import LoopWatchdog, _extract_args, run_agent_loop
from gauntlet.client import GauntletClient
from gauntlet.runner import run_task
from gauntlet.sandbox import ToolSandbox, tools_for
from gauntlet.task import Assert, Task, ToolDef


def _client_with_script(script: list[dict]) -> GauntletClient:
    """Mock endpoint that returns scripted responses in order."""
    idx = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n = idx["n"]
        idx["n"] += 1
        step = script[min(n, len(script) - 1)]
        return httpx.Response(200, json=step, request=request)

    return GauntletClient("http://test/v1", "mock", transport=httpx.MockTransport(handler))


def _completion(content=None, tool_calls=None, finish="stop"):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = [
            {
                "id": f"t{i}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
            }
            for i, tc in enumerate(tool_calls)
        ]
        finish = "tool_calls"
    usage = {"prompt_tokens": 10, "completion_tokens": 5}
    return {"choices": [{"message": msg, "finish_reason": finish}], "usage": usage}


async def test_loop_executes_tool_and_returns_final():
    script = [
        _completion(tool_calls=[{"name": "calculator", "args": {"expression": "2+3*4"}}]),
        _completion(content="The result is 14."),
    ]
    client = _client_with_script(script)
    sandbox = ToolSandbox(seed=1)
    outcome = await run_agent_loop(
        client, sandbox, "sys", "compute 2+3*4",
        tools=tools_for(["calculator"]),
    )
    assert outcome.terminated == "completed"
    assert outcome.final_text == "The result is 14."
    assert outcome.tool_calls == 1
    assert outcome.call_log[0]["result"] == {"result": 14}
    sandbox.cleanup()


async def test_error_recovery_flow():
    """Tool 500s once; model retries and succeeds — the loop just relays results."""
    script = [
        _completion(tool_calls=[{"name": "calculator", "args": {"expression": "10/2"}}]),
        _completion(tool_calls=[{"name": "calculator", "args": {"expression": "10/2"}}]),
        _completion(content="5"),
    ]
    client = _client_with_script(script)
    sandbox = ToolSandbox(seed=2)
    sandbox.fail_next("calculator", 1)
    outcome = await run_agent_loop(client, sandbox, "sys", "compute", tools=tools_for(["calculator"]))
    assert outcome.terminated == "completed"
    # first call errored, second succeeded
    assert outcome.call_log[0]["result"]["error"] == "internal_error"
    assert outcome.call_log[1]["result"] == {"result": 5}
    sandbox.cleanup()


async def test_watchdog_terminates_identical_loop():
    wd = LoopWatchdog(max_repeats=3)
    assert not wd.check_call("f", {"a": 1})
    assert not wd.check_call("f", {"a": 1})
    assert wd.check_call("f", {"a": 1})


async def test_loop_terminates_on_repeated_tool_call():
    script = [_completion(tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}}])] * 10
    client = _client_with_script(script)
    sandbox = ToolSandbox(seed=3)
    outcome = await run_agent_loop(client, sandbox, "sys", "p", tools=tools_for(["calculator"]), max_turns=8)
    assert outcome.terminated == "looped"
    sandbox.cleanup()


async def test_max_turns_termination():
    script = [_completion(tool_calls=[{"name": "get_time", "args": {}}])] * 20
    client = _client_with_script(script)
    sandbox = ToolSandbox(seed=4)
    outcome = await run_agent_loop(client, sandbox, "sys", "p", tools=tools_for(["get_time"]), max_turns=5)
    # watchdog should catch repeated identical calls before max_turns
    assert outcome.terminated in ("looped", "max_turns")
    sandbox.cleanup()


async def test_empty_final_answer_is_empty_response():
    """Model returns empty content with no tool calls -> empty_response, never completed."""
    script = [_completion(content=""), _completion(content="   ")]
    client = _client_with_script(script)
    sandbox = ToolSandbox(seed=10)
    outcome = await run_agent_loop(client, sandbox, "sys", "do something", tools=[], max_turns=4)
    assert outcome.terminated == "empty_response"
    sandbox.cleanup()


def test_extract_args_python_kwargs():
    assert _extract_args("search_flights(origin='SFO', destination='JFK', date='2026-10-01')") == {
        "origin": "SFO", "destination": "JFK", "date": "2026-10-01",
    }


def test_extract_args_json():
    assert _extract_args('calculator({"expression": "2+2"})') == {"expression": "2+2"}


async def test_runner_pass_k():
    """Task with 2 repeats where model always succeeds -> pass_k 1.0."""
    script = [
        _completion(tool_calls=[{"name": "calculator", "args": {"expression": "6*7"}}]),
        _completion(content="42"),
    ]
    client = _client_with_script(script)
    task = Task(
        id="calc_simple", suite="tooluse", description="d",
        prompt="What is 6*7? Use the calculator.",
        tools=[ToolDef(name="calculator", description="calc", parameters={})],
        asserts=[Assert(type="contains_all", values=["42"])],
        repeats=2,
    )
    record = await run_task(client, task, seed=0)
    assert record["pass1"] == 1.0
    assert record["pass_k"] == 1.0
    assert len(record["attempts"]) == 2


async def test_runner_fails_on_wrong_answer():
    script = [_completion(content="The answer is 99.")]
    client = _client_with_script(script)
    task = Task(
        id="calc_wrong", suite="tooluse", description="d",
        prompt="What is 6*7?",
        asserts=[Assert(type="contains_all", values=["42"])],
    )
    record = await run_task(client, task, seed=0)
    assert record["pass1"] == 0.0
    assert record["pass_k"] == 0.0
    assert record["attempts"][0]["failed"]
