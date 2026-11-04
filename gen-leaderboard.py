#!/usr/bin/env python3
"""Generate results/_published/LEADERBOARD.md from extended card JSONs + perf JSONs.
Scores come from card JSONs (CLI 7-suite weights, the run's working standard).
Perf as measured; cache-flagged baselines (completion_tokens < 50 AND
TTFT < 1.0s) get a dagger. Separate sections (classifier/routing/OCR/LH) use
verified result files, never merged into the generative headline.
"""
import glob, json, re, sys
from pathlib import Path

ROOT = Path("results")
CARDS = ROOT / "cards"

FAM_ORDER = ["spark-x2.6-4b", "spark-x2.6-1.7b", "bolt-e4b", "lfm3-1.7b",
             "minicpm", "dory-4b", "dory-1.0-4b",
             "qwen35-9b", "lfm25-8b-a1b", "lfm25-1.2b", "lfm25-24b-a2b"]
FAM_LABEL = {"spark-x2.6-4b": "Spark-X2.6-4B", "spark-x2.6-1.7b": "Spark-X2.6-1.7B",
             "bolt-e4b": "Bolt E4B", "lfm3-1.7b": "LFM3-1.7B",
             "minicpm": "MiniCPM-V 4.7 1B",
             "dory-4b": "Dory 1.0 4B", "dory-1.0-4b": "Dory 1.0 4B",
             "qwen35-9b": "Qwen3.5-9B", "lfm25-8b-a1b": "LFM2.5-8B-A1B",
             "lfm25-1.2b": "LFM2.5-1.2B", "lfm25-24b-a2b": "LFM2.5-24B-A2B (offload)"}


def fam_of(mid):
    if mid.startswith("minicpm"):
        return "minicpm"
    for p in FAM_ORDER:
        if mid.startswith(p):
            return p
    # old-repo cards: prefix before first quant-ish token
    m = re.match(r"^([a-z0-9]+(?:-[a-z0-9.]+)*?)-(q|iq|ud)", mid)
    return m.group(1) if m else "other"


def pct(x):
    return f"{x * 100:.1f}" if x is not None else "—"


