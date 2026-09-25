"""Runtime task enrichment: fills dynamic placeholders before execution.

tool_hard_long_context_reservation carries a {FLIGHT_CATALOG} placeholder;
this module builds a fresh seeded catalog per run (40+ rows, one target that
matches the constraints, distractors priced/destined to tempt wrong picks).
"""

from __future__ import annotations

import random

from gauntlet.task import Task

DESTINATIONS = ["JFK", "LAX", "ORD", "DFW", "DEN", "SEA", "SFO", "MIA", "PHX", "IAH",
                "BOS", "ATL", "MSP", "DTW", "PHL", "LGA", "SLC", "SAN", "TPA", "PDX"]
CARRIERS = ["Skyway", "PacificJet", "AirMetro", "TransCondor", "NimbusAir", "RedTail"]


def build_flight_catalog(rng: random.Random, target_id: str = "FL_FAI_7") -> str:
    """Generate a flight catalog text block with one target matching:
    destination FAI, price < 200. Everything else is a distractor."""
    lines = ["FLIGHT CATALOG", "flight_id | carrier | origin | destination | price_usd | seats_left"]
    used_ids = set()
    # 4 near-miss FAI flights: right destination, over budget (200-399)
    for i, price in enumerate((249, 299, 339, 389)):
        lines.append(f"FL_FAI_M{i} | {rng.choice(CARRIERS)} | JFK | FAI | {price}.00 | {rng.randint(1, 9)}")
        used_ids.add(f"FL_FAI_M{i}")
    # 2 traps: under 200 but WRONG destination
    for i in range(2):
        d = rng.choice([d for d in DESTINATIONS if d != "FAI"])
        fid = f"FL_TRAP_{i}"
        lines.append(f"{fid} | {rng.choice(CARRIERS)} | JFK | {d} | {rng.randint(120, 190)}.50 | {rng.randint(1, 9)}")
        used_ids.add(fid)
    # 60 filler flights (long-context resilience needs real volume at 8K+ tokens)
    for _ in range(60):
        while True:
            fid = f"FL{rng.randint(1000, 9999)}"
            if fid not in used_ids:
                break
        used_ids.add(fid)
        o, d = rng.sample(DESTINATIONS, 2)
        price = rng.randint(85, 890)
        lines.append(f"{fid} | {rng.choice(CARRIERS)} | {o} | {d} | {price}.00 | {rng.randint(0, 9)}")
    # target: cheapest FAI flight, under 200, placed at random position
    target_row = f"{target_id} | {rng.choice(CARRIERS)} | JFK | FAI | {rng.randint(140, 189)}.00 | {rng.randint(1, 9)}"
    pos = rng.randint(6, len(lines))
    lines.insert(pos, target_row)
    return "\n".join(lines)


def enrich_task(task: Task, seed: int) -> Task:
    """Fill dynamic placeholders with seeded generated content. Returns a copy."""
    data = task.model_dump()
    if "{FLIGHT_CATALOG}" in data["prompt"]:
        rng = random.Random(seed)
        data["prompt"] = data["prompt"].replace("{FLIGHT_CATALOG}", build_flight_catalog(rng))
    return Task(**data)
