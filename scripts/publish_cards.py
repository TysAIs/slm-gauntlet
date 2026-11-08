#!/usr/bin/env python3
"""Card JSON -> HTML -> verified PNG, for every configuration a sweep measured.

WHY THIS EXISTS
---------------
`scripts/cards_from_runs.py` writes `results/cards/card_<model>.json`; `scripts/make_cards.py`
renders HTML from a list of those dicts; `scripts/render_card_png.py` screenshots HTML to PNG.
Each piece worked, nothing joined them, so the publish step depended on someone hand-building
a combined JSON and naming the files: after the 0.5.0 sweep the README pointed at 35 card
images that did not exist (`leaderboard_check.py` refused to pass on exactly that drift).

This is that join. It publishes only cards whose own `details.methodology` matches the epoch
asked for, so a table for one epoch can never silently include another epoch's card.

USAGE
  python3 scripts/publish_cards.py                     # current methodology, all 0.5.0 cards
  python3 scripts/publish_cards.py --methodology 0.5.0 --models id1,id2
  python3 scripts/publish_cards.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gauntlet.methodology import METHODOLOGY_VERSION  # noqa: E402

CARDS = ROOT / "results" / "cards"


def collect(methodology: str, models: set[str] | None) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(CARDS / "card_*.json"))):
        try:
            data = json.load(open(f))
        except Exception:  # noqa: BLE001 - one unreadable card must not stop the publish
            continue
        for m in data if isinstance(data, list) else [data]:
            det = m.get("details") or {}
            if det.get("methodology") != methodology:
                continue
            if models and m.get("model") not in models:
                continue
            if m.get("overall_pct") is None:
                continue
            out.append(m)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methodology", default=METHODOLOGY_VERSION)
    ap.add_argument("--models", default="", help="comma-separated model ids (default: every card)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout-ms", type=int, default=15000)
    a = ap.parse_args(argv)

    models = {m.strip() for m in a.models.split(",") if m.strip()} or None
    cards = collect(a.methodology, models)
    if not cards:
        print(f"[publish_cards] no {a.methodology} cards found")
        return 1
    print(f"[publish_cards] {len(cards)} card(s) at methodology {a.methodology}")

    with tempfile.TemporaryDirectory() as td:
        combined = Path(td) / "cards.json"
        combined.write_text(json.dumps(cards, indent=1))
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_cards.py"), str(combined)],
                           cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode:
            print("[publish_cards] make_cards.py failed:\n" + (r.stderr or r.stdout)[-1500:])
            return 1

    htmls = [str(CARDS / f"card_{m['model']}.html") for m in cards]
    missing = [h for h in htmls if not Path(h).exists()]
    if missing:
        print("[publish_cards] HTML missing for %d card(s): %s" % (len(missing), missing[:3]))
        return 1
    if a.dry_run:
        print(f"[publish_cards] would render {len(htmls)} PNG(s)")
        return 0

    # playwright lives on the system interpreter on areo, not in the project venv
    render_py = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
    cmd = [render_py, str(ROOT / "scripts" / "render_card_png.py"), *htmls,
           "--outdir", "results/cards", "--prefix", "card_", "--timeout-ms", str(a.timeout_ms)]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print((r.stdout or "").strip().splitlines()[-1] if r.stdout else "")
    if r.returncode:
        print("[publish_cards] render failed:\n" + (r.stderr or r.stdout)[-1500:])
        return 1
    pngs = [CARDS / f"card_{m['model']}.png" for m in cards]
    bad = [str(p.relative_to(ROOT)) for p in pngs if not p.exists() or p.stat().st_size < 1024]
    if bad:
        print("[publish_cards] %d PNG(s) missing/too small: %s" % (len(bad), bad[:3]))
        return 1
    print(f"[publish_cards] {len(pngs)} verified card image(s) in results/cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
