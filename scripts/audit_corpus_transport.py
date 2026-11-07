#!/usr/bin/env python3
"""How much of the published corpus is a dead endpoint wearing a score?

Usage:
    python3 scripts/audit_corpus_transport.py            # report, exit 1 if a card is affected
    python3 scripts/audit_corpus_transport.py --verbose  # every run log, including clean ones

Read-only. For every scored run log under results/, computes the share of attempts
that terminated `error` with zero prompt AND zero completion tokens (a request the
model never processed) and prints the runs above gauntlet.run_health's threshold,
followed by the published cards that were sourced from one.

This is the receipt behind audit finding F16: one card in the 2026-10 corpus was
published as 0.0% from 79/79 zero-token attempts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gauntlet.run_health import (  # noqa: E402
    TRANSPORT_FAILURE_SHARE,
    transport_failure,
    zero_token_error_counts,
)


def scan(results_dir: Path) -> list[dict]:
    out = []
    for p in sorted(results_dir.glob("*.json")):
        if p.name.startswith(("perf_", "cap_", "provenance_")):
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict) or not isinstance(d.get("results"), list):
            continue
        results = d["results"]
        if not results:
            continue
        failed, why = transport_failure(results)
        zero, total = zero_token_error_counts(results)
        out.append({
            "path": str(p.relative_to(ROOT)),
            "model": (d.get("meta") or {}).get("model", ""),
            "tasks": len(results),
            "attempts": total,
            "zero_token_errors": zero,
            "share": zero / total if total else 0.0,
            "transport_failure": failed,
            "why": why,
        })
    return out


def load_publisher():
    """The publisher's own card->log resolver, so this audit cannot disagree with it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "leaderboard_check_under_audit", ROOT / "scripts" / "leaderboard_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--cards", default=str(ROOT / "results" / "cards"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    runs = scan(Path(args.results))
    bad = [r for r in runs if r["transport_failure"]]
    print(
        "scanned %d scored run logs; %d are transport failures (share > %.0f%% zero-token attempts)"
        % (len(runs), len(bad), TRANSPORT_FAILURE_SHARE * 100)
    )
    for r in bad if not args.verbose else runs:
        flag = "FAIL" if r["transport_failure"] else "ok  "
        print("  %s %-78s n=%d attempts=%d zero=%d (%.0f%%)"
              % (flag, r["path"], r["tasks"], r["attempts"], r["zero_token_errors"], r["share"] * 100))
        if r["why"]:
            print("       %s" % r["why"])

    # The published surface is the card corpus. Resolve every card to the run log the
    # publisher would source it from, and report the ones that resolve to a dead run.
    lb = load_publisher()
    logs = lb.index_logs(Path(args.results))
    affected = []
    for card in lb.load_cards(Path(args.cards)):
        card_epoch = lb.scorer_epoch(card.get("ts", ""))
        weights = lb.EPOCHS[card_epoch]["weights"] if card_epoch in lb.EPOCHS else None
        src, _note = lb.pick_log(card, logs, weights)
        if not src:
            continue
        failed, why = (src.get("score") or {}).get("transport_failure", (False, ""))
        if failed:
            affected.append((card["file"], Path(src["path"]).name, card.get("overall_pct"), why))
    if not affected:
        print("\nno published card is sourced from a transport-failed run")
        return 0

    # A transport-failed card is only a DEFECT if it could still be ranked. The
    # publisher excludes it (classify() -> "transport failure"), which is what makes
    # the exclusion auditable rather than a deleted row nobody can explain.
    print("\npublished cards sourced from a transport-failed run:")
    still_ranked = 0
    for card, log, pct, why in affected:
        print("  %s  published=%s  <- %s" % (card, pct, log))
        print("       %s" % why)
    for card in lb.load_cards(Path(args.cards)):
        epoch = lb.scorer_epoch(card.get("ts", ""))
        weights = lb.EPOCHS[epoch]["weights"] if epoch in lb.EPOCHS else None
        src, _ = lb.pick_log(card, logs, weights)
        if not src:
            continue
        failed, _why = (src.get("score") or {}).get("transport_failure", (False, ""))
        if failed and lb.classify(card, src)[0]:
            still_ranked += 1
    if still_ranked:
        print("\nDEFECT: %d transport-failed card(s) would still be ranked" % still_ranked)
        return 1
    print("all transport-failed cards are excluded from the ranking (classify() refuses them)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
