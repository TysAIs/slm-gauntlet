"""Aggregation + leaderboard table generation from results/ JSONs."""

from __future__ import annotations

import json
from pathlib import Path

from gauntlet.methodology import METHODOLOGY_VERSION, SUITE_WEIGHTS

# The published aggregate is the one the runner prints. Do not invent a second
# weighting here: report.py used to carry its own (tooluse .40) and it silently
# disagreed with `gauntlet run`.
DEFAULT_WEIGHTS = SUITE_WEIGHTS


def aggregate_results(results: list[dict], weights: dict | None = None) -> dict:
    weights = weights or DEFAULT_WEIGHTS
    by_suite: dict[str, list[dict]] = {}
    for r in results:
        by_suite.setdefault(r["suite"], []).append(r)

    suite_scores = {}
    for suite, items in by_suite.items():
        pass1 = sum(i["pass1"] for i in items) / len(items)
        pass_k = sum(i["pass_k"] for i in items) / len(items)
        suite_scores[suite] = {"pass1": round(pass1, 3), "pass_k": round(pass_k, 3), "tasks": len(items)}

    # capability score only over suites present in this run (weights renormalized)
    active = {s: w for s, w in weights.items() if s in suite_scores}
    total_w = sum(active.values()) or 1.0
    score = sum(suite_scores[s]["pass1"] * w for s, w in active.items()) / total_w

    # loop/timeout failure modes
    fail_modes: dict[str, int] = {}
    for r in results:
        for a in r["attempts"]:
            if a["terminated"] != "completed":
                fail_modes[a["terminated"]] = fail_modes.get(a["terminated"], 0) + 1

    profile = classify_profile(suite_scores)
    # Coverage: a run over a subset of the methodology's suites renormalizes the
    # weights, so 2 tasks can print a perfect 1.000. Say so in the summary
    # instead of letting the headline imply full-suite coverage.
    covered = sorted(suite_scores)
    missing = sorted(s for s in weights if s not in suite_scores)
    total_tasks = sum(v["tasks"] for v in suite_scores.values())
    return {
        "subagent_capability_score": round(score, 3),
        "profile": profile,
        "suites": suite_scores,
        "failure_modes": fail_modes,
        "coverage": {
            "tasks": total_tasks,
            "suites": covered,
            "missing_suites": missing,
            "partial": bool(missing),
        },
    }


def classify_profile(suite_scores: dict) -> str:
    """Coarse model classification from per-suite deltas."""
    s = {k: v["pass1"] for k, v in suite_scores.items()}
    tool = s.get("tooluse", 0)
    code = s.get("coding", 0)
    gen = (s.get("structured", 0) + s.get("instruction", 0) + s.get("retrieval", 0)) / 3
    if tool >= 0.6 and code >= 0.6 and gen >= 0.6:
        return "generalist"
    if tool >= 0.6 and gen < 0.6:
        return "subagent-specialist"
    if code >= 0.6 and gen < 0.5:
        return "coding-specialist"
    if max(s.values(), default=0) < 0.3:
        return "weak-general"
    return "generalist-lite"


def generate_leaderboard(results_dir: Path) -> str:
    """Scan results/*.json (skip perf_*), build a markdown leaderboard table."""
    rows = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name.startswith("perf_"):
            continue
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        meta = data.get("meta", {})
        results = data.get("results", [])
        summary = aggregate_results(results)
        rows.append((meta.get("model", "?"), summary))

    rows.sort(key=lambda x: x[1]["subagent_capability_score"], reverse=True)
    # The weight sentence is GENERATED from the one methodology table. It used to
    # be a hand-written string and it went stale the moment weights changed.
    weight_note = ", ".join(f"{k} {v:.2f}" for k, v in SUITE_WEIGHTS.items())
    cell_keys = tuple(SUITE_WEIGHTS)
    lines = [
        "# SLM Gauntlet Leaderboard",
        "",
        f"Methodology {METHODOLOGY_VERSION}: Subagent Capability Score = weighted pass@1 ({weight_note}).",
        "",
        "| Model | Score | Profile | " + " | ".join(cell_keys) + " | loops |",
        "|---" * (len(cell_keys) + 3) + "|",
    ]
    for model, s in rows:
        st = s["suites"]
        cells = [st.get(k, {}).get("pass1", "-") for k in cell_keys]
        loops = s["failure_modes"].get("looped", 0) + s["failure_modes"].get("max_turns", 0)
        lines.append(
            f"| {model} | {s['subagent_capability_score']} | {s['profile']} | "
            + " | ".join(str(c) for c in cells)
            + f" | {loops} |"
        )
    return "\n".join(lines)
