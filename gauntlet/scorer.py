"""Deterministic scoring engine.

Every scored task uses assertions evaluated here — no LLM judge in scored
paths. Supported assertion types (used in task YAML):

  exact_match:    {type: exact_match, value: "..."}          (case-sensitive)
  contains_all:   {type: contains_all, values: ["a","b"]}    (all substrings present)
  contains_any:   {type: contains_any, values: ["a","b"]}    (at least one present)
  regex:          {type: regex, pattern: "..."}              (re.search)
  json_schema:    {type: json_schema, schema: {...}}         (minimal JSON-Schema subset)
  predicate:      {type: predicate, expr: "<python bool expr on `out`>"}
                  -- expr is eval'd with `out` bound to parsed output;
                     only allowed if task YAML explicitly enables it.

The JSON-Schema support is intentionally minimal (types, properties, required,
items, enum) — enough for the gauntlet's structured-output suite without a
jsonschema dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreResult:
    passed: bool
    checks: list[dict] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    score: float = 1.0  # weighted partial-credit rubric score in [0, 1]

    def merge(self, other: ScoreResult) -> ScoreResult:
        return ScoreResult(
            passed=self.passed and other.passed,
            checks=self.checks + other.checks,
            failed=self.failed + other.failed,
            score=min(self.score, other.score),
        )


def _strip_code_fence(text: str) -> str:
    """Extract the first JSON-looking block, tolerating ```json fences."""
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    # fall back: first {...} or [...] block — whichever opener comes FIRST
    # (trying { before [ made "[{...}]" extract only the inner {...} and
    # broke array-schema checks)
    candidates = []
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start != -1:
            candidates.append((start, opener, closer))
    if candidates:
        start, opener, closer = min(candidates)
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"' and not in_str:
                in_str = True
            elif ch == '"' and in_str:
                in_str = False
            elif not in_str:
                if ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
    return text.strip()


def exact_match(output: str, expected: str) -> ScoreResult:
    ok = output.strip() == expected.strip()
    return ScoreResult(ok, checks=[{"check": "exact_match", "ok": ok}])


def contains_all(output: str, values: list[str]) -> ScoreResult:
    missing = [v for v in values if v not in output]
    ok = not missing
    return ScoreResult(ok, checks=[{"check": "contains_all", "ok": ok, "missing": missing}])


def contains_any(output: str, values: list[str]) -> ScoreResult:
    ok = any(v in output for v in values)
    return ScoreResult(ok, checks=[{"check": "contains_any", "ok": ok}])


def regex_check(output: str, pattern: str) -> ScoreResult:
    try:
        ok = re.search(pattern, output) is not None
    except re.error as e:
        return ScoreResult(False, failed=[f"bad regex {pattern!r}: {e}"])
    return ScoreResult(ok, checks=[{"check": "regex", "ok": ok, "pattern": pattern}])


def _validate_schema(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Minimal JSON-Schema subset validator. Returns list of errors."""
    errors: list[str] = []
    t = schema.get("type")
    type_map = {
        "object": dict, "array": list, "string": str,
        "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
    }
    if t and t in type_map:
        expected = type_map[t]
        # bool is subclass of int — exclude it from integer/number
        if t in ("integer", "number") and isinstance(value, bool):
            errors.append(f"{path}: expected {t}, got boolean")
        elif not isinstance(value, expected):
            errors.append(f"{path}: expected {t}, got {type(value).__name__}")
            return errors

    if isinstance(value, dict) and "properties" in schema:
        for key, sub in schema["properties"].items():
            if key in value:
                errors.extend(_validate_schema(value[key], sub, f"{path}.{key}"))
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required key {req!r}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(_validate_schema(item, schema["items"], f"{path}[{i}]"))
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
    return errors


def json_schema_check(output: str, schema: dict) -> ScoreResult:
    try:
        value = json.loads(_strip_code_fence(output))
    except ValueError as e:
        return ScoreResult(False, failed=[f"invalid JSON: {e}"])
    errors = _validate_schema(value, schema)
    ok = not errors
    return ScoreResult(ok, checks=[{"check": "json_schema", "ok": ok}], failed=errors)


def predicate_check(output: Any, expr: str) -> ScoreResult:
    """Evaluate a boolean expression with `out` bound. For trusted task YAML only.
    `out` goes in GLOBALS so comprehension scopes (separate frames) can see it."""
    import json as _json
    safe_builtins = {
        "len": len, "abs": abs, "sum": sum, "round": round,
        "any": any, "all": all, "min": min, "max": max, "int": int, "float": float,
        "str": str, "json": _json,
    }
    try:
        ok = bool(eval(expr, {"__builtins__": safe_builtins, "out": output}))
    except Exception as e:  # noqa: BLE001 — task authors get the error message
        return ScoreResult(False, failed=[f"predicate error: {e}"])
    return ScoreResult(ok, checks=[{"check": "predicate", "ok": ok, "expr": expr}])


class Scorer:
    """Runs a task's assertion list against model output.

    Scoring model (Vals-AI / Anthropic partial-credit pattern):
      - every assert carries a weight (default 1.0)
      - rubric score = earned weight / total weight
      - a must_pass assert failing forces the task score to 0
      - ScoreResult.passed remains the strict all-checks binary
    """

    def score(self, output: str, asserts: list[dict]) -> ScoreResult:
        if not asserts:
            raise ValueError("task has no asserts — refusing to score trivially")
        result = ScoreResult(True)
        earned = 0.0
        total = 0.0
        must_pass_failed = False
        # number-format-agnostic matching: contains/exact checks compare against
        # comma-stripped text (models format numbers inconsistently: 5,411,914)
        norm_output = output.replace(",", "")
        for a in asserts:
            a = dict(a)
            weight = float(a.pop("weight", 1.0))
            must_pass = bool(a.pop("must_pass", False))
            kind = a.pop("type")
            known = {
                "exact_match": exact_match,
                "contains_all": contains_all,
                "contains_any": contains_any,
                "regex": regex_check,
                "json_schema": json_schema_check,
            }
            if kind == "predicate":
                # predicates evaluate against the RAW output text — no JSON
                # extraction (code/loose text tasks would mis-parse)
                r = predicate_check(output, a["expr"])
            else:
                if kind not in known:
                    raise ValueError(f"unknown assert type: {kind}")
                fn = known[kind]
                if kind == "json_schema":
                    r = fn(output, a["schema"])
                elif kind in ("contains_all", "contains_any"):
                    vals = [v.replace(",", "") for v in a["values"]]
                    r = fn(norm_output, vals)
                elif kind == "exact_match":
                    r = fn(norm_output, a["value"].replace(",", ""))
                elif kind == "regex":
                    r = fn(output, a["pattern"])
                else:
                    raise ValueError(f"unknown assert type: {kind}")
            total += weight
            check_ok = r.passed
            if check_ok:
                earned += weight
            if must_pass and not check_ok:
                must_pass_failed = True
            merged = result.merge(r)
            # surface failed checks in `failed` (merge only ANDs booleans)
            merged.failed = result.failed + [
                f"{kind}: {json.dumps(c)}" for c in r.checks if not c.get("ok")
            ] + r.failed
            result = merged

        result.score = earned / total if total else 0.0
        if must_pass_failed:
            result.score = 0.0
        return result
