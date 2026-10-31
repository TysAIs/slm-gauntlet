#!/usr/bin/env python3
"""Recreate the 5 missing card JSONs (Qwen3.5-9B, LFM2.5-8B/1.2B/24B) whose
legacy HTML/PNG exist but whose JSON sources are absent from results/cards/.
Scores/suites/failure_modes are computed from the full result files with CLI
7-suite weights (same standard as all other cards) — nothing hand-typed except
display metadata already recorded in the run log (VRAM, GGUF, release).
"""
import glob, json, sys
from pathlib import Path

sys.path.insert(0, ".")
from gauntlet.report import aggregate_results
from gauntlet.cli import SUITE_WEIGHTS as CLI_WEIGHTS

ROOT = Path("results")
CUTOFF = "20261028T201000Z"

SPECS = {
    "qwen35-9b-q4km": dict(display="Qwen3.5-9B", release="Feb–Mar 2026",
                           gguf="Qwen3.5-9B-Q4_K_M.gguf", size=5680522464,
                           quant="Q4_K_M", kv="FP16", context=32768, vram=6527,
                           category="on-GPU ≤12B",
                           sub="Q4_K_M · FP16 · 32K · GTX 1070 Ti · Feb–Mar 2026"),
    "lfm25-8b-a1b-udq4km": dict(display="LFM2.5-8B-A1B", release="May 28 2026",
                                gguf="LFM2.5-8B-A1B-UD-Q4_K_M.gguf", size=5322223200,
                                quant="UD-Q4_K_M", kv="FP16", context=32768, vram=5657,
                                category="on-GPU ≤12B",
                                sub="UD-Q4_K_M · FP16 · 32K · GTX 1070 Ti · May 2026"),
    "lfm25-1.2b-q4km": dict(display="LFM2.5-1.2B", release="Jan 2026",
                            gguf="LFM2.5-1.2B-Instruct-Q4_K_M.gguf", size=730895584,
                            quant="Q4_K_M", kv="FP16", context=32768, vram=1289,
                            category="on-GPU ≤12B",
                            sub="Q4_K_M · FP16 · 32K · GTX 1070 Ti · Jan 2026"),
    "lfm25-1.2b-q8_0": dict(display="LFM2.5-1.2B", release="Jan 2026",
                            gguf="LFM2.5-1.2B-Instruct-Q8_0.gguf", size=1246254304,
                            quant="Q8_0", kv="FP16", context=32768, vram=1781,
                            category="on-GPU ≤12B",
                            sub="Q8_0 · FP16 · 32K · GTX 1070 Ti · Jan 2026"),
    "lfm25-24b-a2b-udq4xl": dict(display="LFM2.5-24B-A2B", release="Oct 2026",
                                 gguf="LFM2.5-24B-A2B-UD-Q4_K_XL.gguf", size=14876901632,
                                 quant="UD-Q4_K_XL", kv="FP16", context=8192, vram=1293,
                                 category="offload",
                                 sub="UD-Q4_K_XL · FP16 · 8K offload · GTX 1070 Ti · Oct 2026"),
}

out = []
for mid, sp in SPECS.items():
    best, best_diff = None, 1e9
    for rf in glob.glob(str(ROOT / f"{mid}_*.json")):
        rj = json.load(open(rf))
        if not isinstance(rj, dict) or "results" not in rj:
            continue
        if len(rj["results"]) < 67:
            continue
        agg = aggregate_results(rj["results"], CLI_WEIGHTS)
        if agg["subagent_capability_score"] > 0:
            best, best_diff = (rj, agg), 0
            break
    assert best, f"no full result for {mid}"
    rj, agg = best
    suites = {k: v["pass1"] for k, v in agg["suites"].items()}
    ts = rj.get("meta", {}).get("timestamp", "")
    build = "Sep 11 · 0.4.0-dev" if ts < CUTOFF else "0.8.0-dev (new primary)"
    m = {"model": mid, "display_name": sp["display"], "sub": sp["sub"],
         "overall_pct": round(agg["subagent_capability_score"] * 100, 1),
         "suites": suites, "n": 71, "rank": "",
         "ts": ts[:8] if ts else "",
         "device_name": "GTX 1070 Ti", "device_vram_mb": 8192, "device_kind": "nvidia",
         "failure_modes": agg["failure_modes"],
         "details": {"release_date": sp["release"], "gguf_file": sp["gguf"],
                     "gguf_size_bytes": sp["size"], "quant": sp["quant"],
                     "kv_type": sp["kv"], "context_tokens": sp["context"],
                     "vram_used_mb": sp["vram"], "vram_total_mb": 8192,
                     "kv_pool_tokens": sp["context"],
                     "max_subagents": sp["context"] // 8192,
                     "server_build": build, "category": sp["category"]}}
    json.dump([m], open(ROOT / "cards" / f"card_{mid}.json", "w"), indent=1)
    out.append(m)
    print(mid, m["overall_pct"], "build:", build, "fm:", m["failure_modes"])
json.dump(out, open("/tmp/missing-input.json", "w"), indent=1)
