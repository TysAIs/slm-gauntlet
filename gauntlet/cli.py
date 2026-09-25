"""CLI entrypoint: `gauntlet run`, `gauntlet perf`, `gauntlet report`."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from gauntlet.client import GauntletClient
from gauntlet.report import aggregate_results
from gauntlet.runner import run_suite, write_results
from gauntlet.task import Task

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"

SUITE_WEIGHTS = {
    "tooluse": 0.30,
    "structured": 0.15,
    "retrieval": 0.15,
    "coding": 0.10,
    "instruction": 0.10,
    "adversarial": 0.10,
    "agent_chains": 0.10,
}


def load_tasks(suites: list[str] | None = None) -> list[Task]:
    tasks: list[Task] = []
    for path in sorted(TASKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        for raw in data:
            t = Task(**raw)
            if suites is None or t.suite in suites:
                tasks.append(t)
    return tasks


def cmd_run(args: argparse.Namespace) -> int:
    suites = args.suite.split(",") if args.suite != "all" else None
    tasks = load_tasks(suites)
    if args.repeats > 1:
        # pass^k reliability mode: every task runs k times, pass^k = all-reps rate
        for t in tasks:
            t.repeats = args.repeats

    # generated (contamination-resistant) tasks for retrieval
    from gauntlet.taskgen.needle_haystack import make_needle_task, make_refusal_task

    retrieval_wanted = suites is None or "retrieval" in suites
    if retrieval_wanted:
        gen: list[Task] = []
        for i, ctx in enumerate((4000, 8000, 16000, 32000)):
            gen.append(make_needle_task(f"gen_needle_{ctx//1000}k", ctx, seed=args.seed * 100 + i))
        gen.append(make_needle_task("gen_nolima_8k", 8000, seed=args.seed * 100 + 50, nolima=True))
        gen.append(make_needle_task("gen_nolima_16k", 16000, seed=args.seed * 100 + 51, nolima=True))
        gen.append(make_refusal_task("gen_refusal", seed=args.seed * 100 + 60))
        gen.append(make_needle_task("gen_needle_multi_4k", 4000, seed=args.seed * 100 + 70))
        tasks.extend(gen)

    print(f"[gauntlet] {len(tasks)} tasks -> {args.endpoint} (model={args.model})")

    async def go():
        client = GauntletClient(base_url=args.endpoint, model=args.model, timeout=args.timeout)
        try:
            return await run_suite(client, tasks, concurrency=args.concurrency, seed=args.seed)
        finally:
            await client.close()

    results = asyncio.run(go())
    out = write_results(
        results,
        meta={"model": args.model, "endpoint": args.endpoint, "seed": args.seed},
        outdir=Path("results"),
    )
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


def cmd_pagoda(args: argparse.Namespace) -> int:
    import asyncio

    from gauntlet.pagoda_cli import run as pagoda_run

    data = asyncio.run(pagoda_run(args.endpoint, args.model, args.max_tokens, args.out))
    out = args.out or f"results/pagoda_{args.model.replace('/', '_')}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"model": args.model, "score": data.as_dict(), "output": ""}, indent=1))
    print(f"[gauntlet] pagoda results -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gauntlet")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run quality suites against an endpoint")
    run_p.add_argument("--endpoint", required=True, help="OpenAI-compatible base URL, e.g. http://host:8080/v1")
    run_p.add_argument("--model", required=True)
    run_p.add_argument("--suite", default="all", help="comma-separated suites or 'all'")
    run_p.add_argument(
        "--concurrency", type=int, default=2,
        help="parallel tasks; keep low (1-2) for 8GB GPU endpoints",
    )
    run_p.add_argument("--timeout", type=float, default=600.0)
    run_p.add_argument("--seed", type=int, default=0)
    run_p.add_argument(
        "--repeats", type=int, default=1,
        help="run every task k times; pass^k = all-reps reliability (tau-bench style). 3 recommended",
    )
    # add pagoda subcommand
    pag_p = sub.add_parser("pagoda", help="run the Pagoda creative-build benchmark")
    pag_p.add_argument("--endpoint", required=True)
    pag_p.add_argument("--model", required=True)
    pag_p.add_argument("--max-tokens", type=int, default=1500)
    pag_p.add_argument("--out", default=None)
    pag_p.set_defaults(fn=cmd_pagoda)
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
