"""CLI entrypoint: `gauntlet run`, `gauntlet perf`, `gauntlet report`."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from gauntlet.client import GauntletClient
from gauntlet.methodology import (
    METHODOLOGY_VERSION,
    NOLIMA_LADDER,
    RETRIEVAL_LADDER,
    SUITE_WEIGHTS,
    check_weights,
)
from gauntlet.report import aggregate_results
from gauntlet.runner import run_suite, write_results
from gauntlet.task import Task

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def validate_tasks(tasks: list[Task]) -> None:
    """Fail before the run, not in the results.

    A regex that cannot compile (e.g. `^(?i)(yes|no)$` — Python forbids a global
    inline flag that is not at the start) fails EVERY model and looks like a
    model weakness in the table. A python_exec assert with no tests does the
    same. Refuse to run such a suite.
    """
    import re as _re

    problems = []
    for t in tasks:
        for a in t.asserts:
            if a.type == "regex" and a.pattern:
                try:
                    _re.compile(a.pattern)
                except _re.error as e:
                    problems.append(f"{t.id}: bad regex {a.pattern!r}: {e}")
            if a.type == "python_exec" and not a.tests:
                problems.append(f"{t.id}: python_exec assert has no `tests`")
            if a.type == "predicate" and not a.expr:
                problems.append(f"{t.id}: predicate assert has no `expr`")
            if a.type in ("contains_all", "contains_any", "set_equal") and not a.values:
                problems.append(f"{t.id}: {a.type} assert has no `values`")
            if a.type == "needle_set" and not a.value:
                problems.append(f"{t.id}: needle_set assert has no `value`")
            if a.type == "entity_gate" and not a.source:
                problems.append(f"{t.id}: entity_gate assert has no `source`")
        if not t.asserts and not t.state_asserts:
            problems.append(f"{t.id}: no asserts")
        for sa in t.state_asserts:
            if sa.type == "file_lines" and not sa.lines:
                problems.append(f"{t.id}: file_lines assert has no `lines`")
            if sa.type in ("state_path", "file_content", "file_lines") and not sa.path:
                problems.append(f"{t.id}: {sa.type} assert has no `path`")
    if problems:
        raise SystemExit("[gauntlet] task validation failed:\n  " + "\n  ".join(problems))


def load_tasks(suites: list[str] | None = None, tasks_dir: Path | None = None) -> list[Task]:
    tasks: list[Task] = []
    tasks_dir = Path(tasks_dir) if tasks_dir else TASKS_DIR
    for path in sorted(tasks_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        for raw in data:
            t = Task(**raw)
            if suites is None or t.suite in suites:
                tasks.append(t)
    return tasks


def cmd_run(args: argparse.Namespace) -> int:
    check_weights()
    # Thermal preflight: the operator's 89C rule (1070 Ti is rated to 94C). Refuse to
    # start hot; a host without a readable sensor is a no-op, not a failure.
    from gauntlet.thermal import THERMAL_LIMIT_C, assert_thermal_ok

    limit = getattr(args, "thermal_limit", THERMAL_LIMIT_C)
    temp = assert_thermal_ok(limit)
    if temp is not None:
        print(f"[gauntlet] GPU {temp:.0f}C (ceiling {limit:.0f}C)")
    suites = args.suite.split(",") if args.suite != "all" else None
    tasks_dir = Path(args.tasks_dir) if getattr(args, "tasks_dir", None) else TASKS_DIR
    tasks = load_tasks(suites, tasks_dir)
    if args.repeats > 1:
        # pass^k reliability mode: every task runs k times, pass^k = all-reps rate
        for t in tasks:
            t.repeats = args.repeats

    # generated (contamination-resistant) tasks for retrieval
    from gauntlet.taskgen.needle_haystack import make_needle_task, make_refusal_task

    retrieval_wanted = (suites is None or "retrieval" in suites) and tasks_dir == TASKS_DIR
    if retrieval_wanted:
        gen: list[Task] = []
        for i, ctx in enumerate(RETRIEVAL_LADDER):
            gen.append(make_needle_task(f"gen_needle_{ctx//1000}k", ctx, seed=args.seed * 100 + i))
        for j, ctx in enumerate(NOLIMA_LADDER):
            gen.append(
                make_needle_task(f"gen_nolima_{ctx//1000}k", ctx, seed=args.seed * 100 + 50 + j, nolima=True)
            )
        gen.append(make_refusal_task("gen_refusal", seed=args.seed * 100 + 60))
        gen.append(make_needle_task("gen_needle_multi_8k", 8000, seed=args.seed * 100 + 70))
        tasks.extend(gen)

    validate_tasks(tasks)

    print(f"[gauntlet] {len(tasks)} tasks -> {args.endpoint} (model={args.model}, methodology {METHODOLOGY_VERSION})")

    from gauntlet.provenance import collect_provenance

    provenance_box: dict = {}

    async def go():
        client = GauntletClient(base_url=args.endpoint, model=args.model, timeout=args.timeout)
        try:
            provenance_box["data"] = await collect_provenance(
                client,
                gguf_path=getattr(args, "gguf", None),
                quant=getattr(args, "quant", None),
                kv_type=getattr(args, "kv_type", None),
                ctx=getattr(args, "ctx", None),
                np_=getattr(args, "slots", None),
                serve_flags=getattr(args, "serve_flags", None),
            )
            return await run_suite(client, tasks, concurrency=args.concurrency, seed=args.seed)
        finally:
            await client.close()

    results = asyncio.run(go())
    from gauntlet.run_health import transport_failure, zero_token_error_counts

    failed, why = transport_failure(results)
    zero, total = zero_token_error_counts(results)
    out = write_results(
        results,
        meta={
            "model": args.model,
            "endpoint": args.endpoint,
            "seed": args.seed,
            "methodology": METHODOLOGY_VERSION,
            "task_count": len(tasks),
            "context_ladder": list(RETRIEVAL_LADDER),
            "transport_failure": failed,
            "zero_token_errors": zero,
            "attempts": total,
            "provenance": provenance_box.get("data"),
        },
        outdir=Path("results"),
    )
    if failed:
        print(f"[gauntlet] WARNING transport failure: {why}")
        print("[gauntlet] this run is NOT a model score; check the endpoint and re-run")
    print(f"[gauntlet] results -> {out}")

    summary = aggregate_results(results, SUITE_WEIGHTS)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_perf(args: argparse.Namespace) -> int:
    from gauntlet.perf import run_perf_suite

    data = asyncio.run(run_perf_suite(args.endpoint, args.model))
    stamp_path = Path("results") / f"perf_{args.model.replace('/', '_')}.json"
    stamp_path.parent.mkdir(exist_ok=True)
    stamp_path.write_text(json.dumps(data, indent=2))
    print(f"[gauntlet] perf results -> {stamp_path}")
    print(json.dumps(data, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from gauntlet.report import generate_leaderboard

    table = generate_leaderboard(Path("results"))
    print(table)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gauntlet")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run quality suites against an endpoint")
    run_p.add_argument("--endpoint", required=True, help="OpenAI-compatible base URL, e.g. http://host:8080/v1")
    run_p.add_argument("--model", required=True)
    run_p.add_argument("--suite", default="all", help="comma-separated suites or 'all'")
    run_p.add_argument(
        "--tasks-dir",
        default=None,
        help="task YAML directory (default: tasks/); extra suites MUST live outside tasks/ "
        "so --suite all never mixes them in",
    )
    run_p.add_argument(
        "--concurrency", type=int, default=2,
        help="parallel tasks; keep low (1-2) for 8GB GPU endpoints",
    )
    run_p.add_argument("--timeout", type=float, default=600.0)
    run_p.add_argument("--seed", type=int, default=0)
    run_p.add_argument(
        "--thermal-limit",
        type=float,
        default=89.0,
        help="refuse to start at or above this GPU temperature in C (default 89, the operator's rule; 0 disables)",
    )
    run_p.add_argument(
        "--repeats", type=int, default=1,
        help="run every task k times; pass^k = all-reps reliability (tau-bench style). 3 recommended",
    )
    run_p.add_argument("--gguf", default=None,
                       help="path to the served GGUF (recorded in result provenance, sha256 hashed once)")
    run_p.add_argument("--quant", default=None, help="quant label, recorded in result provenance")
    run_p.add_argument("--kv-type", default=None, help="KV cache type, recorded in result provenance")
    run_p.add_argument("--ctx", type=int, default=None, help="serve context size, recorded in result provenance")
    run_p.add_argument("--slots", type=int, default=None, help="serve slot count (np), recorded in result provenance")
    run_p.add_argument("--serve-flags", default=None,
                       help="full serve command line / flags when known, recorded in result provenance")
    run_p.set_defaults(fn=cmd_run)

    perf_p = sub.add_parser("perf", help="throughput benchmark (TTFT/tok-s at c=1/4/8)")
    perf_p.add_argument("--endpoint", required=True)
    perf_p.add_argument("--model", required=True)
    perf_p.set_defaults(fn=cmd_perf)

    rep_p = sub.add_parser("report", help="generate leaderboard from results/")
    rep_p.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
