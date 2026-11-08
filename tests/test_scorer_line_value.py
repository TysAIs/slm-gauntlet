"""line_value: the answer is the number the model claims, not the first operand.

Measured on the 1070 Ti probe (2026-11-08): asked for a payroll breakdown, a model
answered

    OVERTIME: 6 * 33.00 = $198.00

which is correct. The task's predicate read the first number after the label and
scored it 6, i.e. it failed a right answer. This assert type exists so that the
common "label: working = value" answer shape grades as the value.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gauntlet.scorer import Scorer, line_value_check  # noqa: E402

ASSERT = {"type": "line_value", "label": "OVERTIME", "equals": 198.00, "weight": 1.0}


def test_reads_the_final_number_when_the_model_shows_its_work():
    out = "REGULAR: 880.00\nOVERTIME: 6 * 33.00 = $198.00\nGROSS: $1078.00"
    r = line_value_check(out, "OVERTIME", 198.00)
    assert r.passed, r.failed


def test_reads_a_plain_dollar_amount():
    assert line_value_check("OVERTIME: $198", "OVERTIME", 198.00).passed
    assert line_value_check("OVERTIME: 1,980.00", "OVERTIME", 1980.00).passed


def test_wrong_value_fails():
    assert not line_value_check("OVERTIME: 795.00", "OVERTIME", 198.00).passed


def test_missing_label_fails_with_a_named_reason():
    r = line_value_check("gross pay was 1078", "OVERTIME", 198.00)
    assert not r.passed
    assert "no line names" in r.failed[0]


def test_label_must_be_a_whole_word():
    """`NET` must not match `NETWORK`, and `TAX` must not match `TAXABLE`."""
    assert not line_value_check("NETWORK: 847.80", "NET", 847.80).passed
    assert not line_value_check("TAXABLE: 145.20", "TAX", 145.20).passed


def test_uses_the_last_labelled_line():
    """A model that restates the answer in a summary line is graded on the summary."""
    out = "OVERTIME: 132.00\n... correction ...\nOVERTIME: 198.00"
    assert line_value_check(out, "OVERTIME", 198.00).passed


def test_scorer_dispatch_and_rubric_score():
    r = Scorer().score("OVERTIME: 6 * 33.00 = $198.00", [ASSERT])
    assert r.passed and r.score == 1.0
    bad = Scorer().score("OVERTIME: 795.00", [ASSERT])
    assert not bad.passed and bad.score == 0.0
