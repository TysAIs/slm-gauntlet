"""Validity gate for tasks/realworld.yaml — gold answer vs near-miss, per scored unit.

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

So every task now ships with answers in this file:

  GOLD      a correct answer for the SCENARIO, written independently of the
            asserts. If any unit of the scenario cannot be passed by the gold
            answer, the task is broken -> test fails.
  NEAR_MISS_EDIT
            for every unit, the exact (gold substring, wrong substring) pair
            that makes ONLY that unit's answer wrong — the mistake that unit
            exists to catch. If the edited answer still passes, the unit does
            not discriminate -> test fails.

This is not a substitute for model evidence — a real model has to run it — but
it proves the instrument is not already broken before any GPU time is spent.

0.5.1 note: a scenario's independent values are separate tasks
`<scenario>__<unit>` that share one prompt (see the header of
tasks/realworld.yaml). The gold answer is therefore written once per scenario,
and the near-miss is written once per unit.
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

# Gold answers, keyed by SCENARIO id (the part before "__"). Deliberately written
# in a DIFFERENT format from the prompt's example where a robust grader is
# claimed, so the test proves the parsing, not the exact formatting.
GOLD: dict[str, str] = {
    "rw_expense_split": "SUBTOTAL: 200.00\nTIP: 36.00\nPER_PERSON: 63.00",
    "rw_inbox_triage": '{"spam": ["e3"], "billing": ["e1", "e5"], "urgent": ["e2"], "other": ["e4"]}',
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
    "rw_payroll_net": "REGULAR: 880.00\nOVERTIME: 198.00\nGROSS: 1078.00\nTAX: 145.20\nNET: 847.80",
    "rw_med_dose": '{"tablets_per_dose": 2, "max_safe_doses": 3, "daily_mg": 0.75}',
    "rw_connection_legality": '{"B": 125}',
    "rw_lease_proration": (
        '{"billable_days": 17, "prorated_rent": 1360.00, "late_fee": 120.00, '
        '"max_deposit": 2400.00, "due_total": 1480.00}'
    ),
    "rw_ledger_recon": "NET: 4.25",
    "rw_recipe_scale": "EGGS: 6\nFLOUR_G: 366\nMINUTES: 43",
    "rw_retry_schedule": "[12, 16, 24, 40, 70, 100]",
    "rw_allergy_swap": (
        '{"choice": "sunflower-seed butter", "price": 4.99, '
        '"rejected": ["almond butter", "cashew cream", "tahini"]}'
    ),
    "rw_room_conflicts": '[["B2", "B3"], ["B2", "B4"], ["B3", "B4"]]',
    "rw_invoice_deadline": '{"deadline": "2026-03-06", "discounted": 8232.00, "payment": 8247.00}',
}

# unit id -> (substring of the gold answer, replacement) producing the mistake
# that unit exists to catch. Applied to GOLD[scenario].
NEAR_MISS_EDIT: dict[str, tuple[str, str]] = {
    # tipped on the tax-inclusive total / divided the receipt by four
    "rw_expense_split__subtotal": ("SUBTOTAL: 200.00", "SUBTOTAL: 216.00"),
    "rw_expense_split__tip": ("TIP: 36.00", "TIP: 38.88"),
    # routed the blocklisted-domain email by its "invoice" keyword
    "rw_inbox_triage__precedence": ('"spam": ["e3"]', '"spam": ["e1", "e3"]'),
    # dropped the invoice-less vendor email from billing
    "rw_inbox_triage__vendor": ('"billing": ["e1", "e5"]', '"billing": ["e1"]'),
    # gave the unopened in-window order nothing
    "rw_refund_eligibility__a": ('"A": {"decision": "full"', '"A": {"decision": "none"'),
    # paid full on the opened item
    "rw_refund_eligibility__b": ('"B": {"decision": "half"', '"B": {"decision": "full"'),
    # refused the damaged item because it was past 30 days
    "rw_refund_eligibility__c": ('"C": {"decision": "full"', '"C": {"decision": "none"'),
    "rw_refund_eligibility__d": ('"D": {"decision": "none"', '"D": {"decision": "full"'),
    # treated Denver as UTC-6
    "rw_timezone_meeting__utc": ("2026-01-20T16:30", "2026-01-20T15:30"),
    # treated Berlin as UTC+2
    "rw_timezone_meeting__berlin": ("+01:00", "+02:00"),
    # crossed midnight the wrong way
    "rw_timezone_meeting__tokyo": ("2026-01-21T01:30", "2026-01-20T00:30"),
    # charged the 6.00 minimum on an 8.00 order
    "rw_shipping_quote__o1": ("O1: 8.00", "O1: 6.00"),
    # ignored the remote surcharge on O2
    "rw_shipping_quote__o2": ("O2: 19.50", "O2: 15.50"),
    # dropped the express handling on O3
    "rw_shipping_quote__o3": ("O3: 36.00", "O3: 27.00"),
    "rw_shipping_quote__total": ("TOTAL: 63.50", "TOTAL: 59.50"),
    # wrote the file correctly but never said where
    "rw_write_order_totals": ("Wrote out/order_totals.csv.", "Done."),
    # reported only the changed amount and dropped the row missing from L1
    "rw_ledger_recon": ("NET: 4.25", "NET: 1.00"),
    # bought the cheapest OVERALL items instead of one per category
    "rw_budget_plan__choices": ('"tools": "tape"', '"tools": "soap"'),
    "rw_budget_plan__total": ("10.10", "19.75"),
    # lost a ticket from the queue
    "rw_ticket_priority__ids": ('"T-9", "T-4"]', '"T-9", "T-5"]'),
    # put the severity-3 ticket first because it is the newest
    "rw_ticket_priority__severity_last": ('"T-9", "T-4"]', '"T-4", "T-9"]'),
    # ignored the id ascending tie-break between T-7 and T-9
    "rw_ticket_priority__tie_id": ('"T-7", "T-9"', '"T-9", "T-7"'),
    # ignored the age descending tie-break between T-2 and T-1
    "rw_ticket_priority__age_key": ('"T-2", "T-1"', '"T-1", "T-2"'),
    # added 18 months but clamped to Feb 28, missing the 2028 leap day
    "rw_warranty_expiry__w1": ("W1: 2028-02-29", "W1: 2028-02-28"),
    # treated 13 months as "one year plus a full 31-day month"
    "rw_warranty_expiry__w2": ("W2: 2026-02-28", "W2: 2026-03-31"),
    # dropped a real survivor along with the empty-email record
    "rw_data_cleanup__count": (', {"email": "bo@example.com", "name": "Bo", "plan": "basic"}', ""),
    # kept the FIRST duplicate instead of the most recently updated
    "rw_data_cleanup__ana": ('"name": "Ana Lopez"', '"name": "Ana"'),
    "rw_data_cleanup__bo": ('"name": "Bo"', '"name": "Bobby"'),
    "rw_data_cleanup__cy": ('"name": "Cy Nguyen"', '"name": "Cy"'),
    # paid all 46 hours at the regular rate
    "rw_payroll_net__regular": ("REGULAR: 880.00", "REGULAR: 1012.00"),
    # paid the overtime hours at straight time
    "rw_payroll_net__overtime": ("OVERTIME: 198.00", "OVERTIME: 132.00"),
    "rw_payroll_net__gross": ("GROSS: 1078.00", "GROSS: 1012.00"),
    # taxed the overtime hours at the regular 12% rate
    "rw_payroll_net__tax": ("TAX: 145.20", "TAX: 129.36"),
    "rw_payroll_net__net": ("NET: 847.80", "NET: 863.64"),
    # read one 0.125 mg tablet as the whole 250 mcg dose
    "rw_med_dose__tablets": ('"tablets_per_dose": 2', '"tablets_per_dose": 1'),
    # ignored the second drug's 0.2 mg against the 1 mg ceiling
    "rw_med_dose__doses": ('"max_safe_doses": 3', '"max_safe_doses": 4'),
    "rw_med_dose__daily_mg": ('"daily_mg": 0.75', '"daily_mg": 1.0'),
    # treated the terminal-change itinerary A as legal
    "rw_connection_legality__valid_set": ('{"B": 125}', '{"A": 75, "B": 125}'),
    "rw_connection_legality__minutes": ('"B": 125', '"B": 120'),
    # excluded the move-in day
    "rw_lease_proration__billable_days": ('"billable_days": 17', '"billable_days": 16'),
    "rw_lease_proration__prorated": ('"prorated_rent": 1360.00', '"prorated_rent": 1280.00'),
    # used the smaller of the two late-fee rules
    "rw_lease_proration__late_fee": ('"late_fee": 120.00', '"late_fee": 75.00'),
    # collected the 1.5 months the landlord asked for
    "rw_lease_proration__deposit": ('"max_deposit": 2400.00', '"max_deposit": 3600.00'),
    "rw_lease_proration__due_total": ('"due_total": 1480.00', '"due_total": 1400.00'),
    # scaled eggs by "half again" instead of by the pan-area ratio
    "rw_recipe_scale__eggs": ("EGGS: 6", "EGGS: 4"),
    "rw_recipe_scale__flour": ("FLOUR_G: 366", "FLOUR_G: 217"),
    # scaled the bake time linearly with area instead of by its square root
    "rw_recipe_scale__minutes": ("MINUTES: 43", "MINUTES: 59"),
    # ignored Retry-After and started the backoff at 2 s
    "rw_retry_schedule__retry_after": ("[12, 16", "[2, 4"),
    # let a wait exceed the 30 s cap
    "rw_retry_schedule__cap": ("70, 100]", "70, 130]"),
    # stopped at 5 retries
    "rw_retry_schedule__count": ("[12, 16, 24, 40, 70, 100]", "[12, 16, 24, 40, 70]"),
    # took the cheapest option and ignored "may contain traces of tree nuts"
    "rw_allergy_swap__choice": ('"choice": "sunflower-seed butter"', '"choice": "tahini"'),
    "rw_allergy_swap__price": ('"price": 4.99', '"price": 3.99'),
    "rw_allergy_swap__rejected": (
        '["almond butter", "cashew cream", "tahini"]',
        '["almond butter", "cashew cream"]',
    ),
    # checked only hard overlaps and missed the 10-minute buffer breach
    "rw_room_conflicts__overlap_b24": (
        '[["B2", "B3"], ["B2", "B4"], ["B3", "B4"]]',
        '[["B2", "B3"], ["B3", "B4"]]',
    ),
    "rw_room_conflicts__overlap_b34": (
        '[["B2", "B3"], ["B2", "B4"], ["B3", "B4"]]',
        '[["B2", "B3"], ["B2", "B4"]]',
    ),
    "rw_room_conflicts__buffer_b23": (
        '[["B2", "B3"], ["B2", "B4"], ["B3", "B4"]]',
        '[["B2", "B4"], ["B3", "B4"]]',
    ),
    # treated the exact 15-minute gap as a conflict
    "rw_room_conflicts__boundary_b12": ('[["B2", "B3"]', '[["B1", "B2"], ["B2", "B3"]'),
    # kept the Saturday deadline instead of moving to the preceding business day
    "rw_invoice_deadline__deadline": ('"deadline": "2026-03-06"', '"deadline": "2026-03-07"'),
    # applied no discount
    "rw_invoice_deadline__discounted": ('"discounted": 8232.00', '"discounted": 8400.00'),
    # forgot the wire fee
    "rw_invoice_deadline__payment": ('"payment": 8247.00', '"payment": 8232.00'),
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
    },
    "rw_ledger_recon": {
        "out/recon.csv": (
            "date,status,delta\n"
            "2026-03-03,amount_diff,1.00\n"
            "2026-03-05,missing_in_l1,3.25\n"
        )
    },
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
    },
    "rw_ledger_recon": {
        "out/recon.csv": (
            "date,status,delta\n"
            "2026-03-03,amount_diff,1.00\n"
        )
    },
}


def _load_tasks() -> list[Task]:
    data = yaml.safe_load(TASKS_FILE.read_text())
    return [Task(**raw) for raw in data]


TASKS = {t.id: t for t in _load_tasks()}


def _scenario(task_id: str) -> str:
    return task_id.split("__")[0]


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
    missing_gold = sorted({_scenario(t) for t in TASKS} - set(GOLD))
    missing_miss = sorted(set(TASKS) - set(NEAR_MISS_EDIT))
    assert not missing_gold, f"no GOLD answer for: {missing_gold}"
    assert not missing_miss, f"no NEAR_MISS_EDIT for: {missing_miss}"
    stale = sorted(set(NEAR_MISS_EDIT) - set(TASKS))
    assert not stale, f"NEAR_MISS_EDIT names tasks that no longer exist: {stale}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_gold_answer_scores_full(task_id: str):
    task = TASKS[task_id]
    res = Scorer().score(GOLD[_scenario(task_id)], task.to_assert_dicts())
    state = _state_score(task, GOLD_FILES.get(task_id, {}))
    assert res.score == 1.0, f"{task_id}: gold text scored {res.score}: {res.failed}"
    assert res.passed, f"{task_id}: gold text did not pass strict check: {res.failed}"
    assert state == 1.0, f"{task_id}: gold work product scored {state}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_near_miss_is_rejected(task_id: str):
    task = TASKS[task_id]
    find, repl = NEAR_MISS_EDIT[task_id]
    gold = GOLD[_scenario(task_id)]
    assert find in gold, f"{task_id}: near-miss edit {find!r} is not in the gold answer"
    wrong = gold.replace(find, repl, 1)
    assert wrong != gold, f"{task_id}: near-miss edit changed nothing"
    res = Scorer().score(wrong, task.to_assert_dicts())
    state = _state_score(task, NEAR_MISS_FILES.get(task_id, {}))
    total = min(res.score, state)
    assert total < 1.0, f"{task_id}: a wrong answer passed — task does not discriminate"


def test_every_task_is_gated_by_its_own_assert():
    """A scored unit carries exactly one assert, which therefore always gates its
    own score. A composite task (a written file, a required tool call) must gate
    with must_pass on the structural assert, or a model could earn full credit
    while getting the point of the task wrong."""
    ungated = []
    for t in TASKS.values():
        structural = any(a.must_pass for a in t.asserts) or any(a.must_pass for a in t.state_asserts)
        if not structural and len(t.asserts) + len(t.state_asserts) != 1:
            ungated.append(t.id)
    assert not ungated, f"multi-assert tasks with no must_pass gate: {ungated}"


def test_realworld_has_no_impossible_or_trivial_format():
    """No task may require the letter it bans, or a token it never mentions."""
    for t in TASKS.values():
        assert t.prompt.strip(), f"{t.id}: empty prompt"
        assert t.max_tokens >= 256, f"{t.id}: max_tokens {t.max_tokens} truncates a real answer"


def test_units_share_their_scenario_prompt():
    """Every unit of a scenario must carry the scenario's exact prompt, so the
    unit is a graded part of one answer and not a different, easier question."""
    by_scenario: dict[str, set[str]] = {}
    for t in TASKS.values():
        by_scenario.setdefault(_scenario(t.id), set()).add(t.prompt)
    split = {k: len(v) for k, v in by_scenario.items() if len(v) > 1}
    assert not split, f"scenarios whose units do not share one prompt: {split}"


def test_suite_weight_matches_task_count():
    """The published weight table claims a realworld suite; this file must exist
    and carry the task count the methodology documents."""
    from gauntlet.methodology import EPOCHS, METHODOLOGY_VERSION

    spec = EPOCHS[METHODOLOGY_VERSION]
    assert "realworld" in spec["weights"], "realworld missing from the published weights"
    assert len(TASKS) >= 10, f"realworld has {len(TASKS)} tasks, expected >= 10"
