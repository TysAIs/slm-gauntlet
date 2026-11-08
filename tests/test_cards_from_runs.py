"""A new measurement reaches the published corpus only through a card.

`scripts/cards_from_runs.py` turns a run log into `results/cards/card_<model>.json`.
These tests pin the two properties that make that safe to publish:

  * the label is READ, never invented -- quant and KV type come from the file the
    run actually served and the state row it ran under;
  * a run that did not cover the epoch's task count is REFUSED, so an aborted
    sweep cannot publish a full-looking score.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("cards_from_runs", ROOT / "scripts" / "cards_from_runs.py")
cardgen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cardgen)


def _run_log(tmp_path: Path, model: str, tasks: int, ts: str = "20261107T120000Z") -> tuple[Path, dict]:
    results = [
        {
            "task_id": f"t{i}",
            "suite": "tooluse",
            "repeats": 1,
            "pass1": 1.0 if i % 2 == 0 else 0.0,
            "pass_k": 0.0,
            "attempts": [{"rep": 0, "passed": bool(i % 2 == 0), "score": 1.0 if i % 2 == 0 else 0.0,
                          "failed": [], "terminated": "completed", "turns": 1, "tool_calls": 0,
                          "prompt_tokens": 10, "completion_tokens": 5, "final_text": "x",
                          "call_log": []}],
        }
        for i in range(tasks)
    ]
    payload = {"meta": {"model": model, "timestamp": ts, "methodology": "0.5.0",
                        "transport_failure": False, "zero_token_errors": 0,
                        "attempts": tasks}, "results": results}
    d = tmp_path / "results"
    d.mkdir(exist_ok=True)
    p = d / f"{model}_{ts}.json"
    p.write_text(json.dumps(payload))
    return p, payload


def test_label_is_read_from_the_run_not_guessed(tmp_path, monkeypatch):
    monkeypatch.setattr(cardgen, "ROOT", tmp_path)
    model = "nvidia-nemotron-3.5-bolt-e4b-ud-q4-k-xl-kvq8_0"
    _run_log(tmp_path, model, cardgen.CURRENT_TASK_COUNT)
    row = {"alias": model, "path": "/mnt/data/models/bolt-e4b-ud/NVIDIA-Nemotron-3.5-Bolt-E4B-UD-Q4_K_XL.gguf",
           "ctx": 32768, "ctk": "q8_0", "ctv": "q8_0", "gpu_pins_ok": True}
    card, why = cardgen.build_card(model, row, {}, cardgen.CURRENT_TASK_COUNT)
    assert why == "ok"
    d = card["details"]
    assert d["quant"] == "UD-Q4_K_XL"        # exactly the filename's spelling, not Q4_K_M
    assert d["kv_type"] == "q8_0"            # not "FP8": q8_0 KV is not FP8
    assert d["context_tokens"] == 32768
    assert d["gguf_file"].startswith("NVIDIA-Nemotron-3.5-Bolt-E4B-UD-Q4_K_XL")
    assert card["display_name"] == "Bolt E4B"          # one family, not a new spelling
    assert card["n"] == cardgen.CURRENT_TASK_COUNT
    assert 0.0 <= card["overall_pct"] <= 100.0


def test_partial_run_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(cardgen, "ROOT", tmp_path)
    model = "some-model-q4_k_m"
    _run_log(tmp_path, model, cardgen.CURRENT_TASK_COUNT - 1)
    card, why = cardgen.build_card(model, {"ctx": 32768, "ctk": "f16", "path": "x.gguf"},
                                   {}, cardgen.CURRENT_TASK_COUNT)
    assert card is None
    assert "no complete run log" in why


def test_newest_run_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(cardgen, "ROOT", tmp_path)
    model = "m-q4_k_m"
    _run_log(tmp_path, model, cardgen.CURRENT_TASK_COUNT, ts="20261101T000000Z")
    _run_log(tmp_path, model, cardgen.CURRENT_TASK_COUNT, ts="20261107T000000Z")
    found = cardgen.newest_run(model, cardgen.CURRENT_TASK_COUNT)
    assert found is not None
    assert "20261107T000000Z" in found[0].name


def test_mixed_kv_is_labelled_as_a_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(cardgen, "ROOT", tmp_path)
    model = "m2-q4_k_m"
    _run_log(tmp_path, model, cardgen.CURRENT_TASK_COUNT)
    card, _ = cardgen.build_card(model, {"ctx": 32768, "ctk": "f16", "ctv": "q8_0", "path": "x.gguf"},
                                 {}, cardgen.CURRENT_TASK_COUNT)
    assert card["details"]["kv_type"] == "FP16/q8_0"
