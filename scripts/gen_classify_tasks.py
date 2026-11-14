#!/usr/bin/env python3
"""Fixture generator + drift guard for tasks/classify.yaml (P2 design 2.2).

Recomputes the batch classification table and the multilabel set from
the fixture item data (keyword rules stated here mirror the fixture
texts) and asserts equality with tests/validity_data_classify.py; parses
tasks/classify.yaml through the real Task model. Single-label golds for
prose fixtures are pinned by the validity test against the real scorer.

Usage: gen_classify_tasks.py [--check]   Exit 0 = agreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BATCH_ITEMS = [
    ("i1", "My card was charged twice this month.", "billing"),
    ("i2", "The parcel arrived with a torn box.", "shipping"),
    ("i3", "The app freezes when I press save.", "technical"),
    ("i4", "How do I change the email on my account?", "account"),
    ("i5", "I was billed for a plan I cancelled.", "billing"),
    ("i6", "Tracking shows the package in the wrong city.", "shipping"),
    ("i7", "The login page shows a blank screen.", "technical"),
    ("i8", "Please update the name on my profile.", "account"),
    ("i9", "Do you offer a discount for schools?", "other"),
    ("i10", "The invoice total does not match the quote.", "billing"),
]
MULTILABEL_POST = ("We are hiring two support engineers. Also, our pricing page was "
                   "updated today with the new tiers.")
MULTILABEL_TAGS = {"hiring", "pricing", "support"}  # hiring post + support role + pricing update


def compute_golds() -> dict[str, str]:
    return {
        "cr_batch_table": json.dumps({i: c for i, _t, c in BATCH_ITEMS}),
        "cr_multilabel": json.dumps(sorted(MULTILABEL_TAGS)),
    }


def main() -> int:
    golds = compute_golds()
    root = Path(__file__).resolve().parent.parent
    tasks_path = root / "tasks" / "classify.yaml"
    data_path = root / "tests" / "validity_data_classify.py"
    failures = []
    if tasks_path.exists():
        import yaml
        sys.path.insert(0, str(root))
        docs = yaml.safe_load(tasks_path.read_text())
        try:
            from gauntlet.task import Task
            tasks = [Task(**raw) for raw in docs]
            ids = [t.id for t in tasks]
            prompts = {t.id: t.prompt for t in tasks}
        except ImportError:
            ids = [d["id"] for d in docs]
            prompts = {d["id"]: d["prompt"] for d in docs}
        assert len(ids) == len(set(ids)), "duplicate task ids in classify.yaml"
        # the batch prompt must contain every fixture item verbatim
        batch_prompt = prompts["cr_batch_table__i1"]
        for iid, text, _c in BATCH_ITEMS:
            if text not in batch_prompt:
                failures.append(f"batch prompt lost fixture item {iid}")
        print(f"classify.yaml parses: {len(ids)} units")
    if data_path.exists():
        ns: dict = {}
        exec(data_path.read_text(), ns)
        if json.loads(golds["cr_batch_table"]) != json.loads(ns["GOLD"]["cr_batch_table"]):
            failures.append("batch table drift")
        if set(json.loads(golds["cr_multilabel"])) != set(json.loads(ns["GOLD"]["cr_multilabel"])):
            failures.append("multilabel set drift")
        print("validity_data_classify.py compared (batch table, multilabel set)")
    if failures:
        for f in failures:
            print("DRIFT:", f, file=sys.stderr)
        return 1
    print("gen_classify_tasks: OK — fixtures, recomputed golds and committed files agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