def main():
    cards = []
    for jf in sorted(glob.glob(str(CARDS / "card_*.json"))):
        data = json.load(open(jf))
        if not isinstance(data, list) or not data:
            continue
        m = data[0]
        if m["model"] == "announcement":
            continue
        cards.append(m)
    # perf
    perf = {}
    for pf in glob.glob(str(ROOT / "perf_*.json")):
        mid = Path(pf).name[len("perf_"):-len(".json")]
        try:
            perf[mid] = json.load(open(pf))
        except Exception:
            pass

    groups = {}
    for m in cards:
        groups.setdefault(fam_of(m["model"]), []).append(m)
    for g in groups.values():
        g.sort(key=lambda m: -m["overall_pct"])

    lines = []
    lines.append("# SLM Gauntlet — Leaderboard (updated Oct 31, 2026)")
    lines.append("")
    lines.append("All runs on a single PVE GTX 1070 Ti (8 GB), `-ngl 99`, seed 1, temp 0, "
                 "71 tasks / 7 suites, 32K primary unless noted. "
                 "KV labels are exact: q8_0 is NOT FP8, q4_0 is NOT FP4. "
                 "FP8/FP4 KV cache is NOT supported by the llama.cpp builds used (blocked, recorded).")
    lines.append("")
    lines.append("## Method notes (read before ranking)")
    lines.append("")
    lines.append("- **Scores use CLI 7-suite weights** (tool .30, structured .15, retrieval .15, "
                 "coding .10, instruction .10, adversarial .10, agent_chains .10) — the same "
                 "figures as every model card and the run log. `gauntlet/report.py` defines a "
                 "different 5-suite headline (tool .40, structured .20, retrieval .20, coding .10, "
                 "instruction .10; adversarial/chains excluded); e.g. Bolt Q4 q4_0 is 85.5% here "
                 "vs 87.9% under report.py weights. Unifying the weighting is an open decision; "
                 "no score below was recomputed to hide the gap.")
    lines.append("- **Ties:** scores within one task of each other are ties, stated plainly. "
                 "A winner must win on the full 71-task suite with per-suite breakdown — never "
                 "from a smoke test, perf alone, or a single run.")
    lines.append("- **Perf:** TTFT + tok/s as measured. † = baseline looks prefix-cache-affected "
                 "(completion_tokens < 50 AND TTFT < 1.0s); those baselines are NOT comparable "
                 "for ranking — see the run log per-variant notes. `decode_tok_s` fields are a "
                 "script artifact and are never shown. Concurrency aggregates are shown as measured; "
                 "cache-fast concurrency figures are flagged in the run log.")
    lines.append("- **Categories:** on-GPU ≤12B is the primary scope; >12B / MoE-offload rows are "
                 "scored separately and never merged. Classifier, routing, OCR, and long-horizon "
                 "suites have their own sections below — never merged into the generative headline.")
    lines.append("- **Cards:** every row links its regenerated card (new template: release date, "
                 "GGUF file/size, quant, KV, context, VRAM used/total, KV pool, max subagents, "
                 "failure modes, server build, category). VRAM 'not recorded' means the run log "
                 "did not record a 32K serve figure for that variant — it was not guessed.")
    lines.append("- **LFM2.5-8B-A1B perf is degenerate** (reasoning-format issue: 1-token "
                 "completions, 0.43 tok/s baseline) — do NOT use its tok/s row as speed. "
                 "Its accuracy row (56.1%) stands as measured; the failure mode is "
                 "empty_response 29 (reasoning-only output not landing in the harness final-text "
                 "field), not a server failure.")
    lines.append("")

    # BEST-OF
    lines.append("## BEST-OF")
    lines.append("")
    ongpu = [m for m in cards if (m.get("details") or {}).get("category") != "offload"]
    best = max(ongpu, key=lambda m: m["overall_pct"])
    lines.append(f"- **Best on-GPU overall: {best['display_name']} "
                 f"({best['details'].get('quant')}, KV {best['details'].get('kv_type')}) — "
                 f"{best['overall_pct']:.1f}%** — card `cards/card_{best['model']}.png`. "
                 f"Ties within one task are listed per family below; no single winner is declared "
                 f"from a one-task gap.")
    lines.append("- **Best offload (generative): LFM2.5-24B-A2B UD-Q4_K_XL, 8K cap — 59.2%** "
                 "(retrieval 0% is an 8K-cap artifact, not a model score). Flint IQ2_XXS has no "
                 "full score (aborted on swap; smoke 89.5% only, NOT a score).")
    lines.append("- **Best classifier:** no single winner — Clef 27B Q4 for accuracy/calibration "
                 "(choice 100%, score 100%, ECE 0.029, 2.4s), Clef-flash Q4 for on-GPU accuracy "
                 "(choice 100%, 346ms), d1-2B Q4 for speed + score-MAE (56ms, MAE 0.083). "
                 "See the classifier section.")
    lines.append("- **Best long-horizon (100K+): Qwen3.5-9B Q4_K_M q4_0 KV — 0.875 (7/8)** "
                 "(both hard aggregation tasks exact). 32K rank does NOT predict 100K rank: "
                 "Spark best-at-32K falls to 0.50 at 100K, MiniCPM best to 0.19. "
                 "See the long-horizon section.")
    lines.append("- **Best KV per family** (best variant per KV type; full per-variant rows below):")
    for fam in FAM_ORDER:
        ms = groups.get(fam, [])
        if not ms:
            continue
        bykv = {}
        for m in ms:
            kv = (m.get("details") or {}).get("kv_type") or "?"
            if kv not in bykv or m["overall_pct"] > bykv[kv]["overall_pct"]:
                bykv[kv] = m
        parts = [f"{kv}: {m['details'].get('quant')} {m['overall_pct']:.1f}%"
                 for kv, m in sorted(bykv.items())]
        lines.append(f"  - {FAM_LABEL.get(fam, fam)} — " + "; ".join(parts))
    lines.append("")

    # Generative table, grouped by family
    lines.append("## Generative leaderboard (71 tasks, 32K primary)")
    lines.append("")
    hdr = ("| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | "
           "KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | "
           "TTFT | tok/s 1/4/8 | Failure modes | Card | Category |")
    sep = ("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for fam in FAM_ORDER + sorted(set(groups) - set(FAM_ORDER)):
        ms = groups.get(fam)
        if not ms:
            continue
        lines.append(f"### {FAM_LABEL.get(fam, fam)}")
        lines.append("")
        lines.append(hdr)
        lines.append(sep)
        for m in ms:
            d = m.get("details") or {}
            s = m.get("suites") or {}
            p = perf.get(m["model"]) or {}
            ttft, tps = "—", "—"
            if p:
                b = p.get("baseline_short") or {}
                tt = b.get("ttft_s")
                flag = "†" if (b.get("completion_tokens", 99) < 50 and tt is not None and tt < 1.0) else ""
                ttft = f"{tt:.2f}s{flag}" if tt is not None else "—"
                conc = p.get("concurrency") or []
                if len(conc) >= 3:
                    tps = (f"{conc[0]['aggregate_tok_s']:.0f}/"
                           f"{conc[1]['aggregate_tok_s']:.0f}/"
                           f"{conc[2]['aggregate_tok_s']:.0f}")
                elif conc:
                    tps = f"{conc[0]['aggregate_tok_s']:.0f}"
            gg = d.get("gguf_file") or "—"
            if d.get("gguf_size_bytes"):
                gg += f" ({d['gguf_size_bytes'] / 1e9:.2f} GB)"
            vram = (f"{d['vram_used_mb']:,} / {d.get('vram_total_mb', 8192):,}"
                    if d.get("vram_used_mb") else "not recorded")
            fm = m.get("failure_modes") or {}
            fm_s = "none" if not fm else " · ".join(f"{k} {v}" for k, v in sorted(fm.items()))
            lines.append(
                f"| {m['display_name']} | {d.get('release_date') or '—'} | {gg} | "
                f"{d.get('quant') or '—'} | {d.get('kv_type') or '—'} | "
                f"{d.get('context_tokens', 32768):,} | {vram} | "
                f"{d.get('kv_pool_tokens', 32768):,} | {d.get('max_subagents', 4)} | "
                f"**{m['overall_pct']:.1f}%** | {pct(s.get('tooluse'))} | {pct(s.get('structured'))} | "
                f"{pct(s.get('retrieval'))} | {pct(s.get('coding'))} | {pct(s.get('instruction'))} | "
                f"{pct(s.get('adversarial'))} | {pct(s.get('agent_chains'))} | {ttft} | {tps} | "
                f"{fm_s} | `cards/card_{m['model']}.png` | {d.get('category') or '—'} |")
        lines.append("")

    # Separate sections (verified numbers, hardcoded from result files)
    lines.append("## Classifier leaderboard (SEPARATE — never merged into generative %)")
    lines.append("")
    lines.append("48-task v1.0 benchmark (`classifier-bench/`): routing/topic choice, urgency score "
                 "(4-level), noul @0.5. Metrics: choice accuracy, noul accuracy, score exact-level "
                 "accuracy + MAE, ECE (10 bins), multiclass Brier, mean/p95 latency, abstention "
                 "(confidence < 0.6), option-order flip rate (0–26). No composite % is invented.")
    lines.append("")
    lines.append("| Model | Quant | Choice | Noul | Score exact / MAE | ECE / Brier | Latency mean/p95 | Abstain | Flips |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    lines.append("| Clef-flash 9B (on-GPU) | Q4_K_M | 100% | 100% | 91.67% / 0.172 | 0.034 / 0.0015 | 346 / 497 ms | 2.08% | 0/26 |")
    lines.append("| Clef 27B (offload, -ngl 20, 8K) | Q4_K_M | 100% | 100% | 100% / 0.105 | 0.029 / 0.0026 | 2424 / 2928 ms | 4.17% | 0/26 |")
    lines.append("| d1-2B | Q4_K_M | 96.15% | 100% | 91.67% / 0.083 | 0.059 / 0.0348 | 56 / 71 ms | 8.33% | 0/26 |")
    lines.append("| d1-2B | Q8_0 | 100% | 100% | 83.33% / 0.167 | 0.060 / 0.0259 | 50 / 67 ms | 6.25% | 0/26 |")
    lines.append("| d1-3B | Q4_K_M | 96.15% | 100% | 91.67% / 0.231 | 0.088 / 0.0570 | 69 / 103 ms | 4.17% | 0/26 |")
    lines.append("| d1-Omni-2B | Q8_0 | 96.15% | 90% | 91.67% / 0.083 | 0.112 / 0.0474 | 52 / 61 ms | 6.25% | 1/26 |")
    lines.append("| d1-omni-600M | Q8_0 | 96.15% | 100% | 58.33% / 0.512 | 0.054 / 0.0318 | 39 / 51 ms | 8.33% | 1/26 |")
    lines.append("| Laya 421M | Q8_0 | 88.46% | 100% | 50.00% / 0.682 | 0.112 / 0.1473 | 47 / 58 ms | 14.58% | 1/26 |")
    lines.append("")
    lines.append("Notes: Clef-flash Q8_0 does-not-fit on-GPU (9.4 GB weights > 8 GB VRAM). "
                 "d1-omni-600M, d1-Omni-2B, and Laya have NO Q4 GGUF (Q8_0 used). "
                 "Clef vendor inference code defaults max_length 16,384 with silent trimming — "
                 "benchmarks must pass max_length explicitly. Candidate identification, Oct 31: "
                 "Julia-1 (SupersonicLabs/Julia-1, Sep 23 2026; GGUF Oct 1), Kev-4B "
                 "(jaredpalmer/kev-4b, Sep 19 2026; GGUF Oct 1), Strands Decider (StrandsAgents, "
                 "Oct 2026 variants), s1-llm-auto-router (system1models Oct 2 / decisionmodels "
                 "Oct 15 2026), Sieve family (sthanika-ai, Oct 2026) all EXIST on HF, but their "
                 "type (classifier vs generative), weights/format for decision serving, size, "
                 "and PVE fit are NOT verified and they are NOT benched — do not assume them. "
                 "'lev' remains ambiguous (no confident classifier match).")
    lines.append("")
    lines.append("## Routing suite (SEPARATE — 12 tasks, validated on 2 models)")
    lines.append("")
    lines.append("| Model | Routing | Failure modes |")
    lines.append("|---|---|---|")
    lines.append("| Spark-X2.6-4B Q8_0 q4_0 (strong) | 12/12 (100%) | none |")
    lines.append("| MiniCPM-V 4.7 1B Q4_K_M q4_0 (weak) | 8/12 (66.7%) | looped 1; wrong-tool-then-refuse, looped refusal, dropped 2nd hop ×2 |")
    lines.append("")
    lines.append("Verdict: KEEP SEPARATE. Measures tool routing, a different skill from the 71-task "
                 "generative suite; discrimination confirmed with interpretable failure modes.")
    lines.append("")
    lines.append("## OCR suite (SEPARATE — 10 tasks, vision models ONLY)")
    lines.append("")
    lines.append("| Model | OCR field score | Notes |")
    lines.append("|---|---|---|")
    lines.append("| MiniCPM-V 4.7 1B Q4_K_M + mmproj | 0.95 | 9/10 perfect; redacted 0.5 (computed a total instead of refusing) |")
    lines.append("| LFM3-VL-2B Q4_K_M + mmproj | 0.90 | 9/10 perfect; redacted 0.0 (empty response) |")
    lines.append("")
    lines.append("Verdict: KEEP SEPARATE. Both models refuse illegible input correctly, handle "
                 "rotation/low-contrast/two-column. Text models are never scored here. "
                 "LFM3-VL-2B is OCR-track only in this run.")
    lines.append("")
    lines.append("## Long-horizon 100K+ suite (SEPARATE — 8 tasks, ~95K–100K prompt tokens)")
    lines.append("")
    lines.append("Shared 71,438-word ledger; buried policies (exclude [INTERNAL] transfers; ISO dates); "
                 "multi-hop sum, buried-policy total, retrieval at distance, multi-turn state, "
                 "distractor, count, ISO date, amendment. Bench max_tokens 4096 = harness standard. "
                 "Per-model prompt tokens recorded (tokenizer-dependent). Never overwrites 32K scores.")
    lines.append("")
    lines.append("| Model | Context / KV | VRAM @102400 | Prompt tokens | LH score | Notes |")
    lines.append("|---|---|---|---|---|---|")
    lines.append("| Qwen3.5-9B Q4_K_M q4_0 KV | 102400 / q4_0 | 6,847 MiB (spare 1,345) | ~93.5K | **0.875 (7/8)** | 100K LEADER; both hard aggregation tasks exact; only multihop-sum empty; FP16 KV-OOM at 102400 |")
    lines.append("| LFM3-1.7B IQ4_NL FP16 | 102400 / FP16 | 2,571 MiB | ~98.1K | 0.75 (6/8) | Failures are wrong values ($149K vs $164K; count 3 vs 7) |")
    lines.append("| Spark-X2.6-4B IQ3_M FP16 | 102400 / FP16 | 6,519 MiB (spare 1,673) | ~100.6K | 0.50 (4/8) | Aggregation tasks empty (full reasoning, no answer); run-to-run unstable |")
    lines.append("| MiniCPM-V 4.7 1B IQ4_XS FP16 | 102400 / FP16 | 2,103 MiB | ~93.5K | 0.1875 (1.5/8) | Near-total collapse; date policy violated; amendment took original budget |")
    lines.append("| Dory 1.0 4B Q5_K_M q4_0 | 102400 / q4_0 | 6,909 MiB (spare 1,283) | 103.3K | does-not-fit | Tokenizer needs 103,328+ tokens > 102400 cap (clean 400s, server healthy). q8_0 KV also fails at 102400 (KV alloc OOM): Dory does-not-fit at 100K+ for both KVs |")
    lines.append("| Bolt E4B Q4_K_M | 102400 req. / FP16 | 5,153 MiB | 93,154 | does-not-fit | Model context capped at 65,536 (training); prompt exceeds cap. Model-level cap (all Bolt quants share the architecture/config): Bolt does-not-fit at 100K+ as a model, not just Q4_K_M |")
    lines.append("| Spark-X2.6-1.7B Q8_0 FP16 | 102400 / FP16 | 3,599 MiB (spare 4,593) | ~100.7K | 0.625 (5/8) | Pass multihop, multiturn, distractor, date, amendment. Fail (all EMPTY, fast ~36s): buried-total, distance, count. Beats Spark 4B best (0.50) at 100K |")
    lines.append("| LFM2.5-8B-A1B UD-Q4_K_M FP16 | 102400 / FP16 | 6,549 MiB (spare 1,643) | ~98.1K | 0.1875 (1.5/8) | Pass amendment; distance partial 0.5. Fail: multihop refusal after 138s reasoning; buried/distractor/date EMPTY (~62s); multiturn 'I don't know'; count boxed 9 (truth 7). Genuine reasoning failures, not the 8B 71-task format artifact (LH reads content directly) |")
    lines.append("| LFM2.5-1.2B Q8_0 FP16 | 102400 / FP16 | 2,673 MiB (spare 5,519) | ~100.7K | 0.0 (0/8) | Complete collapse, worst in the set: 6/8 EMPTY (fast); multihop EMPTY after 110.8s; count + date-policy echoed ledger boilerplate instead of answering |")
    lines.append("")
    lines.append("Finding: 32K rank does NOT predict 100K rank. Best-per-model LH coverage is now "
                 "complete (Qwen, LFM3, Spark 4B, Spark 1.7B, MiniCPM, LFM2.5-8B, LFM2.5-1.2B scored; "
                 "Dory + Bolt does-not-fit with distinct reasons). Remaining per-variant LH rows "
                 "(every other fitting quant/KV) are a documented continuation queue, not silently "
                 "dropped (fit test: 102400 serve + spare ≥1 GiB + tokenizer prompt ≤ cap + model "
                 "context cap ≥ prompt).")
    lines.append("")
    lines.append("## 71-task audit (Oct 28, 2026)")
    lines.append("")
    lines.append("Core 71 kept unchanged for comparability: overwhelmingly real subagent work "
                 "(tool calls, error recovery, instruction following, long-context retrieval, "
                 "structured output, coding, agent chains). Mock-domain tasks (flights, records) are "
                 "real skill with synthetic data — flagged, not dropped. Weakest items are "
                 "trivial-arithmetic discipline checks (defensible as tool-use probes). Harder / "
                 "real-domain tasks belong in new separate suites (routing, OCR, long-horizon above), "
                 "validated on ≥2 models before any merge decision.")
    lines.append("")
    lines.append("## Future-proofing (scaling to bigger cards)")
    lines.append("")
    lines.append("The same 71-task suite, per-quant × per-KV rows, and separate classifier/routing/OCR/"
                 "long-horizon suites run unchanged on bigger cards: raise `-c` (32K → 64K → 102400+), "
                 "keep `--kv-unified`, and re-derive KV pool (= cap) and max 8K subagents "
                 "(= floor(pool/8192)). Quants that do-not-fit here (e.g. Clef-flash Q8_0, "
                 "Bolt 74B-A9B, Granite Switch 4.1 8B at 32K) become first-class rows there; "
                 "offload rows get a real context cap instead of an artifact. No AREO 3090 testing "
                 "was done in this run (PVE 1070 Ti only, per directive).")
    lines.append("")
    lines.append("## Pre-existing repo results (v0.3.1, NOT re-scored this run)")
    lines.append("")
    lines.append("The v0.3.1 leaderboard below is reproduced verbatim from the previous "
                 "LEADERBOARD.md (backed up as `LEADERBOARD.md.bak-v031`). These models were "
                 "already tested before this run and were NOT re-run, re-carded, or merged into "
                 "the rows above; their legacy card images remain in `results/cards/`. "
                 "Scores here used the v0.3.1 methodology (Bonsai-2: 65 merged tasks).")
    lines.append("")
    lines.append("| # | Model | Quant | Gauntlet % | Tests | tok/s (1 stream) |")
    lines.append("|---|-------|-------|-----------:|------:|-----------------:|")
    lines.append("| 🥇 | Gemma 4 · E4B | Q4_K_M | **87.9%** | 71 | 13.8 |")
    lines.append("| 🥈 | MiniCPM-V 5 · 2B | Q8_0 | **87.7%** | 71 | 26.3 |")
    lines.append("| 🥉 | Ternary Bonsai-2 · 27B | PTQ1_0 | **86.2%** | 65 | — |")
    lines.append("| 4 | MiniCPM-V 5 · 2B | Q4_K_M | **85.6%** | 71 | 31.7 |")
    lines.append("| 5 | Ornith 1.5 · 9B | Q4_K_M | **75.7%** | 71 | 10.2 |")
    lines.append("| 6 | MiMo V2.6 · 9B | Q4_K_M | **75.3%** | 71 | 13.0 |")
    lines.append("| 7 | Gemma 4 · 12B | UD-Q2_K_XL | **72.6%** | 71 | 7.0 |")
    lines.append("| 8 | LFM 2.5 · 2.6B | Q8_0 | **69.9%** | 71 | 25.9 |")
    lines.append("| 9 | LFM 2.5 · 2.6B | Q4_K_M | **69.6%** | 71 | 34.5 |")
    lines.append("| 10 | Qwen 3.5 · 4B | Q4_K_M | **68.2%** | 71 | 15.6 |")
    lines.append("| 11 | Gemma 4 · 12B | IQ3_XXS | **68.0%** | 71 | 6.5 |")
    lines.append("| 12 | Sharp-Spark X2.5 · 4B | Q4_K_XL | **66.4%** | 71 | 16.7 |")
    lines.append("| 13 | Gemma 3n · E4B | Q4_K_M | **56.3%** | 71 | 13.1 |")
    lines.append("")
    lines.append("## Blocks and open decisions (for Tyler)")
    lines.append("")
    lines.append("- Flint full suite: blocked on host RAM/swap (16 GB RAM, 8 GB swap); smoke 89.5% only. "
                 "Needs a bigger host, a Flint-only swap waiver, or smoke-only status.")
    lines.append("- Granite Switch 4.1 8B: does-not-fit 32K within the 1 GiB rule (spare 297 MiB). "
                 "Needs a headroom relaxation, an 8K score, or a does-not-fit ruling.")
    lines.append("- Thermal threshold: strict 80C caps probe-verified context at 32K (normal sustained "
                 "load is 81–82C); applied deviation is hard abort at 84C. Needs a confirmed threshold.")
    lines.append("- Score weighting: CLI 7-suite weights (cards/log) vs report.py 5-suite headline "
                 "differ (example above). Needs a unification ruling; leaderboard uses card figures.")
    lines.append("- Full KV expansion (q4_1, iq4_nl, q5_0, q5_1) for the older 39 variants: NOT assumed; "
                 "needs a Tyler decision.")
    lines.append("- Full re-runs of completed variants on the new build: NOT assumed (~40 full suites); "
                 "needs explicit instruction. Completed variants keep their build's scores, labeled per card.")
    lines.append("- Publish path: this file is generated from `results/cards/*.json` by "
                 "`gen-leaderboard.py`; the README table is generated by "
                 "`scripts/leaderboard_check.py`, which fails when the two disagree.")
    lines.append("- Card footer version discrepancy: footer says v0.3.1, code says 0.1.0, log says v0.4. "
                 "Flagged, not silently picked.")
    lines.append("")
    out = Path("results/_published/LEADERBOARD.md")
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.write_text("\n".join(lines))
    print(f"rows: {len(cards)} groups: {sorted(groups.keys())}")


if __name__ == "__main__":
    main()
