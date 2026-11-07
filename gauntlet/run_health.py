"""Is a finished run a measurement, or a transport failure wearing a score?

A gauntlet run that never reached the model still produces a number. The measured
case in this corpus: ``results/spark-x2.6-4b-q4ks-xhtoken-kvq4_20261029T040626Z.json``
— 79 of 79 attempts terminated ``error`` with **0 prompt tokens and 0 completion
tokens** (the endpoint refused or died), and the card published that as ``0.0%``.
Every retry answered the same way, so it is not one unlucky request; no request was
ever processed.

An endpoint that refuses connections measures the *endpoint*. A zero-token attempt
carries no evidence about the model's ability, so a run dominated by them must not
be published as a low score, and must not be silently re-used to source a card.

This module is the single definition of that condition. The runner stamps it into
``meta``; the publisher refuses to rank a card whose source log fails it.
"""

from __future__ import annotations

# A run with more than this share of zero-token errors did not measure the model.
# 0.5 is deliberately blunt: partial flakiness is a real (if noisy) measurement and
# stays rankable; "most of the suite never got an answer" is not.
TRANSPORT_FAILURE_SHARE = 0.5


def _attempts(results):
    for r in results or []:
        if not isinstance(r, dict):
            continue
        for a in r.get("attempts") or []:
            if isinstance(a, dict):
                yield a


def zero_token_error_counts(results) -> tuple[int, int]:
    """(zero-token errors, attempts) over a run's attempt records."""
    total = 0
    zero = 0
    for a in _attempts(results):
        total += 1
        if a.get("terminated") == "error" and not a.get("completion_tokens") and not a.get("prompt_tokens"):
            zero += 1
    return zero, total


def zero_token_error_share(results) -> float:
    zero, total = zero_token_error_counts(results)
    return (zero / total) if total else 0.0


def transport_failure(results, threshold: float = TRANSPORT_FAILURE_SHARE) -> tuple[bool, str]:
    """(is_transport_failure, human reason). Empty run = failure: it measured nothing."""
    zero, total = zero_token_error_counts(results)
    if total == 0:
        return True, "run recorded no attempts"
    share = zero / total
    if share > threshold:
        return True, (
            "%d of %d attempts returned no tokens at all (%.0f%%) — the model was never reached"
            % (zero, total, share * 100)
        )
    return False, ""
