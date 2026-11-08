#!/usr/bin/env python3
"""Predict a task set's discrimination WITHOUT spending GPU time.

The 0.5.0 corpus stores every model's final answer per task. When a 0.5.1 task is a
scored SUB-UNIT of a 0.5.0 scenario that keeps the scenario's prompt byte-for-byte
(id `<scenario>__<unit>`), the recorded answers still are the answers that prompt
produces — so the new asserts can be replayed against them and the pass count is
exact, not a forecast.

Guarded: the unit's prompt must be byte-identical to the base scenario's prompt in
the git revision named by --base-rev. A unit whose prompt changed (or that has no
base scenario) is reported as needs-GPU-probe and never silently "predicted".

  python3 scripts/replay_rescore.py --base-rev 067208f
  python3 scripts/replay_rescore.py --base-rev 067208f --json results/_published/replay_0.5.1.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from gauntlet.scorer import Scorer  # noqa: E402
from gauntlet.task import Task  # noqa: E402

SUITE_FILES = ["realworld", "instruction_hard", "instruction", "structured", "structured_hard",
               "coding", "adversarial", "tooluse", "tooluse_hard", "agent_chains"]


def base_tasks(rev: str) -> dict[str, dict]:
    """Task id -> task dict from a git revision (the epoch being replayed)."""
    out: dict[str, dict] = {}
    for name in SUITE_FILES:
        try:
            raw = subprocess.run(
                ["git", "show", f"{rev}:tasks/{name}.yaml"],
                cwd=ROOT, capture_output=True, text=True, check=True,
            ).stdout
        except subprocess.CalledProcessError:
            continue
        for t in yaml.safe_load(raw) or []:
            out[t["id"]] = t
    return out


def corpus(runs: list[str]) -> dict[str, list[str]]:
    """task id -> every recorded final answer in those run logs."""
    out: dict[str, list[str]] = defaultdict(list)
    for rel in runs:
        p = ROOT / rel
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        for t in d.get("results") or []:
            for a in (t.get("attempts") or [])[:1]:
                txt = a.get("final_text")
                if txt is not None:
                    out[t["task_id"]].append(txt)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-rev", required=True, help="git rev holding the epoch's task YAML")
    ap.add_argument("--corpus", default="results/_published/discrimination_0.5.0.json")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    disc = json.loads((ROOT / args.corpus).read_text())
    runs = disc.get("runs") or []
    answers = corpus(runs)
    old = base_tasks(args.base_rev)
    scorer = Scorer()

    rows, probe = [], []
    for name in SUITE_FILES:
        path = ROOT / "tasks" / f"{name}.yaml"
        if not path.exists():
            continue
        for td in yaml.safe_load(path.read_text()) or []:
            tid = td["id"]
            task = Task(**td)
            base_id = tid.split("__")[0]
            rec = {
                "id": tid, "suite": task.suite, "base": base_id,
                "n": len(answers.get(base_id, [])), "pass": None, "replayable": False,
                "reason": "",
            }
            if base_id not in old:
                rec["reason"] = "no base scenario in base rev"
            elif old[base_id].get("prompt") != td.get("prompt"):
                rec["reason"] = "prompt changed vs base rev"
            elif not answers.get(base_id):
                rec["reason"] = "no recorded answers"
            else:
                rec["replayable"] = True
                ok = 0
                texts = answers[base_id]
                for txt in texts:
                    r = scorer.score(txt, task.to_assert_dicts())
                    ok += int(r.passed)
                rec["pass"] = ok
                rec["n"] = len(texts)
            (rows if rec["replayable"] else probe).append(rec)

    print(f"{'task':42s} {'n':>3s} {'pass':>4s}  note")
    for r in rows:
        flag = "  <-- ZERO" if r["pass"] == 0 else ("  <-- FREE" if r["pass"] == r["n"] else "")
        print(f"{r['id']:42s} {r['n']:3d} {r['pass']:4d}{flag}")
    if probe:
        print("\nneeds GPU probe (prompt changed / no base / new task):")
        for r in probe:
            print(f"  {r['id']:40s} {r['reason']}")
    zero = [r['id'] for r in rows if r['pass'] == 0]
    free = [r['id'] for r in rows if r['pass'] == r['n']]
    print(f"\nreplayed {len(rows)} units: {len(zero)} at 0/n {zero}, {len(free)} at n/n {free}")
    if args.json:
        (ROOT / args.json).write_text(json.dumps({"rows": rows, "needs_probe": probe}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
