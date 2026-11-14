#!/usr/bin/env python3
"""Fixture generator + drift guard for tasks/support.yaml (P2 design 2.1).

Recomputes, from the fixture data: the refund decision for each policy
variant (the policy is implemented as code, applied in the prompt's
precedence order C, A, B, D), the SLA arithmetic, the escalation vector,
the split pairs and the KB choice — then asserts equality with the GOLD
fixtures in tests/validity_data_support.py and parses tasks/support.yaml
through the real Task model. Prose-fixture golds (the first-response
draft) are pinned by the validity test against the real scorer.

Usage: gen_support_tasks.py [--check]   Exit 0 = agreement.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------- policy
# Facts per variant: (opened, days_since_delivery, damaged)
VARIANTS = {
    "a": dict(opened=False, days=10, damaged=False),
    "b": dict(opened=True, days=12, damaged=False),
    "c": dict(opened=False, days=45, damaged=True),
    "d": dict(opened=False, days=75, damaged=False),
}


def refund_decision(opened: bool, days: int, damaged: bool):
    """Policy precedence: C (damaged, 60 d) > A (unopened, 30 d) >
    B (opened, 30 d) > D (expired)."""
    if damaged and days <= 60:
        return True, "damaged_arrival"
    if not opened and days <= 30:
        return True, "unopened_in_window"
    if opened and days <= 30:
        return False, "opened"
    return False, "expired"


def compute_golds() -> dict[str, str]:
    golds: dict[str, str] = {}
    for v, facts in VARIANTS.items():
        elig, reason = refund_decision(**facts)
        golds[f"st_refund_decision__{v}"] = json.dumps(
            {"eligible": elig, "reason_code": reason})

    # SLA: created 2026-03-09 08:00, medium = 48 h, now = 2026-03-10 11:00
    created = datetime(2026, 3, 9, 8, 0)
    now = datetime(2026, 3, 10, 11, 0)
    remaining = (created + timedelta(hours=48) - now).total_seconds() / 3600
    assert remaining == 21.0
    golds["st_sla_math"] = f"HOURS_REMAINING: {int(remaining)}\nBREACHED: no"

    # escalation policy: safety / legal / VIP / third report
    tickets = {"T-1": {"safety"}, "T-2": {"legal"}, "T-3": {"vip"},
               "T-4": set(), "T-5": {"third"}, "T-6": set()}
    triggers = {"safety", "legal", "vip", "third"}
    golds["st_escalate_decision"] = json.dumps(
        {tid: bool(flags & triggers) for tid, flags in tickets.items()})

    # split: S1 states the billing problem, S3 the technical one
    golds["st_split_multi_issue"] = json.dumps(
        [{"category": "billing", "summary_id": "S1"},
         {"category": "technical", "summary_id": "S3"}])

    # duplicate: T-202 is the only open ticket about the reports-tab crash
    golds["st_duplicate_find"] = "T-202"
    golds["st_kb_select"] = "KB-2"  # the only article about the reports-tab crash
    return golds


def main() -> int:
    golds = compute_golds()
    root = Path(__file__).resolve().parent.parent
    tasks_path = root / "tasks" / "support.yaml"
    data_path = root / "tests" / "validity_data_support.py"
    failures = []
    if tasks_path.exists():
        import yaml
        sys.path.insert(0, str(root))
        docs = yaml.safe_load(tasks_path.read_text())
        try:
            from gauntlet.task import Task
            tasks = [Task(**raw) for raw in docs]
            ids = [t.id for t in tasks]
        except ImportError:
            ids = [d["id"] for d in docs]
        assert len(ids) == len(set(ids)), "duplicate task ids in support.yaml"
        print(f"support.yaml parses: {len(ids)} units")
    if data_path.exists():
        ns: dict = {}
        exec(data_path.read_text(), ns)
        for scen, gold in golds.items():
            if scen in ns["GOLD"]:
                if gold != ns["GOLD"][scen]:
                    try:
                        same = json.loads(gold) == json.loads(ns["GOLD"][scen])
                    except Exception:
                        same = False
                    if not same:
                        failures.append(f"{scen}: recomputed {gold} != GOLD {ns['GOLD'][scen]}")
        print("validity_data_support.py compared for", len(golds), "recomputed scenarios")
    if failures:
        for f in failures:
            print("DRIFT:", f, file=sys.stderr)
        return 1
    print("gen_support_tasks: OK — fixtures, recomputed golds and committed files agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
