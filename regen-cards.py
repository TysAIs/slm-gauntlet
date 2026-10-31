#!/usr/bin/env python3
"""Regenerate ALL card JSONs with the extended template fields, from existing
card JSONs (scores) + result files (failure_modes, build) + VRAM map (run log)
+ PVE GGUF inventory (exact file/size). No score is recomputed or invented:
overall_pct/suites come from the existing card JSON. Fields that cannot be
determined are left null and render as 'not recorded' (VRAM) or omitted.
Writes extended JSONs back to results/cards/ (originals backed up to
results/cards-backup-v1/) and a combined input file for make_cards.py.
"""
import glob, json, re, shutil, sys
from pathlib import Path

sys.path.insert(0, ".")
from gauntlet.report import aggregate_results
from gauntlet.cli import SUITE_WEIGHTS as CLI_WEIGHTS

ROOT = Path("results")
CARDS = ROOT / "cards"
BACKUP = ROOT / "cards-backup-v1"

QUANT_TOKENS = {
    "q4km": "Q4_K_M", "q8": "Q8_0", "q4ks": "Q4_K_S", "q5km": "Q5_K_M",
    "q5ks": "Q5_K_S", "q6k": "Q6_K", "q6kl": "Q6_K_L", "q6ks": "Q6_K_S",
    "q3km": "Q3_K_M", "q3kl": "Q3_K_L", "q3ks": "Q3_K_S", "q2k": "Q2_K",
    "iq3m": "IQ3_M", "iq3xs": "IQ3_XS", "iq3xxs": "IQ3_XXS", "iq2m": "IQ2_M",
    "iq4nl": "IQ4_NL", "iq4xs": "IQ4_XS", "q40": "Q4_0", "q41": "Q4_1",
    "q50": "Q5_0", "q51": "Q5_1", "q4kl": "Q4_K_L", "q4kxl": "Q4_K_XL", "q5kxl": "Q5_K_XL",
    "q6kxl": "Q6_K_XL", "q8kxl": "Q8_K_XL", "q3kxl": "Q3_K_XL",
    "q2kxl": "Q2_K_XL", "udq2xl": "UD-Q2_K_XL", "udq3xl": "UD-Q3_K_XL",
    "udq4xl": "UD-Q4_K_XL", "udq5xl": "UD-Q5_K_XL", "udq6xl": "UD-Q6_K_XL",
    "udq8xl": "UD-Q8_K_XL", "udq4km": "UD-Q4_K_M", "udq4kxl": "UD-Q4_K_XL",
    "udq5kxl": "UD-Q5_K_XL", "udq6kxl": "UD-Q6_K_XL", "udq8kxl": "UD-Q8_K_XL",
    "udq3kxl": "UD-Q3_K_XL", "udq2kxl": "UD-Q2_K_XL", "udiq2m": "UD-IQ2_M",
    "udiq3xxs": "UD-IQ3_XXS", "udq2k": "UD-Q2_K",
}
# family prefix in card model id -> (vram-map family, PVE dir base, release date)
FAMILIES = [
    ("spark-x2.6-4b", "spark-x2.6-4b", "Oct 2026"),
    ("spark-x2.6-1.7b", "spark-x2.6-1.7b", "Oct 2026"),
    ("bolt-e4b", "bolt-e4b", "Oct 23 2026"),
    ("minicpmv47-1b", "minicpmv47-1b", "Oct 12 2026"),
    ("minicpm-v-4.7-1b", "minicpmv47-1b", "Oct 12 2026"),
    ("lfm3-1.7b", "lfm3-1.7b", "Oct 24 2026"),
    ("dory-4b", "dory-4b", "Oct 2026"),
    ("dory-1.0-4b", "dory-4b", "Oct 2026"),
    ("qwen35-9b", "qwen3.5-9b", "Feb–Mar 2026"),
    ("lfm25-8b-a1b", "lfm2.5-8b-a1b", "May 28 2026"),
    ("lfm25-1.2b", "lfm2.5-1.2b", "Jan 2026"),
    ("lfm25-24b-a2b", "lfm2.5-24b-a2b", "Oct 12 2026"),
    # pre-existing repo cards (outside this run): GGUF mapped where the file
    # still exists on PVE; release/VRAM left blank (not verified this run)
    ("gemma4-e4b", "gemma4-e4b", ""),
    ("gemma4-12b", "gemma4-12b", ""),
    ("gemma-e4b", "gemma-e4b", ""),
    ("llama31-8b", "llama31-8b", ""),
    ("bonsai-2", "bonsai-2", ""),
    ("mimo-9b", "mimo-9b", ""),
    ("ornith-9b", "ornith-9b", ""),
    ("qwen35-4b", "qwen3.5-4b", ""),
    ("spark-x2.5", "spark-x2.5", ""),
    ("minicpm5-2b", "minicpm5-2b", ""),
    ("lfm25-2.6b", "lfm2.5-2.6b", ""),
    ("sharp-spark-4b", "sharp-spark-4b", ""),
    ("granite-switch-41", "granite-switch-41", ""),
]
VRAM_FAMILY = {"spark-x2.6-4b": "spark-x2.6-4b", "spark-x2.6-1.7b": "spark-x2.6-1.7b",
               "bolt-e4b": "bolt-e4b", "minicpmv47-1b": "minicpmv47-1b",
               "minicpm-v-4.7-1b": "minicpmv47-1b",
               "lfm3-1.7b": "lfm3-1.7b", "dory-4b": "dory-4b",
               "dory-1.0-4b": "dory-4b",
               "qwen35-9b": "qwen3.5-9b", "lfm25-8b-a1b": "lfm2.5-8b-a1b",
               "lfm25-1.2b": "lfm2.5-1.2b", "lfm25-24b-a2b": "lfm2.5-24b-a2b"}
