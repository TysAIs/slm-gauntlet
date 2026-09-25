"""Pagoda build benchmark: staged creative construction, element-scored."""
from __future__ import annotations

import importlib.resources as _res
import re
from dataclasses import dataclass

ELEMENTS: list[tuple[str, float, list[str]]] = [
    ("foundation", 1.0, ["stone", "foundation", "base", "platform"]),
    ("stairway", 1.0, ["stair", "path", "steps"]),
    ("torii", 1.5, ["torii", "gate"]),
    ("pagoda_tiers", 2.0, ["tier", "story", "level", "roof"]),
    ("roof_curvature", 1.5, ["sweep", "curve", "lift", "flare", "eave"]),
    ("lanterns", 1.0, ["lantern", "light", "glow"]),
    ("garden", 1.0, ["sakura", "garden", "gravel", "pond", "cherry"]),
    ("backdrop", 1.0, ["mountain", "water", "pond", "falls", "river"]),
    ("atmosphere", 1.0, ["mist", "dusk", "bell", "incense", "smoke", "evening", "fog"]),
]

TOTAL_WEIGHT = sum(w for _, w, _ in ELEMENTS)


def _load_prompt() -> str:
    return (_res.files("gauntlet.taskgen") / "pagoda_prompt.txt").read_text()


PROMPT = _load_prompt()


def strip_wrappers(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"```[a-z]*\n.*?\n```", "", text, flags=re.S)
    return text


@dataclass
class PagodaScore:
    elements: list[tuple[str, bool, float]]
    pct: float  # 0-100
    tier_hits: int  # for pagoda_tiers: number of tiers mentioned

    def as_dict(self) -> dict:
        return {
            "elements": [{"name": n, "passed": p, "weight": w} for n, p, w in self.elements],
            "pct": round(self.pct, 1),
            "tiers_mentioned": self.tier_hits,
        }


def score_pagoda(output: str) -> PagodaScore:
    body = strip_wrappers(output).lower()
    results: list[tuple[str, bool, float]] = []
    for name, weight, keys in ELEMENTS:
        results.append((name, any(k in body for k in keys), weight))
    # tier count: ordinals or counts of tier words
    tier_hits = max(
        [int(m) for m in re.findall(r"\b(\d+|three|four|five)\s+tiers?", body)] + [0]
        + [min(body.count("tier"), 5)]
    )
    pct = sum(w for _, p, w in results if p) / TOTAL_WEIGHT * 100
    return PagodaScore(elements=results, pct=pct, tier_hits=tier_hits)
