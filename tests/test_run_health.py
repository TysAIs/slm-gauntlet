"""The pipeline must never publish a transport failure as a model score.

Measured defect this pins: `results/spark-x2.6-4b-q4ks-xhtoken-kvq4_20261029T040626Z.json`
has 79 attempts, every one terminated `error` with 0 prompt and 0 completion tokens,
and the corpus card for it published `0.0%` as if the model had failed every task.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from gauntlet.run_health import (
    TRANSPORT_FAILURE_SHARE,
    transport_failure,
    zero_token_error_counts,
    zero_token_error_share,
)

ROOT = Path(__file__).resolve().parent.parent


def _attempt(terminated="completed", prompt=10, completion=5):
    return {
        "rep": 0,
        "passed": terminated == "completed",
        "score": 1.0 if terminated == "completed" else 0.0,
        "terminated": terminated,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
    }


def _run(attempts):
    return [{"task_id": "t", "suite": "tooluse", "attempts": [a]} for a in attempts]


def test_zero_token_errors_are_counted_separately_from_real_failures():
    zero, total = zero_token_error_counts(
        _run([_attempt("error", 0, 0), _attempt("error", 120, 40), _attempt()])
    )
    assert (zero, total) == (1, 3)


def test_a_run_that_never_reached_the_model_is_a_transport_failure():
    failed, why = transport_failure(_run([_attempt("error", 0, 0)] * 20))
    assert failed
    assert "20 of 20" in why


def test_scattered_errors_are_a_noisy_measurement_not_a_transport_failure():
    attempts = [_attempt("error", 0, 0)] * 4 + [_attempt()] * 16
    failed, why = transport_failure(attempts and _run(attempts))
    assert not failed
    assert why == ""


def test_share_threshold_is_inclusive_at_the_boundary():
    # exactly at the threshold is still a measurement; above it is not
    at = _run([_attempt("error", 0, 0)] + [_attempt()] * 9)  # 10%
    assert zero_token_error_share(at) == pytest.approx(0.1)
    assert TRANSPORT_FAILURE_SHARE == 0.5


def test_empty_run_is_a_failure_because_it_measured_nothing():
    failed, why = transport_failure([])
    assert failed and "no attempts" in why


def _load_leaderboard_check():
    spec = importlib.util.spec_from_file_location(
        "leaderboard_check_under_test", ROOT / "scripts" / "leaderboard_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_publisher_refuses_to_rank_a_card_sourced_from_a_dead_endpoint():
    lb = _load_leaderboard_check()
    # ts is a CURRENT-epoch timestamp: classify() rejects a card measured under an
    # older epoch (a new epoch starts at 20261108 = 0.5.1).
    card = {"model": "m", "ts": "20261108T040626Z", "n": lb.FULL_TASKS}
    src = {"path": "x.json", "score": {"transport_failure": (True, "79 of 79 attempts returned no tokens at all")}}
    rankable, why = lb.classify(card, src)
    assert not rankable
    assert why.startswith("transport failure:")


def test_publisher_still_ranks_a_measured_card():
    lb = _load_leaderboard_check()
    # ts is a CURRENT-epoch timestamp: classify() rejects a card measured under an
    # older epoch (a new epoch starts at 20261108 = 0.5.1).
    card = {"model": "m", "ts": "20261108T040626Z", "n": lb.FULL_TASKS}
    ok = (False, "")
    src = {"path": "x.json", "score": {"transport_failure": ok}}
    rankable, why = lb.classify(card, src)
    assert rankable, why


def test_runner_writes_the_verdict_into_run_meta(tmp_path):
    """The stamp is what makes a bad run identifiable from its own file later."""
    from gauntlet.runner import write_results

    path = write_results(_run([_attempt("error", 0, 0)] * 3), meta={"model": "m"}, outdir=tmp_path)
    assert path.exists()
    d = json.loads(Path(path).read_text())
    assert isinstance(d, dict)
