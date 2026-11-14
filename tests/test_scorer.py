"""Tests for the deterministic scorer."""


from gauntlet.scorer import (
    Scorer,
    ScoreResult,
    contains_all,
    exact_match,
    json_schema_check,
    predicate_check,
    regex_check,
)
from gauntlet.task import Assert as TaskAssert
from gauntlet.task import Task as TaskModel


def test_exact_match():
    assert exact_match("hello world", "hello world").passed
    assert not exact_match("hello world", "Hello World").passed


def test_contains_all():
    r = contains_all("the cat sat on the mat", ["cat", "mat"])
    assert r.passed
    r2 = contains_all("no animals here", ["cat", "mat"])
    assert not r2.passed
    assert "cat" in str(r2.checks)


def test_regex_check():
    r = regex_check("Order #12345 shipped", r"Order #\d+ shipped")
    assert r.passed
    r2 = regex_check("Order abc shipped", r"Order #\d+ shipped")
    assert not r2.passed


def test_json_schema_valid():
    schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}, "temp": {"type": "number"}},
        "required": ["city", "temp"],
    }
    r = json_schema_check('{"city": "Paris", "temp": 21.5}', schema)
    assert r.passed
    r2 = json_schema_check('{"city": 42, "temp": 21.5}', schema)
    assert not r2.passed
    r3 = json_schema_check("not json at all", schema)
    assert not r3.passed


def test_json_schema_extracts_from_markdown_fence():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
    r = json_schema_check('```json\n{"a": 1}\n```', schema)
    assert r.passed


def test_predicate_check():
    r = predicate_check({"x": 5}, "out.get('x') == 5")
    assert r.passed


def test_predicate_via_to_assert_dicts():
    """Round-trip: Task Assert expr must survive to_assert_dicts -> Scorer."""
    from gauntlet.task import Task as TaskModel

    a = TaskAssert(type="predicate", expr="len(out.split()) <= 30")
    dicts = TaskModel(
        id="x", suite="instruction", description="d", prompt="p",
        asserts=[a],
    ).to_assert_dicts()
    r = Scorer().score("one two three", dicts)
    assert r.score == 1.0
    r2 = Scorer().score(" ".join(["word"] * 40), dicts)
    assert r2.score == 0.0


def test_partial_credit_comma_normalized():
    """Numbers formatted with commas must still match (format-agnostic scoring)."""
    r = Scorer().score("The result is 5,411,914 exactly.", [
        {"type": "contains_all", "values": ["5411914"], "must_pass": True},
    ])
    assert r.score == 1.0


def test_regex_check_stays_raw():
    """Regex/predicate checks see raw output (comma-sensitive IF tests)."""
    r = Scorer().score("a, b, c", [
        {"type": "regex", "pattern": "^((?!,).)*$"},  # must fail: commas present
    ])
    assert not r.passed


def test_scorer_runs_assert_list():
    scorer = Scorer()
    task_asserts = [
        {"type": "contains_all", "values": ["refund"]},
        {"type": "regex", "pattern": r"ID-\d{4}"},
    ]
    result = scorer.score("Your refund ID-1234 is processed", task_asserts)
    assert result.passed
    assert len(result.checks) == 2

    result2 = scorer.score("no useful info", task_asserts)
    assert not result2.passed
    assert len(result2.failed) == 2


# --- json_schema keyword coverage (P3: additionalProperties/pattern/min/max/minItems) ---

def test_json_schema_additional_properties():
    schema = {"type": "object",
              "properties": {"a": {"type": "integer"}},
              "required": ["a"], "additionalProperties": False}
    assert json_schema_check('{"a": 1}', schema).passed
    assert not json_schema_check('{"a": 1, "b": 2}', schema).passed


def test_json_schema_pattern():
    schema = {"type": "object",
              "properties": {"id": {"type": "string", "pattern": "^V[0-9]{3}$"}},
              "required": ["id"]}
    assert json_schema_check('{"id": "V123"}', schema).passed
    assert not json_schema_check('{"id": "X123"}', schema).passed


def test_json_schema_minimum_maximum():
    schema = {"type": "object",
              "properties": {"kg": {"type": "integer", "minimum": 50, "maximum": 5000}},
              "required": ["kg"]}
    assert json_schema_check('{"kg": 1200}', schema).passed
    assert not json_schema_check('{"kg": 10}', schema).passed
    assert not json_schema_check('{"kg": 9000}', schema).passed


def test_json_schema_min_items():
    schema = {"type": "array", "minItems": 3, "items": {"type": "string"}}
    assert json_schema_check('["a", "b", "c"]', schema).passed
    assert not json_schema_check('["a"]', schema).passed


# --- new assert types: needle_set / entity_gate / set_equal ---

def test_needle_set_equality():
    from gauntlet.scorer import needle_set_check
    assert needle_set_check("The code is ZEBRA-12345.", "ZEBRA-12345").passed
    # naming a decoy alongside the secret fails (substring scoring passed this)
    assert not needle_set_check("ZEBRA-12345 and ZEBRA-99999", "ZEBRA-12345").passed
    assert not needle_set_check("ZEBRA-99999", "ZEBRA-12345").passed
    assert not needle_set_check("no code here", "ZEBRA-12345").passed
    # via the full Scorer dispatch + Task schema round-trip
    a = TaskAssert(type="needle_set", value="ZEBRA-12345")
    dicts = TaskModel(id="x", suite="retrieval", description="d", prompt="p",
                      asserts=[a]).to_assert_dicts()
    assert Scorer().score("ZEBRA-12345", dicts).passed
    assert not Scorer().score("ZEBRA-12345 ZEBRA-99999", dicts).passed


def test_entity_gate():
    from gauntlet.scorer import entity_gate_check
    src = "Ada Lovelace ordered 3 widgets for 45.50 on 2026-01-15."
    assert entity_gate_check("Ada Lovelace ordered 3 widgets.", src).passed
    assert not entity_gate_check("Ada Lovelace ordered 9 widgets.", src).passed
    assert not entity_gate_check("Ada Lovelace paid on 2026-02-01.", src).passed
    a = TaskAssert(type="entity_gate", source=src)
    dicts = TaskModel(id="x", suite="structured", description="d", prompt="p",
                      asserts=[a]).to_assert_dicts()
    assert Scorer().score("Ada Lovelace ordered 3 widgets.", dicts).passed


def test_set_equal():
    from gauntlet.scorer import set_equal_check
    assert set_equal_check('["billing", "spam"]', ["spam", "billing"]).passed
    assert set_equal_check("spam, billing", ["spam", "billing"]).passed
    assert set_equal_check("spam\nbilling", ["spam", "billing"]).passed
    assert not set_equal_check('["spam"]', ["spam", "billing"]).passed
    assert not set_equal_check('["spam", "billing", "urgent"]', ["spam", "billing"]).passed
    a = TaskAssert(type="set_equal", values=["spam", "billing"])
    dicts = TaskModel(id="x", suite="structured", description="d", prompt="p",
                      asserts=[a]).to_assert_dicts()
    assert Scorer().score('["billing", "spam"]', dicts).passed


def test_score_result_merge():
    a = ScoreResult(True, [], [])
    b = ScoreResult(False, [], ["x"])
    merged = a.merge(b)
    assert not merged.passed
    assert merged.failed == ["x"]
