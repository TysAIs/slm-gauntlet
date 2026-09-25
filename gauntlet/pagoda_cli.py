"""CLI: run the Pagoda build benchmark against an endpoint."""
from __future__ import annotations

import argparse
import asyncio
import json

from gauntlet.client import GauntletClient
from gauntlet.taskgen.pagoda import PROMPT, PagodaScore, score_pagoda


async def run(endpoint: str, model: str, max_tokens: int, out: str | None) -> PagodaScore:
    client = GauntletClient(base_url=endpoint, model=model)
    r = await client.chat([{"role": "user", "content": PROMPT}], max_tokens=max_tokens, temperature=0.7, no_think=True)
    s = score_pagoda(r.content or "")
    data = {"model": model, "endpoint": endpoint, "score": s.as_dict(), "output": r.content}
    if out:
        with open(out, "w") as f:
            json.dump(data, f, indent=1)
    print(f"Pagoda {model}: {s.pct:.0f}% ({s.tier_hits} tiers)")
    for name, p, w in s.elements:
        print(f"  {'✓' if p else '✗'} {name} (w{w})")
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-tokens", type=int, default=1500)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    asyncio.run(run(a.endpoint, a.model, a.max_tokens, a.out))


if __name__ == "__main__":
    main()
