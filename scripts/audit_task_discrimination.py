#!/usr/bin/env python3
"""Measure per-task discrimination in the run corpus: tasks no model passes and
tasks every model passes.

WHY THIS EXISTS
---------------
A benchmark task that every model fails contributes a constant zero to every row:
it cannot rank anything, and because tasks with `must_pass` asserts score 0 unless
*all* of them hold, a task with three hard sub-answers reads as "0.00" even when a
model got two of them right. A task every model passes is just as useless in the
other direction. Both are worth knowing before a table is published, and neither
is visible in an aggregate score.

USAGE
  python3 scripts/audit_task_discrimination.py                 # sweep state corpus
  python3 scripts/audit_task_discrimination.py --glob 'results/*_2026110*.json'
  python3 scripts/audit_task_discrimination.py --json results/_published/discrimination.json

OUTPUT
  per-task pass counts and, for each task, the weighted cost that a guaranteed
  zero imposes on every published row (suite weight x task share of its suite).
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gauntlet.methodology import epoch_spec, newest_published_epoch  # noqa: E402


def run_logs_from_sweep(state: Path) -> list[Path]:
    out = []
    if not state.exists():
        return out
    for line in state.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        res = rec.get("result")
        if rec.get("status") == "done" and res and (ROOT / res).exists():
            out.append(ROOT / res)
    return out


def collect(logs: list[Path], epoch_tasks: int):
    per = defaultdict(lambda: {"pass": 0, "n": 0, "suite": None, "partial": []})
    used, skipped = [], 0
    for f in logs:
        try:
            d = json.loads(f.read_text())
        except Exception:
            skipped += 1
            continue
        results = d.get("results") or []
        if len(results) != epoch_tasks:  # partial run: not comparable
            skipped += 1
            continue
        used.append(str(f.relative_to(ROOT)))
        for t in results:
            tid = t.get("task_id")
            if not tid:
                continue
            row = per[tid]
            row["suite"] = t.get("suite")
            row["n"] += 1
            ok = t.get("pass1") == 1.0 or t.get("pass1") is True
            row["pass"] += int(bool(ok))
            for a in t.get("attempts") or []:
                row["partial"].append(float(a.get("score") or 0.0))
    return per, used, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=str(ROOT / "results/_sweep_state.jsonl"))
    ap.add_argument("--glob", default=None, help="run-log glob instead of the sweep state")
    ap.add_argument("--json", default=None, help="write the full result here")
    args = ap.parse_args()

    logs = [Path(p) for p in sorted(glob.glob(args.glob))] if args.glob else run_logs_from_sweep(Path(args.state))
    if not logs:
        print("no run logs found", file=sys.stderr)
        return 2

    epoch = newest_published_epoch({"0.5.0"}) or "0.5.0"
    spec = epoch_spec(epoch)
    full = spec["tasks"]
    per, used, skipped = collect(logs, full)
    if not per:
        print("no complete run logs found", file=sys.stderr)
        return 2

    models = max(r["n"] for r in per.values())
    suite_sizes = defaultdict(int)
    for r in per.values():
        suite_sizes[r["suite"]] += 1
    weights = spec["weights"]

    zero = {k: v for k, v in per.items() if v["pass"] == 0}
    allp = {k: v for k, v in per.items() if v["pass"] == v["n"] and v["n"] >= min(5, models)}
    constant_zero_pp = sum(weights.get(v["suite"], 0.0) / max(suite_sizes[v["suite"]], 1) for v in zero.values()) * 100

    print(f"corpus: {len(used)} complete {full}-task runs ({models} models); skipped {skipped}")
    print(f"tasks: {len(per)}; passed by nobody: {len(zero)}; passed by everybody: {len(allp)}")
    print(f"weighted cost of the unwinnable set: {constant_zero_pp:.1f} pp subtracted from EVERY row\n")

    print(f"{'task':26s} {'suite':13s} pass/model  mean_partial")
    for tid, r in sorted(per.items(), key=lambda kv: (kv[1]["pass"] / max(kv[1]["n"], 1), kv[0])):
        mp = sum(r["partial"]) / len(r["partial"]) if r["partial"] else 0.0
        flag = "  <-- unwinnable" if r["pass"] == 0 else ("  <-- no signal" if r["pass"] == r["n"] else "")
        print(f"{tid:26s} {r['suite']:13s} {r['pass']:3d}/{r['n']:<3d}      {mp:.2f}{flag}")

    if args.json:
        out = {
            "runs": used,
            "models": models,
            "epoch": epoch,
            "tasks": full,
            "constant_zero_pp": round(constant_zero_pp, 2),
            "unwinnable": sorted(zero),
            "no_signal": sorted(allp),
            "per_task": {
                k: {
                    "suite": v["suite"],
                    "pass": v["pass"],
                    "n": v["n"],
                    "mean_partial": round(sum(v["partial"]) / len(v["partial"]), 4) if v["partial"] else 0.0,
                }
                for k, v in sorted(per.items())
            },
        }
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
