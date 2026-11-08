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
  python_exec:    {type: python_exec, tests: "<python asserts>", timeout: 10}
                  -- takes the first ```python block (or the whole answer),
                     runs it in a subprocess together with `tests`, and passes
                     only if the process exits 0. Use for coding tasks: a
                     regex can match broken code, an execution cannot.

The JSON-Schema support is intentionally minimal (types, properties, required,
items, enum) — enough for the gauntlet's structured-output suite without a
jsonschema dependency.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreResult:
    passed: bool
    checks: list[dict] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    score: float = 1.0  # weighted partial-credit rubric score in [0, 1]
    gated: bool = False  # a must_pass assert failed and forced the score to 0

    def merge(self, other: ScoreResult) -> ScoreResult:
        return ScoreResult(
            passed=self.passed and other.passed,
            checks=self.checks + other.checks,
            failed=self.failed + other.failed,
            score=min(self.score, other.score),
            gated=self.gated or other.gated,
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
    `out` goes in GLOBALS so comprehension scopes (separate frames) can see it.

    `data` is also bound: the answer's first JSON value (fence-tolerant), or None
    when the answer is not JSON. Real-world tasks grade the parsed structure
    (which bucket an email went to), not whether a keyword appeared."""
    import json as _json
    # The builtin set must cover what a task author actually writes: a missing
    # `sorted` turns every model's answer into "predicate error" (hif_exact_bullets
    # scored 0% for 253 configurations for exactly that reason).
    safe_builtins = {
        "len": len, "abs": abs, "sum": sum, "round": round,
        "any": any, "all": all, "min": min, "max": max, "int": int, "float": float,
        "str": str, "json": _json, "sorted": sorted, "list": list, "dict": dict,
        "set": set, "tuple": tuple, "enumerate": enumerate, "zip": zip, "range": range,
        "bool": bool, "isinstance": isinstance, "reversed": reversed,
        # `re` so a task can parse amounts/ids out of prose instead of doing
        # brittle substring matching ("$59.00" vs "59.00" vs "USD 59.00").
        "re": re,
    }
    try:
        data = _json.loads(_strip_code_fence(output))
    except (ValueError, TypeError):
        data = None
    try:
        ok = bool(eval(expr, {"__builtins__": safe_builtins, "out": output, "data": data}))
    except Exception as e:  # noqa: BLE001 — task authors get the error message
        return ScoreResult(False, failed=[f"predicate error: {e}"])
    return ScoreResult(ok, checks=[{"check": "predicate", "ok": ok, "expr": expr}])


_CODE_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_python(output: str) -> str:
    """The first fenced python block, else the whole answer (a model may just
    paste code). Never invent code: an answer with no fence and no python-ish
    line yields the raw text, which usually SyntaxErrors — a real failure."""
    m = _CODE_FENCE.search(output)
    if m:
        return m.group(1)
    return output


def python_exec_check(output: str, tests: str, timeout: float = 10.0) -> ScoreResult:
    """Execution grading: run the model's code plus `tests` in a subprocess.

    A regex can be satisfied by a broken implementation ("def flatten" passes
    even if the function returns None); execution cannot. The subprocess is
    isolated (-I: no site/user site-packages, no PYTHONPATH), runs in a scratch
    cwd, and is killed at `timeout` — a model that ships an infinite loop fails
    the task instead of hanging the suite.
    """
    code = extract_python(output)
    if not code.strip():
        return ScoreResult(False, failed=["python_exec: no code in answer"])
    with tempfile.TemporaryDirectory(prefix="gauntlet-exec-") as td:
        path = os.path.join(td, "answer.py")
        with open(path, "w") as f:
            f.write(code)
            f.write("\n\n")
            f.write(tests)
            f.write("\n")
        try:
            r = subprocess.run(
                [sys.executable, "-I", path],
                cwd=td,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ScoreResult(False, failed=[f"python_exec: timeout after {timeout}s"])
    if r.returncode == 0:
        return ScoreResult(True, checks=[{"check": "python_exec", "ok": True}])
    tail = (r.stderr or r.stdout or "").strip().splitlines()
    detail = tail[-1][:300] if tail else f"exit {r.returncode}"
    return ScoreResult(False, failed=[f"python_exec failed: {detail}"])


def line_value_check(output: str, label: str, equals: float, tol: float = 0.005) -> ScoreResult:
    """The last number on the line that names `label` must equal `equals`.

    Measured on the 1070 Ti probe: a model answered
        OVERTIME: 6 * 33.00 = $198.00
    and a "first number after the label" regex read 6 — the grader called a correct
    answer wrong. A model may also answer "OVERTIME: $198" or "OVERTIME: 198.00",
    so the parse is: find the labelled line(s), take the LAST number on the last one
    (an answer is written at the end of its own sentence), and compare numerically.
    """
    lines = [
        ln for ln in output.splitlines()
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(label)}(?![A-Za-z0-9_])", ln, re.I)
    ]
    if not lines:
        return ScoreResult(False, checks=[{"check": "line_value", "ok": False, "label": label,
                                           "detail": "label not found"}],
                           failed=[f"line_value: no line names {label!r}"])
    nums = re.findall(r"-?[\d,]+\.?\d*", lines[-1])
    if not nums:
        return ScoreResult(False, checks=[{"check": "line_value", "ok": False, "label": label,
                                           "detail": "no number on the line"}],
                           failed=[f"line_value: no number on the {label!r} line"])
    try:
        got = float(nums[-1].replace(",", ""))
    except ValueError:
        return ScoreResult(False, failed=[f"line_value: unparsable number {nums[-1]!r}"])
    ok = abs(got - float(equals)) <= tol
    return ScoreResult(
        ok,
        checks=[{"check": "line_value", "ok": ok, "label": label, "got": got,
                 "expected": float(equals), "line": lines[-1].strip()[:200]}],
        failed=[] if ok else [f"line_value: {label} is {got}, expected {float(equals)}"],
    )


def line_sum_check(output: str, of: list[str], label: str, tol: float = 0.02) -> ScoreResult:
    """The number on the `label` line must equal the sum of the numbers on the `of`
    lines — the model's own figures.

    This grades internal consistency of an answer, which is what the "grand total"
    line of a quote is: a model whose per-order arithmetic is wrong but whose total
    adds up its own numbers has still done the total correctly. Measured on the
    0.5.1 probe: the strict "total equals 63.50" unit was passed by 0 of 43
    configurations (the same 3-component arithmetic nobody gets right), while the
    consistency version is passed by 32 of 43 — a real, discriminating sub-answer.
    """
    vals: list[float] = []
    for lab in of:
        lines = [
            ln for ln in output.splitlines()
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(lab)}(?![A-Za-z0-9_])", ln, re.I)
        ]
        if not lines:
            return ScoreResult(False, failed=[f"line_sum: no line names {lab!r}"])
        nums = re.findall(r"-?[\d,]+\.?\d*", lines[-1])
        if not nums:
            return ScoreResult(False, failed=[f"line_sum: no number on the {lab!r} line"])
        try:
            vals.append(float(nums[-1].replace(",", "")))
        except ValueError:
            return ScoreResult(False, failed=[f"line_sum: unparsable number {nums[-1]!r}"])
    target = line_value_check(output, label, sum(vals), tol=tol)
    target.checks = [{"check": "line_sum", "ok": target.passed, "label": label,
                      "parts": vals, "expected_sum": round(sum(vals), 4)}] + target.checks
    return target


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
            if kind == "line_value":
                r = line_value_check(output, a["label"], float(a["equals"]), float(a.get("tol", 0.005)))
            elif kind == "line_sum":
                r = line_sum_check(output, list(a["of"]), a["label"], float(a.get("tol", 0.02)))
            elif kind == "predicate":
                # predicates evaluate against the RAW output text — no JSON
                # extraction (code/loose text tasks would mis-parse)
                r = predicate_check(output, a["expr"])
            elif kind == "python_exec":
                r = python_exec_check(output, a["tests"], float(a.get("timeout", 10.0)))
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
                    # a pattern that cannot compile fails EVERY model silently;
                    # raise at score time so the run surfaces it as a task bug
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
        result.gated = must_pass_failed
        return result
