#!/usr/bin/env python3
"""CLI: run the voxel code-pagoda benchmark against an endpoint.

Grades the generated single-file HTML scene headlessly (playwright chromium);
saves artifact screenshot + score JSON.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from gauntlet.client import GauntletClient
from gauntlet.taskgen.pagoda_code import PAGODA_CODE_PROMPT, score_pagoda_code


async def run(endpoint: str, model: str, max_tokens: int, out: str | None) -> dict:
    client = GauntletClient(base_url=endpoint, model=model)
    r = await client.chat(
        [{"role": "user", "content": PAGODA_CODE_PROMPT}],
        max_tokens=max_tokens,
        temperature=0.2,
        no_think=True,
    )
    src = (r.content or "").strip()
    if src.startswith("```"):  # strip fences if the model added them anyway
        src = src.split("\n", 1)[1] if "\n" in src else src
        if src.rstrip().endswith("```"):
            src = src.rstrip()[:-3]

    score = score_pagoda_code(src, "results/voxel_artifacts", model)
    d = score.as_dict()
    d.update({"model": model, "endpoint": endpoint, "output_head": src[:400]})
    if out:
        with open(out, "w") as f:
            json.dump(d, f, indent=1)
    print(f"voxel pagoda {model}: {d['pct']:.0f}%  voxels={score.voxel_count} "
          f"floors={score.pagoda_floors} fps={score.fps:.0f} tod={score.time_of_day!r} "
          f"bytes={score.file_bytes} checks={d['checks']}")
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    asyncio.run(run(a.endpoint, a.model, a.max_tokens, a.out))


if __name__ == "__main__":
    main()
