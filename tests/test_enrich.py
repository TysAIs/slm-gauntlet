"""Tests for runtime task enrichment (dynamic placeholders)."""

import random

from gauntlet.task import Assert, Task
from gauntlet.taskgen.enrich import build_flight_catalog, enrich_task


def _long_context_task() -> Task:
    return Task(
        id="t", suite="tooluse", description="d",
        prompt="Find FAI flight under 200:\n\n{FLIGHT_CATALOG}",
        asserts=[Assert(type="contains_any", values=["CONF"])],
    )


def test_enrich_fills_catalog():
    task = _long_context_task()
    enriched = enrich_task(task, seed=1)
    assert "{FLIGHT_CATALOG}" not in enriched.prompt
    assert "flight_id | carrier" in enriched.prompt


def test_enrich_deterministic_per_seed():
    task = _long_context_task()
    a = enrich_task(task, seed=42)
    b = enrich_task(task, seed=42)
    assert a.prompt == b.prompt
    c = enrich_task(task, seed=43)
    assert a.prompt != c.prompt


def test_catalog_has_target_and_traps():
    rng = random.Random(7)
    catalog = build_flight_catalog(rng)
    lines = catalog.splitlines()
    # target present: FAI under 200
    target_rows = [row for row in lines if row.startswith("FL_FAI_7 ")]
    assert len(target_rows) == 1
    assert "| FAI |" in target_rows[0]
    price = int(target_rows[0].split("|")[4].split(".")[0].strip())
    assert price < 200
    # near-miss FAI flights over 200
    near_miss = [row for row in lines if row.startswith("FL_FAI_M")]
    assert len(near_miss) == 4
    # traps: under 200 but wrong destination
    traps = [row for row in lines if row.startswith("FL_TRAP_")]
    assert len(traps) == 2
    assert all("| FAI |" not in row for row in traps)


def test_enrich_skips_static_tasks():
    task = Task(
        id="s", suite="tooluse", description="d",
        prompt="No placeholders here",
        asserts=[Assert(type="contains_any", values=["x"])],
    )
    assert enrich_task(task, seed=1).prompt == task.prompt
