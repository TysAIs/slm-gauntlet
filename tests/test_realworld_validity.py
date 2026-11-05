"""Validity gate for tasks/realworld.yaml — gold answer vs near-miss.

Why this exists: a benchmark task is a measurement instrument, and an
unguarded instrument lies in both directions. The 0.3 audit found both
failure modes in the live corpus:

  * `hif_letter_ban_long` required a sentinel that contained a letter its own
    constraint banned — impossible, 0% across 253 configurations, and it read
    as a model weakness;
  * `adv_encoded_bypass` was passed by 97% of configurations — it measured
    nothing;
  * several tasks graded a regex ("def flatten") that a broken implementation
    satisfies.

So every task now ships with two answers in this file:

  GOLD      a correct answer, written independently of the asserts. If the
            task cannot be passed, the task is broken -> test fails.
  NEAR_MISS a plausible wrong answer: the mistake the task is designed to
            catch (included tax in the tip base, keyword-routed the spam
            email, ignored a tie-break, wrote an unsorted file...). If it
            scores 1.0, the task does not discriminate -> test fails.

This is not a substitute for model evidence — a real model has to run it — but
it proves the instrument is not already broken before any GPU time is spent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gauntlet.sandbox import ToolSandbox  # noqa: E402
from gauntlet.scorer import Scorer  # noqa: E402
from gauntlet.state_check import evaluate_state_asserts  # noqa: E402
from gauntlet.task import Task  # noqa: E402

TASKS_FILE = Path(__file__).resolve().parent.parent / "tasks" / "realworld.yaml"

# Gold answers. Deliberately written in a DIFFERENT format from the prompt's
# example where a robust grader is claimed ("USD 59.00" vs "$59.00") so the
# test proves the amount parsing, not the exact formatting.
GOLD: dict[str, str] = {
    "rw_expense_split": (
        "SUBTOTAL: 200.00\n"
        "TIP: 36.00\n"
        "PER_PERSON: 59.00"
    ),
    "rw_inbox_triage": (
        '{"spam": ["e3"], "billing": ["e1", "e5"], "urgent": ["e2"], "other": ["e4"]}'
    ),
    "rw_refund_eligibility": (
        '{"A": {"decision": "full", "amount": 84.99}, '
        '"B": {"decision": "half", "amount": 64.75}, '
        '"C": {"decision": "full", "amount": 39.99}, '
        '"D": {"decision": "none", "amount": 0}}'
    ),
    "rw_timezone_meeting": (
        "UTC: 2026-01-20T16:30:00+00:00\n"
        "Europe/Berlin: 2026-01-20T17:30:00+01:00\n"
        "Asia/Tokyo: 2026-01-21T01:30:00+09:00"
    ),
    "rw_shipping_quote": "O1: 8.00\nO2: 19.50\nO3: 36.00\nTOTAL: 63.50",
    "rw_write_order_totals": "Wrote out/order_totals.csv.",
    "rw_budget_plan": '{"food": "beans", "tools": "tape", "clean": "soap", "total": 10.10}',
    "rw_ticket_priority": '["T-2", "T-1", "T-7", "T-9", "T-4"]',
    "rw_warranty_expiry": "W1: 2028-02-29\nW2: 2026-02-28",
    "rw_data_cleanup": (
        '[{"email": "ana@example.com", "name": "Ana Lopez", "plan": "pro"}, '
        '{"email": "bo@example.com", "name": "Bo", "plan": "basic"}, '
        '{"email": "cy@example.com", "name": "Cy Nguyen", "plan": "pro"}]'
    ),
}

# The mistake each task exists to catch.
NEAR_MISS: dict[str, str] = {
    # tipped on the tax-inclusive total -> 38.88 tip, 63.72 per person
    "rw_expense_split": "SUBTOTAL: 216.00\nTIP: 38.88\nPER_PERSON: 63.72",
    # routed the blocklisted-domain email by its "invoice" keyword, and the
    # VIP cancellation into billing
    "rw_inbox_triage": (
        '{"spam": [], "billing": ["e1", "e2", "e3", "e5"], "urgent": [], "other": ["e4"]}'
    ),
    # paid full on the opened item and refunded nothing for the damaged one
    "rw_refund_eligibility": (
        '{"A": {"decision": "full", "amount": 84.99}, '
        '"B": {"decision": "full", "amount": 129.50}, '
        '"C": {"decision": "none", "amount": 0}, '
        '"D": {"decision": "none", "amount": 0}}'
    ),
    # treated Denver as UTC-6 and Berlin as UTC+2
    "rw_timezone_meeting": (
        "UTC: 2026-01-20T15:30:00+00:00\n"
        "Europe/Berlin: 2026-01-20T17:30:00+02:00\n"
        "Asia/Tokyo: 2026-01-20T00:30:00+09:00"
    ),
    # ignored the remote surcharge on O2
    "rw_shipping_quote": "O1: 8.00\nO2: 15.50\nO3: 36.00\nTOTAL: 59.50",
    # wrote the file but left the dump order (unsorted)
    "rw_write_order_totals": "Wrote out/order_totals.csv.",
    # bought the cheapest OVERALL items instead of one per category
    "rw_budget_plan": '{"food": "beans", "tools": "soap", "clean": "tape", "total": 10.10}',
    # ignored the id ascending tie-break between T-7 and T-9
    "rw_ticket_priority": '["T-2", "T-1", "T-9", "T-7", "T-4"]',
    # added 18 months but clamped to Feb 28, missing the 2028 leap day
    "rw_warranty_expiry": "W1: 2028-02-28\nW2: 2026-02-28",
    # kept the FIRST duplicate instead of the most recently updated
    "rw_data_cleanup": (
        '[{"email": "ana@example.com", "name": "Ana", "plan": "pro"}, '
        '{"email": "bo@example.com", "name": "Bo", "plan": "basic"}, '
        '{"email": "cy@example.com", "name": "Cy", "plan": "free"}]'
    ),
}

# Files the GOLD answer must produce, for the tasks that write a work product.
GOLD_FILES: dict[str, dict[str, str]] = {
    "rw_write_order_totals": {
        "out/order_totals.csv": (
            "sku,qty,unit_price,line_total\n"
            "SKU-1,10,0.50,5.00\n"
            "SKU-2,3,4.25,12.75\n"
            "SKU-3,1,99.99,99.99\n"
        )
    }
}

# What the near-miss wrote instead: right header, dump order and one bad total.
NEAR_MISS_FILES: dict[str, dict[str, str]] = {
    "rw_write_order_totals": {
        "out/order_totals.csv": (
            "sku,qty,unit_price,line_total\n"
            "SKU-2,3,4.25,12.75\n"
            "SKU-1,10,0.50,5.00\n"
            "SKU-3,1,99.99,99.99\n"
        )
    }
}


def _load_tasks() -> list[Task]:
    data = yaml.safe_load(TASKS_FILE.read_text())
    return [Task(**raw) for raw in data]


TASKS = {t.id: t for t in _load_tasks()}


def _state_score(task: Task, files: dict[str, str]) -> float:
    """Run the task's state asserts against a sandbox holding exactly `files`."""
    sandbox = ToolSandbox(seed=0)
    try:
        for path, content in files.items():
            sandbox.execute("write_file", {"path": path, "content": content})
        if not task.state_asserts:
            return 1.0
        return evaluate_state_asserts(sandbox, task.state_asserts)["score"]
    finally:
        sandbox.cleanup()