CUTOFF = "20261028T201000Z"  # Oct 28 14:10 MDT = 20:10 UTC, new-build promotion


def parse_model(mid):
    kv = "FP16"
    rest = mid
    m = re.search(r"-kv(q4|q8)$", mid)
    if m:
        kv = "q4_0" if m.group(1) == "q4" else "q8_0"
        rest = mid[: m.start()]
    infix = None
    for inf in ("-xhtoken", "-bartowski", "-prithiv"):
        if inf in rest:
            infix = inf[1:]
            rest = rest.replace(inf, "")
    fam = None
    for prefix, _, _ in FAMILIES:
        if rest.startswith(prefix):
            fam = prefix
            break
    qtoken = rest[len(fam):].lstrip("-") if fam else None
    return fam, infix, qtoken, kv


def main():
    vram = json.load(open("vram-map.json"))["vram"]
    # inventory format is size,path, repeated
    parts = open("pve-gguf-inventory.txt").read().split(",")
    # parts alternate: size, path, size, path ... (trailing empty dropped)
    inv = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            size = int(parts[i].strip())
        except ValueError:
            continue
        path = parts[i + 1].strip()
        if not path.endswith(".gguf"):
            continue
        fn = path.split("/")[-1]
        d = path.split("/")[-2]
        qm = re.search(r"([A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)\.gguf$", fn)
        qtok = qm.group(1) if qm else None
        inv.setdefault((d, qtok), []).append((fn, size))

    BACKUP.mkdir(exist_ok=True)
    out_models, stats = [], {"cards": 0, "vram": 0, "gguf": 0, "build": 0,
                             "fail": 0, "unparsed": []}
    for jf in sorted(glob.glob(str(CARDS / "card_*.json"))):
        data = json.load(open(jf))
        if not isinstance(data, list) or not data:
            continue
        m = dict(data[0])
        mid = m["model"]
        if mid == "announcement":
            continue
        fam, infix, qtoken, kv = parse_model(mid)
        quant = QUANT_TOKENS.get(qtoken)
        if fam is None or quant is None:
            stats["unparsed"].append((mid, qtoken))
        # result file match: closest headline to card overall_pct among full runs
        best, best_diff = None, 1e9
        for rf in glob.glob(str(ROOT / f"{mid}_*.json")):
            try:
                rj = json.load(open(rf))
            except Exception:
                continue
            if not isinstance(rj, dict) or "results" not in rj:
                continue
            try:
                # cards were scored with the CLI 7-suite weights (see run log:
                # report.py 5-suite headline differs, e.g. Bolt Q4 q4_0 card
                # 85.5 vs report headline 87.9). Match on CLI weights; do NOT
                # rewrite card scores.
                agg = aggregate_results(rj["results"], CLI_WEIGHTS)
            except Exception:
                continue
            if len(rj["results"]) < 67:
                continue
            diff = abs(agg["subagent_capability_score"] * 100 - m["overall_pct"])
            if diff < best_diff:
                best, best_diff = (rj, agg), diff
        fm, build = {}, None
        if best and best_diff <= 0.2:
            fm = best[1]["failure_modes"]
            ts = best[0].get("meta", {}).get("timestamp", "")
            build = "Sep 11 · 0.4.0-dev" if ts < CUTOFF else "0.8.0-dev (new primary)"
            stats["build"] += 1
            if fm:
                stats["fail"] += 1
        # GGUF file/size
        gguf_file, gguf_size = None, None
        if fam:
            d = {"spark-x2.6-4b": "spark-x2.6-4b", "spark-x2.6-1.7b": "spark-x2.6-1.7b",
                 "bolt-e4b": "bolt-e4b", "minicpmv47-1b": "minicpmv47-1b",
                 "minicpm-v-4.7-1b": "minicpmv47-1b",
                 "gemma4-e4b": "gemma4-e4b", "gemma4-12b": "gemma4-12b",
                 "gemma-e4b": "gemma-e4b", "llama31-8b": "llama31-8b",
                 "bonsai-2": "bonsai-2", "mimo-9b": "mimo-9b",
                 "ornith-9b": "ornith-9b", "qwen35-4b": "qwen3.5-4b",
                 "spark-x2.5": "spark-x2.5", "minicpm5-2b": "minicpm5-2b",
                 "lfm25-2.6b": "lfm2.5-2.6b", "sharp-spark-4b": "sharp-spark-4b",
                 "granite-switch-41": "granite-switch-41",
                 "lfm3-1.7b": "lfm3-1.7b", "dory-4b": "dory-4b",
                 "dory-1.0-4b": "dory-4b",
                 "qwen35-9b": "qwen35-9b", "lfm25-8b-a1b": "lfm25-8b-a1b",
                 "lfm25-1.2b": "lfm25-1.2b", "lfm25-24b-a2b": "lfm25-24b-a2b"}[fam]
            if infix in ("xhtoken", "bartowski"):
                d = f"{d}-{infix}"
            # file quant token: strip UD- prefix handling: file token for UD quants
            # is like UD-Q4_K_M; card quant already has UD- form
            cands = inv.get((d, quant), [])
            if cands:
                gguf_file, gguf_size = cands[0]
                stats["gguf"] += 1
        # VRAM
        vram_used = None
        if fam and quant:
            vfam = VRAM_FAMILY[fam]
            vram_used = vram.get(f"{vfam}|{quant}|{kv}")
            if vram_used:
                stats["vram"] += 1
        context = 8192 if "lfm25-24b" in mid else 32768
        release = next((r for p, _, r in FAMILIES if p == fam), None)
        category = "offload" if "lfm25-24b" in mid else "on-GPU ≤12B"
        m["details"] = {
            "release_date": release, "gguf_file": gguf_file,
            "gguf_size_bytes": gguf_size, "quant": quant, "kv_type": kv,
            "context_tokens": context, "vram_used_mb": vram_used,
            "vram_total_mb": 8192, "kv_pool_tokens": context,
            "max_subagents": context // 8192, "server_build": build,
            "category": category,
        }
        m["failure_modes"] = fm
        shutil.copy(jf, BACKUP / Path(jf).name)
        json.dump([m], open(jf, "w"), indent=1)
        out_models.append(m)
        stats["cards"] += 1
    json.dump(out_models, open("/tmp/regen-input.json", "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
