"""Thermal guard + logic-audit regressions (docs/AUDIT-LOGIC-v0.5.md).

Every test here pins a defect that the audit found and this commit fixed. They
run without a GPU: the sensor read is monkeypatched.
"""

import pytest

from gauntlet import thermal
from gauntlet.report import aggregate_results
from gauntlet.sandbox import ToolSandbox
from gauntlet.scorer import Scorer
from gauntlet.state_check import evaluate_state_asserts
from gauntlet.task import StateAssert, Task

# --- F2: the 89C rule is a checked threshold -------------------------------

def test_thermal_limit_is_tylers_89c():
    assert thermal.THERMAL_LIMIT_C == 89.0


def test_thermal_blocks_at_ceiling_and_passes_below(monkeypatch):
    monkeypatch.setattr(thermal, "read_gpu_temp_c", lambda *a, **k: 89.0)
    with pytest.raises(SystemExit):
        thermal.assert_thermal_ok(89.0)

    monkeypatch.setattr(thermal, "read_gpu_temp_c", lambda *a, **k: 88.9)
    assert thermal.assert_thermal_ok(89.0) == 88.9


def test_thermal_missing_sensor_is_not_an_error(monkeypatch):
    monkeypatch.setattr(thermal, "read_gpu_temp_c", lambda *a, **k: None)
    assert thermal.assert_thermal_ok(89.0) is None


def test_thermal_zero_disables_the_check(monkeypatch):
    monkeypatch.setattr(thermal, "read_gpu_temp_c", lambda *a, **k: 99.0)
    assert thermal.assert_thermal_ok(0) is None


# --- F3: an absent state path must not equal False -------------------------

def test_missing_boolean_path_does_not_pass_as_false():
    sb = ToolSandbox(seed=0)
    r = evaluate_state_asserts(sb, [StateAssert(type="state_path", path="flags.sent", equals=False)])
    assert not r["passed"]
    sb.cleanup()


def test_missing_container_path_still_passes_as_empty():
    sb = ToolSandbox(seed=0)
    r = evaluate_state_asserts(sb, [StateAssert(type="state_path", path="reservations", equals=[])])
    assert r["passed"]
    sb.cleanup()


def test_present_false_still_matches():
    sb = ToolSandbox(seed=0)
    sb.state["flags"] = {"sent": False}
    r = evaluate_state_asserts(sb, [StateAssert(type="state_path", path="flags.sent", equals=False)])
    assert r["passed"]
    sb.cleanup()


# --- F8: a failed must_pass gate zeroes the combined rubric ----------------

def test_gated_text_assert_zeroes_combined_rubric():
    score = Scorer().score("wrong", [{"type": "contains_all", "values": ["right"], "must_pass": True}])
    assert score.gated
    combined = 0.0 if score.gated else score.score
    assert combined == 0.0


def test_ungated_partial_credit_is_not_flagged_as_gated():
    score = Scorer().score("half", [{"type": "contains_all", "values": ["half"]},
                                    {"type": "contains_all", "values": ["other"]}])
    assert not score.gated
    assert score.score == 0.5


# --- F9: flaky tasks actually get repeats >= 3 ----------------------------

def _task(**kw):
    base = dict(id="t", suite="s", description="d", prompt="p",
                asserts=[{"type": "contains_all", "values": ["x"]}])
    base.update(kw)
    return Task(**base)


def test_flaky_raises_repeats_to_three():
    assert _task(flaky=True).repeats == 3
    assert _task(flaky=True, repeats=5).repeats == 5
    assert _task(repeats=1).repeats == 1


# --- F4: a partial-coverage run says so -----------------------------------

def test_summary_reports_partial_coverage():
    results = [{"task_id": "a", "suite": "tooluse", "repeats": 1, "pass1": 1.0, "pass_k": 1.0,
                "attempts": [{"terminated": "completed", "passed": True, "score": 1.0}]}]
    summary = aggregate_results(results)
    assert summary["coverage"]["partial"] is True
    assert summary["coverage"]["tasks"] == 1
    assert "instruction" in summary["coverage"]["missing_suites"]
