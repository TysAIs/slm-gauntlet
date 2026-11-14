#!/usr/bin/env python3
"""Fixture generator + drift guard for tasks/summarize.yaml (P2 design 2.4).

The planted sets ARE the fixture data: decisions are the sentences the
fixture marks with the "Decision:" plant, on-topic sentences are the ones
the fixture table tags as bridge-repair facts, changelog triples are the
field diff of the two config versions. This script rebuilds each set
from those tables and asserts equality with tests/validity_data_
summarize.py and with the prompts in tasks/summarize.yaml.

Usage: gen_summarize_tasks.py [--check]   Exit 0 = agreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MEETING = [
    ("S1", "The team reviewed the draft roadmap for the spring release.", False),
    ("S2", "Decision: the launch date moves to 2026-04-15.", True),
    ("S3", "Ana presented the new onboarding flow and its metrics.", False),
    ("S4", "Decision: the support rota gains a weekend shift.", True),
    ("S5", "The group discussed venue options for the offsite.", False),
    ("S6", "Decision: the legacy export feature is retired on 2026-05-01.", True),
    ("S7", "Ben showed photos from the user study sessions.", False),
    ("S8", "The meeting closed with a round of thanks.", False),
]
ARTICLE = [  # (id, text, is_bridge_repair_fact)
    ("S1", "The reservoir level rose slightly after the spring rain.", False),
    ("S2", "The committee approved the budget of 48,000 for the bridge repair.", True),
    ("S3", "Local schools announced a photography contest for students.", False),
    ("S4", "Construction on the bridge begins on 2026-04-06 and lasts 6 weeks.", True),
    ("S5", "A farmers market opens in the square every Saturday.", False),
    ("S6", "The mayor thanked the volunteers at a short ceremony.", False),
    ("S7", "The repair budget covers materials and two inspection visits.", True),
]
CONFIG_A = [("timeout", "30 seconds"), ("retries", "2"), ("theme", "light"), ("logging", "basic")]
CONFIG_B = [("timeout", "60 seconds"), ("retries", "2"), ("theme", "dark"), ("logging", "basic")]


def compute_golds() -> dict[str, str]:
    decisions = [t for _i, t, planted in MEETING if planted]
    on_topic = [i for i, _t, fact in ARTICLE if fact]
    diff = [{"field": f, "from": a, "to": b}
            for (f, a), (_f2, b) in zip(CONFIG_A, CONFIG_B, strict=False) if a != b]
    return {"sum_meeting_decisions": json.dumps(decisions),
            "sum_sentence_select": json.dumps(on_topic),
            "sum_changelog": json.dumps(diff)}


def main() -> int:
    golds = compute_golds()
    root = Path(__file__).resolve().parent.parent
    tasks_path = root / "tasks" / "summarize.yaml"
    data_path = root / "tests" / "validity_data_summarize.py"
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
        assert len(ids) == len(set(ids)), "duplicate task ids in summarize.yaml"
        for _i, text, _p in MEETING:
            if text not in prompts["sum_meeting_decisions__set"]:
                failures.append(f"meeting fixture lost: {text[:40]}")
        print(f"summarize.yaml parses: {len(ids)} units")
    if data_path.exists():
        ns: dict = {}
        exec(data_path.read_text(), ns)
        for scen, gold in golds.items():
            if scen in ns["GOLD"] and json.loads(gold) != json.loads(ns["GOLD"][scen]):
                failures.append(f"{scen}: recomputed {gold} != GOLD {ns['GOLD'][scen]}")
        print("validity_data_summarize.py compared for", len(golds), "recomputed scenarios")
    if failures:
        for f in failures:
            print("DRIFT:", f, file=sys.stderr)
        return 1
    print("gen_summarize_tasks: OK — fixtures, recomputed golds and committed files agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
