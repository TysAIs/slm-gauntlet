"""The published detail document must never rank two methodologies in one table.

These are regressions for defects that were live in `results/_published/LEADERBOARD.md`:

  * the document carried a hardcoded "71 tasks / 7 suites" header while it had started
    to receive 94-task (scorer 0.5.0) rows, so a reader ranked a 94-task row against a
    71-task row;
  * BEST-OF was computed over the whole corpus, so a pre-0.5.0 number (Spark-X2.6 4B
    90.2% at 71 tasks) headlined a document whose current top row is 86.6% at 94 tasks;
  * `fam_of` returned "other" for every model whose id contains a dot or a capital
    ("Qwen3.5-4B-Q4_K_M", "LFM2.5-2.6B-Q8_0"), which silently dropped two measured
    models into a junk section instead of their own family.

The generator is a standalone script (`gen-leaderboard.py`), so it is loaded by path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_leaderboard", ROOT / "gen-leaderboard.py")
gl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gl)


def test_family_grouping_handles_dots_and_case():
    assert gl.fam_of("qwen3.5-4b-q4_K_M") == "qwen3.5-4b"
    assert gl.fam_of("Qwen3.5-4B-Q4_K_M") == "qwen3.5-4b"
    assert gl.fam_of("lfm2.5-2.6b-q8_0") == "lfm2.5-2.6b"
    assert gl.fam_of("spark-x2.6-4b-iq3m-bartowski") == "spark-x2.6-4b"


def test_vendor_prefixed_cards_join_the_same_family():
    # 0.5.0 intake writes the vendor prefix carried by the GGUF; it is the same model.
    assert gl.fam_of("nvidia-nemotron-3.5-bolt-e4b-ud-iq3-xxs-kvf16") == "bolt-e4b"
    assert gl.fam_of("nemotron-3.5-bolt-e4b-q4-k-m-kvf16") == "bolt-e4b"


def test_row_method_is_derived_from_the_card_not_the_document():
    current = {"ts": "20261108T044913Z", "n": gl.FULL_TASKS}
    old = {"ts": "20261029T040626Z", "n": 71}
    cur_label = gl.method_label(current)
    old_label = gl.method_label(old)
    assert gl.epoch_of(current) == gl.CURRENT_EPOCH
    assert gl.epoch_of(old) != gl.CURRENT_EPOCH
    assert "current" in cur_label and str(gl.FULL_TASKS) in cur_label
    assert "current" not in old_label and "71 t" in old_label


def test_best_of_cannot_be_won_by_a_previous_epoch():
    """A 71-task 90.2% row must not beat a 94-task 86.6% row in BEST-OF."""
    cards = [
        {"model": "legacy-4b", "display_name": "Legacy", "ts": "20261029T040626Z", "n": 71,
         "overall_pct": 90.2, "details": {"quant": "Q4", "kv_type": "q8_0", "category": "on-GPU"}},
        {"model": "current-4b", "display_name": "Current", "ts": "20261108T044913Z",
         "n": gl.FULL_TASKS, "overall_pct": 86.6,
         "details": {"quant": "IQ3_XXS", "kv_type": "f16", "category": "on-GPU"}},
    ]
    ongpu = [m for m in cards if m["details"]["category"] != "offload"]
    cur = [m for m in ongpu if gl.epoch_of(m) == gl.CURRENT_EPOCH]
    assert max(cur or ongpu, key=lambda m: m["overall_pct"])["display_name"] == "Current"
