"""The published epoch must come from the card's own methodology, not the calendar.

Measured 2026-11-08: the last 0.5.0 sweep run finished that morning and the first 0.5.1
runs started the same afternoon. Epoch derivation by date made that one 0.5.0 card
"0.5.1 / current" and pushed the other 267 rows into legacy, i.e. bumping the
methodology emptied the ranked table without a single new run existing. A card carries
`details.methodology` (scripts/cards_from_runs.py writes it), so that is what decides.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lb():
    spec = importlib.util.spec_from_file_location(
        "leaderboard_check_epochs", ROOT / "scripts" / "leaderboard_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_card_methodology_wins_over_its_date():
    lb = _lb()
    # a 0.5.0 run that finished on the 0.5.1 release day
    assert lb.scorer_epoch("20261108", "0.5.0") == "0.5.0"
    assert lb.scorer_epoch("20261108", "0.5.1") == "0.5.1"


def test_unknown_or_missing_methodology_falls_back_to_the_date():
    lb = _lb()
    assert lb.scorer_epoch("20261108", None) == "0.5.1"
    assert lb.scorer_epoch("20261108", "not-a-methodology") == "0.5.1"
    assert lb.scorer_epoch("20260926", None) == "v0.3.1"


def test_an_epoch_with_no_cards_is_never_published():
    """Bumping METHODOLOGY_VERSION must not empty the table: the publisher picks the
    newest epoch that actually has rows."""
    lb = _lb()
    assert lb.newest_published_epoch({"v0.3.1", "0.5.0"}) == "0.5.0"
    assert lb.newest_published_epoch({"v0.3.1", "0.5.0", "0.5.1"}) == "0.5.1"
