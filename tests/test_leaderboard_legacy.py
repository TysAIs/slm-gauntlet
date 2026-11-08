"""The published table has to stay readable at an epoch boundary.

Bumping the methodology moves every older configuration out of the ranking at once
(0.5.0 moved 228 cards into the legacy bucket). Dumping one README row per legacy
configuration buried the live table, so the legacy section is collapsed: one row per
model, its best legacy configuration, and the number of configurations behind it.
Full provenance stays in `results/_published/leaderboard.json` and LEADERBOARD.md.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("leaderboard_check", ROOT / "scripts" / "leaderboard_check.py")
lb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lb)


def _legacy(display_name, config, published, epoch="0.3.1", model=None):
    return {
        "model": model or display_name.lower().replace(" ", "-"),
        "display_name": display_name,
        "config": config,
        "published": published,
        "epoch": epoch,
        "not_rankable_because": "scorer v0.3.1 (pre-0.5.0)",
    }


def test_legacy_section_is_one_row_per_model_not_per_configuration():
    legacy = [
        _legacy("Bolt E4B", "UD-Q4_K_XL · KV FP16", 89.1),
        _legacy("Bolt E4B", "UD-Q5_K_XL · KV q8_0", 88.6),
        _legacy("Bolt E4B", "UD-Q6_K_XL · KV q4_0", 86.9),
        _legacy("Dory 1.0 4B", "Q5_K_M · KV q8_0", 88.7),
    ]
    groups = lb.legacy_groups(legacy)
    assert len(groups) == 2
    bolt = [g for g in groups if g["display_name"] == "Bolt E4B"][0]
    # the best legacy configuration represents the model, and the count is the real count
    assert bolt["config"] == "UD-Q4_K_XL · KV FP16"
    assert bolt["published"] == 89.1
    assert bolt["variants"] == 3


def test_legacy_groups_keep_epochs_apart():
    legacy = [
        _legacy("Bolt E4B", "UD-Q4_K_XL", 89.1, epoch="0.3.1"),
        _legacy("Bolt E4B", "UD-Q8_K_XL", 84.0, epoch="0.4.0"),
    ]
    groups = lb.legacy_groups(legacy)
    assert len(groups) == 2
    assert {g["epoch"] for g in groups} == {"0.3.1", "0.4.0"}


def test_missing_score_never_wins_the_legacy_row():
    legacy = [
        _legacy("Gemma 4 E4B", "Q4_K_M", None),
        _legacy("Gemma 4 E4B", "IQ3_XXS", 68.8),
    ]
    groups = lb.legacy_groups(legacy)
    assert len(groups) == 1
    assert groups[0]["published"] == 68.8
    assert groups[0]["variants"] == 2


def test_rendered_block_has_no_per_configuration_legacy_rows():
    data = {
        "rows": [],
        "offload": [],
        "legacy": [_legacy("Bolt E4B", "config-%d" % i, 90 - i) for i in range(30)],
    }
    block = lb.render_block(data)
    legacy_lines = [ln for ln in block.splitlines() if ln.startswith("| Bolt E4B |")]
    assert len(legacy_lines) == 1
    assert "| 30 |" in legacy_lines[0]
