#!/usr/bin/env python3
"""Print what models actually answered on the named tasks, from the 0.5.0 corpus.

Designing a scored unit needs the measured answer distribution, not a guess about
which sub-answer "should" be easy. Reads every complete 94-task run in
results/_published/discrimination_0.5.0.json and prints up to N answers per task.

  python3 scripts/inspect_task_answers.py rw_ticket_priority rw_room_conflicts --max 12
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mx = 12
    for a in sys.argv[1:]:
        if a.startswith("--max="):
            mx = int(a.split("=", 1)[1])
    disc = json.loads((ROOT / "results/_published/discrimination_0.5.0.json").read_text())
    runs = disc.get("runs") or []
    want = set(args)
    seen = {w: 0 for w in want}
    for rel in runs:
        p = ROOT / rel
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        model = d.get("model") or d.get("meta", {}).get("model")
        for t in d.get("results") or []:
            tid = t.get("task_id")
            if tid not in want or seen[tid] >= mx:
                continue
            for att in t.get("attempts") or []:
                if seen[tid] >= mx:
                    break
                txt = (att.get("final_text") or att.get("text") or att.get("output") or "")
                print(f"[{tid}] pass1={t.get('pass1')} score={att.get('score')} {model}: {txt[:400]}")
                seen[tid] += 1
            break
    for w in want:
        if not seen[w]:
            print(f"[{w}] NO ANSWERS FOUND")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
