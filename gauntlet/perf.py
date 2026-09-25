"""Throughput benchmark: TTFT + decode tok/s at c=1/4/8, VRAM probe via endpoint metrics."""

from __future__ import annotations

import asyncio
import statistics
import time

import httpx

from gauntlet.client import GauntletClient

PROMPT_8K_WORDS = 6000  # ~8K tokens; realistic agent prompt size


def build_prefill_prompt() -> str:
    base = "Summarize the following notes in one sentence.\n\n"
    filler = (
        "The quarterly logistics review covered routing, warehouse capacity, and seasonal demand. "
        "Regional dispatch centers reported steady volumes with minor weather delays. "
        "Inventory reconciliation found small discrepancies in two categories, resolved same-day. "
    )
    return base + filler * (PROMPT_8K_WORDS // len(filler.split()))


async def _one_request(client: GauntletClient, prompt: str, max_tokens: int) -> dict:
    r = await client.chat_stream([{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=0.0)
    return {"ttft": r.ttft, "completion_tokens": r.usage.completion_tokens}


async def _timed_generation(client: GauntletClient, prompt: str, max_tokens: int) -> dict:
    """Measure TTFT (stream) and total wall time -> decode tok/s."""
    start = time.perf_counter()
    r = await client.chat_stream([{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=0.0)
    wall = time.perf_counter() - start
    ttft = r.ttft or wall
    decode_time = max(wall - ttft, 1e-6)
    tokens = r.usage.completion_tokens or len((r.content or "").split())
    return {
        "ttft_s": round(ttft, 4),
        "wall_s": round(wall, 4),
        "completion_tokens": tokens,
        "decode_tok_s": round(tokens / decode_time, 2),
        "total_tok_s": round(tokens / wall, 2),
    }


async def _concurrent_wave(client: GauntletClient, prompt: str, max_tokens: int, n: int) -> dict:
    results = await asyncio.gather(*[_timed_generation(client, prompt, max_tokens) for _ in range(n)])
    ttfts = [r["ttft_s"] for r in results]
    return {
        "concurrency": n,
        "ttft_mean_s": round(statistics.mean(ttfts), 4),
        "ttft_p95_s": round(sorted(ttfts)[int(len(ttfts) * 0.95) - 1], 4),
        "decode_tok_s_per_stream": round(statistics.mean(r["decode_tok_s"] for r in results), 2),
        "aggregate_tok_s": round(
            sum(r["completion_tokens"] for r in results) / max(max(r["wall_s"] for r in results), 1e-6), 2
        ),
    }


async def fetch_server_metrics(base_url: str) -> dict:
    """Pull llama-server /metrics (KV cache usage etc.) — observational."""
    try:
        async with httpx.AsyncClient(timeout=10) as hc:
            root = base_url.rsplit("/v1", 1)[0]
            resp = await hc.get(f"{root}/metrics")
            if resp.status_code != 200:
                return {"available": False}
            text = resp.text
            out = {"available": True}
            for line in text.splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                for key in ("kv_cache_tokens", "kv_cache_used", "requests_processing", "requests_waiting"):
                    if key in line:
                        try:
                            out[key] = float(line.split()[-1])
                        except ValueError:
                            pass
            return out
    except Exception:  # noqa: BLE001 — observational only
        return {"available": False}


async def run_perf_suite(endpoint: str, model: str, max_tokens: int = 256) -> dict:
    client = GauntletClient(base_url=endpoint, model=model)
    short_prompt = "Count from 1 to 50, then say DONE."
    try:
        baseline = await _timed_generation(client, short_prompt, max_tokens)
        prefill = await _timed_generation(client, build_prefill_prompt(), max_tokens)
        waves = [await _concurrent_wave(client, short_prompt, max_tokens, n) for n in (1, 4, 8)]
        metrics = await fetch_server_metrics(client.base_url)
    finally:
        await client.close()
    return {
        "baseline_short": baseline,
        "prefill_8k": prefill,
        "concurrency": waves,
        "server_metrics": metrics,
    }
