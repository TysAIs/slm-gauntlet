"""CLI entrypoint: `gauntlet run`, `gauntlet perf`, `gauntlet report`."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from gauntlet.client import GauntletClient
from gauntlet.task import Task
from gauntlet.runner import run_suite, write_results
from gauntlet.report import aggregate_results

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"

SUITE_WEIGHTS = {"tooluse": 0.40, "structured": 0.20, "retrieval": 0.20, "coding": 0.10, "instruction": 0.10}


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
    tasks = load_tasks(args.suite.split(",") if args.suite != "all" else None)
    print(f"[gauntlet] {len(tasks)} tasks -> {args.endpoint} (model={args.model})")

    async def go():
        client = GauntletClient(base_url=args.endpoint, model=args.model, timeout=args.timeout)
        try:
            return await run_suite(client, tasks, concurrency=args.concurrency, seed=args.seed)
        finally:
            await client.close()

    results = asyncio.run(go())
    out = write_results(results, meta={"model": args.model, "endpoint": args.endpoint, "seed": args.seed}, outdir=Path("results"))
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
    run_p.add_argument("--concurrency", type=int, default=4)
    run_p.add_argument("--timeout", type=float, default=600.0)
    run_p.add_argument("--seed", type=int, default=0)
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
