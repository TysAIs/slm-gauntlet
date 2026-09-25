"""Tests for weighted partial credit, must-pass gates, and state-based verification."""

from gauntlet.sandbox import ToolSandbox
from gauntlet.scorer import Scorer
from gauntlet.state_check import evaluate_state_asserts
from gauntlet.task import StateAssert


def test_partial_credit_all_pass():
    r = Scorer().score("alpha beta gamma", [
        {"type": "contains_all", "values": ["alpha"], "weight": 2.0},
        {"type": "contains_all", "values": ["beta"]},
    ])
    assert r.score == 1.0
    assert r.passed


def test_partial_credit_half_earned():
    r = Scorer().score("alpha only", [
        {"type": "contains_all", "values": ["alpha"], "weight": 1.0},
        {"type": "contains_all", "values": ["beta"], "weight": 1.0},
    ])
    assert not r.passed
    assert r.score == 0.5


def test_partial_credit_weighted():
    r = Scorer().score("has core only", [
        {"type": "contains_all", "values": ["core"], "weight": 3.0},
        {"type": "contains_all", "values": ["extra"], "weight": 1.0},
    ])
    assert r.score == 0.75


def test_must_pass_failure_zeroes_score():
    r = Scorer().score("close but wrong number", [
        {"type": "contains_all", "values": ["42"], "must_pass": True},
        {"type": "contains_any", "values": ["answer", "result"]},
    ])
    assert r.score == 0.0
    assert not r.passed


def test_must_pass_passing_does_not_zero():
    r = Scorer().score("the answer is 42, obviously", [
        {"type": "contains_all", "values": ["42"], "must_pass": True},
        {"type": "contains_any", "values": ["answer", "result"]},
    ])
    assert r.score == 1.0


# ---------- state-based checks ----------

def test_state_tool_called_and_not_called():
    sandbox = ToolSandbox(seed=5)
    sandbox.execute("calculator", {"expression": "2+2"})
    sandbox.execute("get_time", {"timezone": "UTC"})
    result = evaluate_state_asserts(sandbox, [
        StateAssert(type="tool_called", tool="calculator"),
        StateAssert(type="tool_not_called", tool="search_flights"),
        StateAssert(type="tool_called", tool="search_flights"),  # fails
    ])
    assert not result["passed"]
    assert result["score"] == 2 / 3
    sandbox.cleanup()


def test_state_path_reservation():
    sandbox = ToolSandbox(seed=6)
    sandbox.execute("reserve_flight", {"flight_id": "FL1", "passenger": {"name": "Ada", "passport": "P1"}})
    result = evaluate_state_asserts(sandbox, [
        StateAssert(type="state_path", path="reservations.0.name", equals="Ada", must_pass=True),
        StateAssert(type="state_path", path="reservations.0.flight_id", equals="FL1"),
    ])
    assert result["passed"]
    assert result["score"] == 1.0
    sandbox.cleanup()


def test_state_must_pass_zeroes():
    sandbox = ToolSandbox(seed=7)
    result = evaluate_state_asserts(sandbox, [
        StateAssert(type="state_path", path="reservations.0.name", equals="Nobody", must_pass=True),
        StateAssert(type="tool_called", tool="get_time"),  # not called either
    ])
    assert result["score"] == 0.0
    sandbox.cleanup()


def test_state_empty_default_when_never_created():
    """Expecting empty container on a never-created path passes (no-op semantics)."""
    sandbox = ToolSandbox(seed=12)  # nothing ever reserved
    result = evaluate_state_asserts(sandbox, [
        StateAssert(type="state_path", path="reservations", equals=[]),
    ])
    assert result["passed"]
    sandbox.cleanup()


def test_state_file_content():
    sandbox = ToolSandbox(seed=8)
    sandbox.execute("write_file", {"path": "out.txt", "content": "GAUNTLET_OK"})
    result = evaluate_state_asserts(sandbox, [
        StateAssert(type="file_content", path="out.txt", contains="GAUNTLET_OK"),
    ])
    assert result["passed"]
    sandbox.cleanup()


def test_state_refusal_behavior():
    """Irrelevant-tool refusal verified by behavior: distractor never called."""
    sandbox = ToolSandbox(seed=9)  # no calls made
    result = evaluate_state_asserts(sandbox, [
        StateAssert(type="tool_not_called", tool="search_flights", must_pass=True),
        StateAssert(type="tool_not_called", tool="calculator", must_pass=True),
    ])
    assert result["passed"]
    assert result["score"] == 1.0
    sandbox.cleanup()
