"""Measure what the published aggregate would be if it used the rubric instead of pass1.

docs/AUDIT-LOGIC-v0.5.md finding F1: `results/*.json` records a per-attempt rubric
score AND a binary pass flag, but every published aggregate is computed from the
binary `pass1`. This walks the corpus and prints, per run log, the weighted
aggregate both ways, plus the corpus-wide delta.

No model calls. Run from the repo root:

    .venv/bin/python scripts/audit_corpus_rubric_delta.py [--limit N]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gauntlet.methodology import SUITE_WEIGHTS  # noqa: E402


def aggregate(results, use_rubric=False):
    """Weighted suite aggregate over the suites present (as report.py does)."""
    by_suite = {}
    for r in results:
        attempts = r.get("attempts") or []
        if use_rubric:
            value = sum(a.get("score", 0.0) for a in attempts) / max(1, len(attempts))
        else:
            value = float(r.get("pass1", 0.0))
        by_suite.setdefault(r["suite"], []).append(value)
    active = {s: w for s, w in SUITE_WEIGHTS.items() if s in by_suite}
    if not active:
        return None
    return sum(sum(by_suite[s]) / len(by_suite[s]) * w for s, w in active.items()) / sum(active.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results", help="directory of run logs")
    ap.add_argument("--limit", type=int, default=6, help="worst rows to print")
    args = ap.parse_args()

    rows = []
    for path in sorted(glob.glob(os.path.join(args.results, "*.json"))):
        try:
            data = json.load(open(path))
        except (ValueError, OSError):
            continue
        results = data.get("results") or []
        if not results or not any("attempts" in r for r in results):
            continue
        binary = aggregate(results)
        rubric = aggregate(results, use_rubric=True)
        if binary is None or rubric is None:
            continue
        rows.append((data.get("meta", {}).get("model"), os.path.basename(path), binary, rubric, len(results)))

    if not rows:
        print("no run logs with per-attempt records under", args.results)
        return 1

    deltas = [(rubric - binary) * 100 for _, _, binary, rubric, _ in rows]
    print("logs compared:", len(rows))
    print(f"mean delta pp (rubric-binary): {statistics.mean(deltas):.2f}  "
          f"median {statistics.median(deltas):.2f}  max {max(deltas):.2f}")
    print(f"rows where rubric > binary: {sum(1 for d in deltas if d > 0.05)}/{len(deltas)}")
    rows.sort(key=lambda r: -(r[3] - r[2]))
    print("worst rows:")
    for model, path, binary, rubric, n in rows[: args.limit]:
        print(f"  {model:<34s} {path:<46s} binary {binary * 100:5.1f} "
              f"rubric {rubric * 100:5.1f} tasks {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
