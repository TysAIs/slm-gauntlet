#!/usr/bin/env python3
"""Answer-frequency table per task across the 0.5.0 corpus (all 33 complete runs).

Used to pick scored units that at least one measured configuration can win, and
that not every configuration wins.

  python3 scripts/answer_frequencies.py rw_ticket_priority --top 20
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    args = [a.lstrip("-").split("=", 1) for a in sys.argv[1:]]
    want, top = [], 15
    flags = dict(a for a in args if len(a) == 2)
    top = int(flags.get("top", 15))
    want = [a[0] for a in args if len(a) == 1]
    disc = json.loads((ROOT / "results/_published/discrimination_0.5.0.json").read_text())
    counts = {w: Counter() for w in want}
    n = Counter()
    for rel in disc.get("runs") or []:
        p = ROOT / rel
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        for t in d.get("results") or []:
            tid = t.get("task_id")
            if tid not in counts:
                continue
            for att in (t.get("attempts") or [])[:1]:
                txt = (att.get("final_text") or "").strip()
                counts[tid][txt[:300]] += 1
                n[tid] += 1
    for tid in want:
        print(f"=== {tid}  ({n[tid]} runs)")
        for txt, c in counts[tid].most_common(top):
            print(f"  {c:3d}  {txt!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
