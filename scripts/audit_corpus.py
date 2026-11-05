#!/usr/bin/env python3
"""Corpus audit for the SLM Gauntlet (scorer/grader validity).

Reads every run log in results/ and reports, per task, whether the task
discriminates between models at all: a task every model passes measures
nothing, and a task no model passes is either very hard or broken (the
difference matters and is reported separately).

Usage:
  python3 scripts/audit_corpus.py [--out results/_published/audit_v0.4]

Outputs (under --out):
  audit.json   machine-readable per-task statistics
  AUDIT.md     human-readable findings, with the evidence for each flag
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

# A task is "informative" only if it has enough attempts to judge and it is
# neither pass-by-everyone nor fail-for-everyone.
MIN_CONFIGS = 8
CEILING_PASS = 0.95
FLOOR_PASS = 0.02


def load_runs() -> list[dict]:
    runs = []
    for path in sorted(RESULTS.glob("*.json")):
        if path.name.startswith("perf_"):
            continue
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict) or "results" not in data:
            continue
        data["_file"] = path.name
        runs.append(data)
    return runs


def normalize_fail(reason: str) -> str:
    """Collapse a failure string to its check family for clustering."""
    reason = re.sub(r"\s+", " ", reason.strip())
    if reason.startswith("state:"):
        return reason.split(":")[1] + ":state"
    m = re.match(r"^([a-z_]+):\s*(\{.*\})?$", reason)
    if m:
        kind = m.group(1)
        blob = m.group(2) or ""
        if "missing" in blob:
            return f"{kind}:missing_token"
        if kind == "json_schema":
            return "json_schema:invalid"
        if kind == "regex":
            return "regex:no_match"
        if kind == "exact_match":
            return "exact_match:no_match"
        return kind
    if reason.startswith("loop_terminated:"):
        return reason
    return reason[:60]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/_published/audit_v0.4")
    args = ap.parse_args()
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)

    runs = load_runs()
    per_task: dict[str, dict] = {}
    per_suite_attempts: Counter = Counter()
    models = set()

    for run in runs:
        model = run.get("meta", {}).get("model", "?")
        models.add(model)
        cfg_key = f"{model}|{run['_file']}"
        for tr in run.get("results", []):
            tid = tr.get("task_id", "?")
            rec = per_task.setdefault(
                tid,
                {
                    "suite": tr.get("suite", "?"),
                    "configs": set(),
                    "attempts": 0,
                    "passed": 0,
                    "terminations": Counter(),
                    "fail_families": Counter(),
                    "zero_score_attempts": 0,
                },
            )
            rec["configs"].add(cfg_key)
            for a in tr.get("attempts", []):
                rec["attempts"] += 1
                per_suite_attempts[rec["suite"]] += 1
                rec["terminations"][a.get("terminated", "?")] += 1
                if a.get("passed"):
                    rec["passed"] += 1
                if a.get("score", 0) == 0:
                    rec["zero_score_attempts"] += 1
                for f in a.get("failed", []) or []:
                    rec["fail_families"][normalize_fail(f)] += 1

    tasks = []
    for tid, rec in sorted(per_task.items()):
        n = rec["attempts"]
        rate = rec["passed"] / n if n else 0.0
        term = rec["terminations"]
        tasks.append(
            {
                "task_id": tid,
                "suite": rec["suite"],
                "configs": len(rec["configs"]),
                "attempts": n,
                "pass_rate": round(rate, 3),
                "terminations": dict(term),
                "noncompleted_rate": round(1 - term.get("completed", 0) / n, 3) if n else 0.0,
                "top_failures": dict(rec["fail_families"].most_common(4)),
            }
        )

    ceiling = [t for t in tasks if t["configs"] >= MIN_CONFIGS and t["pass_rate"] >= CEILING_PASS]
    floor = [t for t in tasks if t["configs"] >= MIN_CONFIGS and t["pass_rate"] <= FLOOR_PASS]
    thin = [t for t in tasks if t["configs"] < MIN_CONFIGS]

    suite_stats: dict[str, dict] = defaultdict(lambda: {"tasks": 0, "ceiling": 0, "floor": 0, "attempts": 0})
    for t in tasks:
        s = suite_stats[t["suite"]]
        s["tasks"] += 1
        s["attempts"] += t["attempts"]
        s["ceiling"] += t in ceiling
        s["floor"] += t in floor

    # discrimination: spread of task pass rates inside each suite
    payload = {
        "runs_scanned": len(runs),
        "models_seen": len(models),
        "tasks_scored": len(tasks),
        "attempts_total": sum(t["attempts"] for t in tasks),
        "thresholds": {"min_configs": MIN_CONFIGS, "ceiling": CEILING_PASS, "floor": FLOOR_PASS},
        "suites": {k: dict(v) for k, v in sorted(suite_stats.items())},
        "ceiling_tasks": ceiling,
        "floor_tasks": floor,
        "thin_tasks": thin,
        "tasks": tasks,
    }
    (outdir / "audit.json").write_text(json.dumps(payload, indent=2))

    lines = [
        "# Gauntlet corpus audit",
        "",
        f"Scanned **{len(runs)} run logs / {len(models)} model configurations / "
        f"{payload['attempts_total']} attempts / {len(tasks)} scored task ids**.",
        "",
        "A task that every configuration passes measures nothing; a task no "
        "configuration passes is either genuinely hard or broken. Both are listed "
        "below with the evidence, because the fix is different.",
        "",
        "## Per-suite",
        "",
        "| suite | tasks | attempts | ceiling (>=95% pass) | floor (<=2% pass) |",
        "|---|---|---|---|---|",
    ]
    for suite, s in sorted(suite_stats.items()):
        lines.append(f"| {suite} | {s['tasks']} | {s['attempts']} | {s['ceiling']} | {s['floor']} |")

    lines += ["", f"## Ceiling tasks (>= {CEILING_PASS:.0%} pass, >= {MIN_CONFIGS} configs)", ""]
    if ceiling:
        lines += ["| task | suite | configs | pass | top failures |", "|---|---|---|---|---|"]
        for t in ceiling:
            lines.append(
                f"| {t['task_id']} | {t['suite']} | {t['configs']} | {t['pass_rate']:.0%} | "
                f"{', '.join(list(t['top_failures'])[:2]) or '-'} |"
            )
    else:
        lines.append("_none_")

    lines += ["", f"## Floor tasks (<= {FLOOR_PASS:.0%} pass, >= {MIN_CONFIGS} configs)", ""]
    if floor:
        lines += ["| task | suite | configs | pass | terminations | top failures |", "|---|---|---|---|---|---|"]
        for t in floor:
            lines.append(
                f"| {t['task_id']} | {t['suite']} | {t['configs']} | {t['pass_rate']:.0%} | "
                f"{t['terminations']} | {', '.join(list(t['top_failures'])[:3]) or '-'} |"
            )
    else:
        lines.append("_none_")

    lines += ["", f"## Thin coverage (< {MIN_CONFIGS} configs — a score here is not yet a measurement)", ""]
    if thin:
        for t in thin:
            lines.append(f"- `{t['task_id']}` ({t['suite']}): {t['configs']} configs, {t['attempts']} attempts")
    else:
        lines.append("_none_")

    (outdir / "AUDIT.md").write_text("\n".join(lines) + "\n")
    print(f"[audit] {len(runs)} runs, {len(tasks)} tasks, {payload['attempts_total']} attempts")
    print(f"[audit] ceiling={len(ceiling)} floor={len(floor)} thin={len(thin)}")
    print(f"[audit] wrote {outdir/'audit.json'} and {outdir/'AUDIT.md'}")
    for t in floor[:15]:
        print("  FLOOR", t["task_id"], t["suite"], t["configs"], t["terminations"])
    for t in ceiling[:15]:
        print("  CEIL ", t["task_id"], t["suite"], t["configs"], t["pass_rate"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
