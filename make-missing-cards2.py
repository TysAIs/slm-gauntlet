#!/usr/bin/env python3
"""Recreate the 9 first-session FP16 card JSONs whose legacy HTML/PNG exist
but whose JSON sources are absent (same class as make-missing-cards.py).
Scores/suites/failure_modes computed from full result files with CLI weights.
VRAM/file sizes from the run log (first-session serve lines). MiniCPM Q8 size
looked up from pve-gguf-inventory.txt at runtime.
"""
import glob, json, sys
from pathlib import Path

sys.path.insert(0, ".")
from gauntlet.report import aggregate_results
from gauntlet.cli import SUITE_WEIGHTS as CLI_WEIGHTS

ROOT = Path("results")
CUTOFF = "20261028T201000Z"

inv = {}
try:
    for chunk in open("pve-gguf-inventory.txt").read().split(","):
        pass
    raw = open("pve-gguf-inventory.txt").read()
    parts = raw.split(",")
    for i in range(0, len(parts) - 1, 2):
        try:
            inv[parts[i + 1].strip().split("/")[-1]] = int(parts[i])
        except (ValueError, IndexError):
            continue
except FileNotFoundError:
    pass

SPECS = {
    "spark-x2.6-4b-q4km": dict(display="Spark-X2.6-4B", release="Oct 2026",
        gguf="Spark-X2.6-4B-Q4_K_M.gguf", size=3543441312, quant="Q4_K_M", vram=4635,
        sub="Q4_K_M · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "spark-x2.6-4b-q8_0": dict(display="Spark-X2.6-4B", release="Oct 2026",
        gguf="Spark-X2.6-4B-Q8_0.gguf", size=4375021824, quant="Q8_0", vram=6031,
        sub="Q8_0 · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "spark-x2.6-1.7b-q4km": dict(display="Spark-X2.6-1.7B", release="Oct 2026",
        gguf="Spark-X2.6-1.7B-Q4_K_M.gguf", size=1768720512, quant="Q4_K_M", vram=2013,
        sub="Q4_K_M · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "spark-x2.6-1.7b-q8_0": dict(display="Spark-X2.6-1.7B", release="Oct 2026",
        gguf="Spark-X2.6-1.7B-Q8_0.gguf", size=1820113440, quant="Q8_0", vram=2575,
        sub="Q8_0 · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "bolt-e4b-q4km": dict(display="Bolt E4B", release="Oct 23 2026",
        gguf="Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf", size=6180446208, quant="Q4_K_M", vram=3985,
        sub="Q4_K_M · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "minicpmv47-1b-q8_0": dict(display="MiniCPM-V 4.7 1B", release="Oct 12 2026",
        gguf="MiniCPM-V-4_7-1B-Q8_0.gguf", size=inv.get("MiniCPM-V-4_7-1B-Q8_0.gguf"), quant="Q8_0", vram=1507,
        sub="Q8_0 · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "minicpmv47-1b-q4km": dict(display="MiniCPM-V 4.7 1B", release="Oct 12 2026",
        gguf="MiniCPM-V-4_7-1B-Q4_K_M.gguf", size=672003680, quant="Q4_K_M", vram=1239,
        sub="Q4_K_M · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "minicpmv47-1b-q5km": dict(display="MiniCPM-V 4.7 1B", release="Oct 12 2026",
        gguf="MiniCPM-V-4_7-1B-Q5_K_M.gguf", size=752461152, quant="Q5_K_M", vram=1285,
        sub="Q5_K_M · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
    "minicpmv47-1b-q6k": dict(display="MiniCPM-V 4.7 1B", release="Oct 12 2026",
        gguf="MiniCPM-V-4_7-1B-Q6_K.gguf", size=837947232, quant="Q6_K", vram=1333,
        sub="Q6_K · FP16 · 32K · GTX 1070 Ti · Oct 2026"),
}

out = []
for mid, sp in SPECS.items():
    assert sp["size"], f"missing size for {mid}"
    cands = []
    for rf in glob.glob(str(ROOT / f"{mid}_*.json")):
        rj = json.load(open(rf))
        if not isinstance(rj, dict) or "results" not in rj:
            continue
        if len(rj["results"]) < 67:
            continue
        cands.append((rf, rj))
    assert len(cands) == 1, f"{mid}: {len(cands)} full candidates"
    rf, rj = cands[0]
    agg = aggregate_results(rj["results"], CLI_WEIGHTS)
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
                     "kv_type": "FP16", "context_tokens": 32768,
                     "vram_used_mb": sp["vram"], "vram_total_mb": 8192,
                     "kv_pool_tokens": 32768, "max_subagents": 4,
                     "server_build": build, "category": "on-GPU ≤12B"}}
    json.dump([m], open(ROOT / "cards" / f"card_{mid}.json", "w"), indent=1)
    out.append(m)
    print(mid, m["overall_pct"], "build:", build, "fm:", m["failure_modes"])
json.dump(out, open("/tmp/missing2-input.json", "w"), indent=1)
