"""Tests for taskgen: determinism under seed, needle placement, no-lexical-overlap."""

from gauntlet.taskgen.needle_haystack import NOLIMA_PAIRS, make_needle_task, make_refusal_task


def test_deterministic_under_seed():
    a = make_needle_task("n1", 4000, seed=42)
    b = make_needle_task("n1", 4000, seed=42)
    assert a.prompt == b.prompt
    assert a.canary == b.canary


def test_different_seeds_differ():
    a = make_needle_task("n1", 4000, seed=42)
    b = make_needle_task("n1", 4000, seed=43)
    assert a.prompt != b.prompt
    assert a.canary != b.canary


def test_needle_present_and_scorable():
    task = make_needle_task("n1", 4000, seed=7)
    code = task.asserts[0].values[0]
    assert code in task.prompt  # needle planted
    assert code.startswith("ZEBRA-")


def test_context_scales_with_target():
    small = make_needle_task("n1", 2000, seed=1)
    big = make_needle_task("n2", 32000, seed=1)
    assert len(big.prompt.split()) > len(small.prompt.split()) * 5


def test_nolima_no_lexical_overlap():
    # spot-check several pairs: needle content words absent from question
    for needle, question, _expected in NOLIMA_PAIRS:
        needle_words = set(w.lower().strip(".,'") for w in needle.split() if len(w) > 4)
        q_words = set(w.lower().strip(".,'?") for w in question.split())
        # allow at most 1 accidental shared word (stopword-ish)
        overlap = needle_words & q_words
        assert len(overlap) <= 1, f"lexical overlap in pair: {overlap} — {needle!r} / {question!r}"


def test_refusal_task_has_no_code():
    task = make_refusal_task("r1", seed=11)
    assert "ZEBRA-" not in task.prompt
    assert task.asserts[0].values == ["NOT_FOUND"]


def test_canary_embedded():
    task = make_needle_task("n1", 1000, seed=3)
    assert task.canary and task.canary.startswith("gauntlet-canary-")