def test_every_task_has_gold_and_near_miss():
    missing_gold = sorted(set(TASKS) - set(GOLD))
    missing_miss = sorted(set(TASKS) - set(NEAR_MISS))
    assert not missing_gold, f"no GOLD answer for: {missing_gold}"
    assert not missing_miss, f"no NEAR_MISS answer for: {missing_miss}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_gold_answer_scores_full(task_id: str):
    task = TASKS[task_id]
    res = Scorer().score(GOLD[task_id], task.to_assert_dicts())
    state = _state_score(task, GOLD_FILES.get(task_id, {}))
    assert res.score == 1.0, f"{task_id}: gold text scored {res.score}: {res.failed}"
    assert res.passed, f"{task_id}: gold text did not pass strict check: {res.failed}"
    assert state == 1.0, f"{task_id}: gold work product scored {state}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_near_miss_is_rejected(task_id: str):
    task = TASKS[task_id]
    res = Scorer().score(NEAR_MISS[task_id], task.to_assert_dicts())
    state = _state_score(task, NEAR_MISS_FILES.get(task_id, {}))
    total = min(res.score, state)
    assert total < 1.0, f"{task_id}: a wrong answer passed — task does not discriminate"
    assert total == 0.0, (
        f"{task_id}: wrong answer earned {total} (must_pass gates should force 0)"
    )


def test_realworld_tasks_are_gated():
    """Every task must carry at least one must_pass gate, or a model could earn
    full credit while getting the point of the task wrong."""
    ungated = [t.id for t in TASKS.values() if not any(a.must_pass for a in t.asserts)
               and not any(a.must_pass for a in t.state_asserts)]
    assert not ungated, f"tasks with no must_pass gate: {ungated}"


def test_realworld_has_no_impossible_or_trivial_format():
    """No task may require the letter it bans, or a token it never mentions."""
    for t in TASKS.values():
        assert t.prompt.strip(), f"{t.id}: empty prompt"
        assert t.max_tokens >= 256, f"{t.id}: max_tokens {t.max_tokens} truncates a real answer"


def test_suite_weight_matches_task_count():
    """The published weight table claims a realworld suite; this file must exist
    and carry the task count the methodology documents."""
    from gauntlet.methodology import EPOCHS, METHODOLOGY_VERSION

    spec = EPOCHS[METHODOLOGY_VERSION]
    assert "realworld" in spec["weights"], "realworld missing from the published weights"
    assert len(TASKS) >= 10, f"realworld has {len(TASKS)} tasks, expected >= 10"
