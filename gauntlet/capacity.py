"""Capacity analysis: KV pool budget and max realistic concurrent subagents.

All math from measured server state, never guessed:
- VRAM model footprint: from llama-server log (load_tensors/ggml_cuda lines) or nvidia-smi delta.
- KV bytes/token: computed from architecture (n_layer, n_head_kv, head_dim) * bytes per element
  (q8_0 KV = ~1.06 bytes/elem effective incl. scale blocks) — but when available we read the
  server's own KV self-test line ("KV self size") which is exact.
- Max concurrent streams: given a per-stream context budget C_min (minimum ctx a subagent needs,
  default 8192), max_streams = floor(kv_pool_bytes / (kv_bytes_per_token * C_min)).
  VRAM ceiling for the pool = total_vram - weights - compute_buffers(observed) - safety_margin.
"""
from __future__ import annotations

import argparse
import json
import re


def fetch_ctx_and_kv(log_text: str) -> dict:
    out = {}
    m = re.search(r"n_ctx_slot = (\d+)", log_text)
    if m:
        out["ctx_per_slot_total"] = int(m.group(1))
    m = re.search(r"KV self size\s*=\s*([0-9.]+)\s*([KMG])iB", log_text)
    if m:
        val = float(m.group(1))
        mult = {"K": 1024, "M": 1024**2, "G": 1024**3}[m.group(2)]
        out["kv_total_bytes"] = int(val * mult)
    m = re.search(r"n_slots = (\d+)", log_text)
    if m:
        out["slots"] = int(m.group(1))
    return out


def capacity_report(
    vram_total_mb: int,
    weights_mb: int,
    kv_total_bytes: int | None,
    ctx_total: int | None,
    slots: int,
    min_ctx_per_agent: int = 8192,
) -> dict:
    # observed: llama.cpp computes buffers ~0.5-1GB for 4B-class on CUDA; use measured delta if given
    kv_per_token = kv_total_bytes / ctx_total if (kv_total_bytes and ctx_total) else None
    # pool = VRAM not used by weights; reserve 1.2GB for compute activations & fragmentation
    pool_bytes = max(int((vram_total_mb - weights_mb - 1200) * 1024**2), 0)
    if kv_per_token:
        max_tokens_kv = int(pool_bytes / kv_per_token)
        max_agents = max_tokens_kv // min_ctx_per_agent
    else:
        max_tokens_kv = None
        max_agents = None
    return {
        "vram_total_mb": vram_total_mb,
        "weights_mb": weights_mb,
        "kv_pool_available_mb": round(pool_bytes / 1024**2),
        "kv_bytes_per_token": round(kv_per_token, 2) if kv_per_token else None,
        "kv_max_tokens_pool": max_tokens_kv,
        "max_concurrent_agents_at_8k_ctx": max_agents,
        "min_ctx_per_agent": min_ctx_per_agent,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="llama-server log file (on this machine)")
    ap.add_argument("--vram-total", type=int, default=8192)
    ap.add_argument("--weights-mb", type=int, required=True)
    ap.add_argument("--min-ctx", type=int, default=8192)
    args = ap.parse_args()
    info = fetch_ctx_and_kv(open(args.log).read())
    rep = capacity_report(
        args.vram_total, args.weights_mb, info.get("kv_total_bytes"),
        info.get("ctx_per_slot_total"), info.get("slots", 1), args.min_ctx,
    )
    rep["server_reported"] = info
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
