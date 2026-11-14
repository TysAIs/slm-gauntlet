"""Scoring Standard v1 guard: scoring is deterministic, period.

The standard (checkpoint pack §2) forbids an LLM judge anywhere in a scored
path. This test is the CI tripwire: it imports every scorer entry point and
statically scans the scoring modules — gauntlet/scorer, gauntlet/state_check
and every extra-suite bench module — for network or LLM-client imports. A
future change that wires a judge (or any network call) into scoring fails
here before it can move a published number.

Bench modules are scanned, not imported: they are CLI scripts that execute on
import (argparse at module level), and several legitimately call the MODEL
endpoint at run time — that is their job. What they must never import is an
LLM-judge client library. The core scorer/state_check modules get the strict
rule: no network imports at all.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Judge / hosted-LLM client libraries: banned in every scoring module.
LLM_CLIENT_ROOTS = {
    "openai", "anthropic", "cohere", "mistralai", "google.generativeai",
    "genai", "litellm", "langchain", "llama_index", "transformers",
    "vllm", "ollama",
}
# Network roots: banned in the core deterministic scorer (bench scripts talk
# to the model endpoint by design, so for them only the judge rule applies).
NETWORK_ROOTS = {
    "socket", "urllib", "requests", "httpx", "http", "aiohttp",
    "websocket", "websockets", "ftplib", "smtplib",
}


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
                roots.add(a.name)  # full dotted name for google.generativeai-style
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
            roots.add(node.module)
    return roots


def _bench_modules() -> list[Path]:
    out = []
    for p in sorted((ROOT / "extra-suites").rglob("*.py")):
        if "bench" in p.name:
            out.append(p)
    return out


def test_scorer_entry_points_importable():
    from gauntlet import scorer, state_check

    for name in (
        "Scorer", "ScoreResult", "exact_match", "contains_all", "contains_any",
        "regex_check", "json_schema_check", "predicate_check", "python_exec_check",
        "line_value_check", "line_sum_check", "needle_set_check",
        "entity_gate_check", "set_equal_check", "extract_entities",
    ):
        assert callable(getattr(scorer, name)), f"scorer entry point missing: {name}"
    assert callable(state_check.evaluate_state_asserts)
    importlib.import_module("gauntlet.taskgen.needle_haystack")


def test_core_scorer_has_no_network_or_llm_imports():
    for rel in ("gauntlet/scorer.py", "gauntlet/state_check.py"):
        roots = _import_roots(ROOT / rel)
        bad_net = sorted(roots & NETWORK_ROOTS)
        bad_llm = sorted(roots & LLM_CLIENT_ROOTS)
        assert not bad_net, f"{rel} gained network imports: {bad_net}"
        assert not bad_llm, f"{rel} gained LLM-client imports: {bad_llm}"


def test_bench_modules_have_no_llm_judge_imports():
    benches = _bench_modules()
    assert benches, "no bench modules found — guard would silently pass"
    for p in benches:
        roots = _import_roots(p)
        bad = sorted(roots & LLM_CLIENT_ROOTS)
        assert not bad, f"{p.relative_to(ROOT)} imports an LLM-judge client: {bad}"


def test_every_assert_type_has_a_scorer_path():
    """Every type in the task schema must be scorable — an unhandled type
    raises at score time and reads as a model failure in a real run."""
    from typing import get_args

    from gauntlet.scorer import Scorer
    from gauntlet.task import Assert

    sample_output = {
        "exact_match": ("x", {"value": "x"}),
        "contains_all": ("x y", {"values": ["x"]}),
        "contains_any": ("x", {"values": ["x", "z"]}),
        "regex": ("abc123", {"pattern": r"\d+"}),
        "json_schema": ('{"a": 1}', {"schema": {"type": "object"}}),
        "predicate": ("anything", {"expr": "len(out) > 0"}),
        "python_exec": ("def f():\n    return 1", {"tests": "assert f() == 1"}),
        "line_value": ("TOTAL: 5", {"label": "TOTAL", "equals": 5.0}),
        "line_sum": ("A: 2\nB: 3\nTOTAL: 5", {"of": ["A", "B"], "label": "TOTAL"}),
        "needle_set": ("ZEBRA-12345", {"value": "ZEBRA-12345"}),
        "entity_gate": ("Ada Lovelace ordered 3 widgets.",
                        {"source": "Ada Lovelace ordered 3 widgets for 45.50."}),
        "set_equal": ('["a", "b"]', {"values": ["a", "b"]}),
    }
    for t in get_args(Assert.model_fields["type"].annotation):
        if t == "state_predicate":
            # graded by the runner against the sandbox (Scorer.score refuses
            # it by design); its scorer path is state_predicate_check.
            from gauntlet.sandbox import ToolSandbox
            from gauntlet.scorer import state_predicate_check

            sb = ToolSandbox(seed=0)
            try:
                res = state_predicate_check(sb, "len(state) >= 0")
            finally:
                sb.cleanup()
            assert res.passed, "state_predicate did not score its own sample"
            continue
        assert t in sample_output, f"no sample output registered for assert type {t}"
        out, extra = sample_output[t]
        res = Scorer().score(out, [{"type": t, **extra}])
        assert res.passed, f"assert type {t} did not score its own sample output"
