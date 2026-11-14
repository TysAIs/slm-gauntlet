"""Validity gate for tasks/support.yaml — gold answer vs near-miss, per scored unit.

Mirrors tests/test_realworld_validity.py (0.5.1 convention): every scenario
ships a GOLD answer that must score full through the real Scorer and the
real state checker, and every unit ships a NEAR-MISS that must fail. Gold
answers and near-miss edits live in tests/validity_data_support.py, which
is generated from the same fixture data as the task file itself
(scripts/gen_support_tasks.py regenerates and re-verifies both).

Scenario convention: the scenario id is the part of the unit id before the
first "__". Suites whose scenarios nest one level deeper carry a SCENARIOS
override in the data module.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from validity_data_support import (  # noqa: E402
    GOLD,
    GOLD_CALLS,
    GOLD_FILES,
    NEAR_FILES,
    NEAR_MISS_EDIT,
    SCENARIOS,
)

from gauntlet.sandbox import ToolSandbox  # noqa: E402
from gauntlet.scorer import Scorer, state_predicate_check  # noqa: E402
from gauntlet.state_check import evaluate_state_asserts  # noqa: E402
from gauntlet.task import Task  # noqa: E402

TASKS_FILE = Path(__file__).resolve().parent.parent / "tasks" / "support.yaml"


def _load_tasks() -> list[Task]:
    data = yaml.safe_load(TASKS_FILE.read_text())
    return [Task(**raw) for raw in data]


TASKS = {t.id: t for t in _load_tasks()}


def _scenario(task_id: str) -> str:
    return SCENARIOS.get(task_id, task_id.split("__")[0])


def _state_score(task: Task, files: dict[str, str],
                 calls: tuple[str, ...] = (),
                 output: str = "") -> float:
    # state_predicate asserts are scored against the sandbox (with the run's
    # final text as `out`) exactly the way the runner scores them: split out,
    # own weights and must_pass gates, folded into the state score.
    sandbox = ToolSandbox(seed=0)
    try:
        for name in calls:
            sandbox.execute(name, {})
        for path, content in files.items():
            sandbox.execute("write_file", {"path": path, "content": content})
        scores = []
        if task.state_asserts:
            scores.append(evaluate_state_asserts(sandbox, task.state_asserts)["score"])
        _, sp_asserts = Scorer().split_state_predicates(task.to_assert_dicts())
        if sp_asserts:
            sp_earned = sp_total = 0.0
            sp_gated = False
            for a in sp_asserts:
                w = float(a.get("weight", 1.0))
                sp_total += w
                if state_predicate_check(sandbox, a["expr"], output=output).passed:
                    sp_earned += w
                elif a.get("must_pass"):
                    sp_gated = True
            scores.append(0.0 if sp_gated else (sp_earned / sp_total if sp_total else 1.0))
        return sum(scores) / len(scores) if scores else 1.0
    finally:
        sandbox.cleanup()


def _text_score(task: Task, text: str) -> float:
    # text-only half: state_predicate asserts are excluded (they grade the
    # sandbox, not the text) exactly as the runner excludes them.
    text_asserts, _ = Scorer().split_state_predicates(task.to_assert_dicts())
    if not text_asserts:
        return 1.0
    res = Scorer().score(text, text_asserts)
    return 0.0 if not res.passed else res.score


def test_every_task_has_gold_and_near_miss():
    missing_gold = sorted({_scenario(t) for t in TASKS} - set(GOLD))
    missing_miss = sorted(set(TASKS) - set(NEAR_MISS_EDIT))
    assert not missing_gold, f"no GOLD answer for: {missing_gold}"
    assert not missing_miss, f"no NEAR_MISS_EDIT for: {missing_miss}"
    stale = sorted(set(NEAR_MISS_EDIT) - set(TASKS))
    assert not stale, f"NEAR_MISS_EDIT names tasks that no longer exist: {stale}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_gold_answer_scores_full(task_id: str):
    task = TASKS[task_id]
    text_asserts, _ = Scorer().split_state_predicates(task.to_assert_dicts())
    res = Scorer().score(GOLD[_scenario(task_id)], text_asserts) if text_asserts else None
    state = _state_score(task, GOLD_FILES.get(task_id, {}),
                         GOLD_CALLS.get(task_id, ()),
                         output=GOLD[_scenario(task_id)])
    if res is not None:
        assert res.score == 1.0, f"{task_id}: gold text scored {res.score}: {res.failed}"
        assert res.passed, f"{task_id}: gold text did not pass strict check: {res.failed}"
    assert state == 1.0, f"{task_id}: gold work product scored {state}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_near_miss_is_rejected(task_id: str):
    task = TASKS[task_id]
    edit = NEAR_MISS_EDIT[task_id]
    if isinstance(edit, dict) and "files" in edit:
        assert task_id in NEAR_FILES or edit["files"], (
            f"{task_id}: file-state near-miss declared but no NEAR_FILES entry")
        state = _state_score(task, NEAR_FILES.get(task_id, {}),
                             GOLD_CALLS.get(task_id, ()),
                             output=GOLD[_scenario(task_id)])
        total = min(_text_score(task, GOLD[_scenario(task_id)]), state)
        assert total < 1.0, (
            f"{task_id}: the near-miss work product passed — task does not discriminate")
        return
    find, repl = edit
    gold = GOLD[_scenario(task_id)]
    assert find in gold, f"{task_id}: near-miss edit {find!r} is not in the gold answer"
    wrong = gold.replace(find, repl, 1)
    assert wrong != gold, f"{task_id}: near-miss edit changed nothing"
    text = _text_score(task, wrong)
    state = _state_score(task, GOLD_FILES.get(task_id, {}),
                         GOLD_CALLS.get(task_id, ()), output=wrong)
    total = min(text, state)
    assert total < 1.0, f"{task_id}: a wrong answer passed — task does not discriminate"


def test_every_task_is_gated_by_its_own_assert():
    ungated = []
    for t in TASKS.values():
        structural = any(a.must_pass for a in t.asserts) or any(a.must_pass for a in t.state_asserts)
        if not structural and len(t.asserts) + len(t.state_asserts) != 1:
            ungated.append(t.id)
    assert not ungated, f"multi-assert tasks with no must_pass gate: {ungated}"


def test_no_impossible_or_trivial_format():
    for t in TASKS.values():
        assert t.prompt.strip(), f"{t.id}: empty prompt"
        assert t.max_tokens >= 256, f"{t.id}: max_tokens {t.max_tokens} truncates a real answer"


def test_units_share_their_scenario_prompt():
    by_scenario: dict[str, set[str]] = {}
    for t in TASKS.values():
        by_scenario.setdefault(_scenario(t.id), set()).add(t.prompt)
    split = {k: len(v) for k, v in by_scenario.items() if len(v) > 1}
    assert not split, f"scenarios whose units do not share one prompt: {split}"
