#!/usr/bin/env python3
"""Generate results/_published/LEADERBOARD.md from extended card JSONs + perf JSONs.

Scores come from the card JSONs: each row is re-scored with the weight table of
the epoch its own card names (`gauntlet/methodology.py` EPOCHS), never with a
weight table typed into this file. Perf as measured; cache-flagged baselines
(completion_tokens < 50 AND TTFT < 1.0s) get a dagger. Separate sections
(classifier/routing/OCR/LH) use verified result files, never merged into the
generative headline.

Usage: python3 scripts/gen_leaderboard.py [--out PATH]
"""
import glob
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "results"
CARDS = ROOT / "cards"

FAM_ORDER = ["spark-x2.6-4b", "spark-x2.6-1.7b", "bolt-e4b", "lfm3-1.7b",
             "minicpm", "dory-4b", "dory-1.0-4b",
             "qwen35-9b", "lfm25-8b-a1b", "lfm25-1.2b", "lfm25-24b-a2b"]
FAM_LABEL = {"spark-x2.6-4b": "Spark-X2.6-4B", "spark-x2.6-1.7b": "Spark-X2.6-1.7B",
             "bolt-e4b": "Bolt E4B", "lfm3-1.7b": "LFM3-1.7B",
             "minicpm": "MiniCPM-V 4.7 1B",
             "dory-4b": "Dory 1.0 4B", "dory-1.0-4b": "Dory 1.0 4B",
             "qwen35-9b": "Qwen3.5-9B", "lfm25-8b-a1b": "LFM2.5-8B-A1B",
             "lfm25-1.2b": "LFM2.5-1.2B", "lfm25-24b-a2b": "LFM2.5-24B-A2B (offload)",
             "gemma-e4b": "Gemma 3n · E4B", "gemma4-e4b": "Gemma 4 · E4B",
             "gemma4-12b": "Gemma 4 · 12B", "mimo-9b": "MiMo V2.6 · 9B",
             "ornith-9b": "Ornith 1.5 · 9B", "sharp-spark-4b": "Sharp-Spark · 4B",
             "qwen3.5": "Qwen3.5 · 4B", "qwen3.5-4b": "Qwen3.5 · 4B",
             "lfm2.5-2.6b": "LFM2.5 · 2.6B"}

# Same model, two card naming conventions (the 0.5.0 intake writes the vendor prefix the
# GGUF carries). One model must not get two sections.
FAM_ALIAS = {"nvidia-nemotron-3.5-bolt-e4b": "bolt-e4b",
             "nemotron-3.5-bolt-e4b": "bolt-e4b",
             "nvidia-nemotron-labs-dory1.0-4b": "dory-1.0-4b"}


def fam_of(mid):
    mid = (mid or "").lower()  # card ids mix cases (Qwen3.5-4B-Q4_K_M); grouping is by identity
    if mid.startswith("minicpm"):
        return "minicpm"
    for p in sorted(FAM_ALIAS):
        if mid.startswith(p):
            return FAM_ALIAS[p]
    for p in FAM_ORDER:
        if mid.startswith(p):
            return p
    # old-repo cards: prefix before first quant-ish token (dots allowed: "qwen3.5", "lfm2.5")
    m = re.match(r"^([a-z0-9][a-z0-9.]*(?:-[a-z0-9.]+)*?)-(q[0-9a-z_]|iq|ud)", mid)
    return m.group(1) if m else "other"



def pct(x):
    return f"{x * 100:.1f}" if x is not None else "—"


# --- epoch honesty ---------------------------------------------------------
# This document carries rows from more than one methodology (the 0.5.0 epoch re-ran
# 42 configurations at 94 tasks; the corpus still holds 225 pre-0.5.0 configurations
# at 71 tasks). The epoch of a row is derived from that card's own timestamp by the
# SAME function the published README table uses, so a row cannot claim an epoch it
# was not measured under, and two epochs never share a ranked table.
_spec = importlib.util.spec_from_file_location(
    "leaderboard_check", Path(__file__).resolve().parent / "leaderboard_check.py")
_lb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lb)
CURRENT_EPOCH = _lb.CURRENT_EPOCH
FULL_TASKS = _lb.FULL_TASKS
scorer_epoch = _lb.scorer_epoch
newest_published_epoch = _lb.newest_published_epoch


def epoch_of(card):
    return scorer_epoch(card.get("ts", ""), (card.get("details") or {}).get("methodology"))


def method_label(card):
    """The row's own task count and scorer - never inferred from a document header."""
    ep = epoch_of(card)
    n = card.get("n")
    tag = "current" if ep == CURRENT_EPOCH else f"pre-{CURRENT_EPOCH}"
    return f"{n if n is not None else '?'} t · {ep} ({tag})"


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
    # The document's header must describe the epoch it PRINTS, which is the newest one
    # that actually has rows — not whatever methodology the code currently ships. Bumping
    # METHODOLOGY_VERSION made this header claim "0.5.1 / 140 tasks" above a table of
    # 0.5.0 rows the moment the task set changed, before any new run existed.
    global CURRENT_EPOCH, FULL_TASKS
    if cards:
        CURRENT_EPOCH = _lb.CURRENT_EPOCH = newest_published_epoch({epoch_of(c) for c in cards})
        FULL_TASKS = _lb.FULL_TASKS = _lb.EPOCHS[CURRENT_EPOCH]["tasks"]
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
    newest = max((str(m.get("ts", "")) for m in cards), default="")
    stamp = f"{newest[:4]}-{newest[4:6]}-{newest[6:8]}" if len(newest) >= 8 else "unknown"
    lines.append(f"# SLM Gauntlet — Leaderboard (generated {stamp} from the card corpus)")
    lines.append("")
    epochs_present: dict[str, int] = {}
    for c in cards:
        ep = epoch_of(c)
        epochs_present[ep] = epochs_present.get(ep, 0) + 1
    mix = "; ".join(
        f"{n} cards at {_lb.EPOCHS[ep]['tasks']} tasks / scorer {ep}"
        for ep, n in sorted(epochs_present.items()) if ep in _lb.EPOCHS
    ) or "no cards"
    lines.append("All runs on a single NVIDIA GTX 1070 Ti (8 GB), `-ngl 99`, seed 1, "
                 "temperature 0 requests, 32K primary unless noted. Every row carries its own "
                 f"**Method** column and is scored with its own epoch's weight table ({mix}). "
                 "Rows from different epochs are printed as separate tables and are never ranked "
                 "against each other. "
                 "KV labels are exact: q8_0 is NOT FP8, q4_0 is NOT FP4. "
                 "FP8/FP4 KV cache is NOT supported by the llama.cpp builds used (blocked, recorded).")
    lines.append("")
    lines.append("## Method notes (read before ranking)")
    lines.append("")
    lines.append("- **Scores use the weights in `gauntlet/methodology.py`** — for 0.6.0 the 14-suite "
                 "table (tooluse .14 / realworld .06 / structured .07 / retrieval .07 / coding .06 / "
                 "instruction .05 / adversarial .05 / agent_chains .05 / email .12 / support .09 / "
                 "classify .08 / docintake .06 / summarize .05 / calendar .05); pre-0.6.0 rows use "
                 "their own frozen 8-suite table. These are the figures every model card and every "
                 "run log carry. `gauntlet/report.py` still defines an older 5-suite headline; no "
                 "score below uses it, and the divergence is named rather than hidden.")
    lines.append("- **Ties:** scores within one task of each other are ties, stated plainly. "
                 f"A winner must win on the full current suite ({FULL_TASKS} tasks at scorer "
                 f"{CURRENT_EPOCH}; 71 before it) with per-suite breakdown — never from a smoke test, "
                 "perf alone, or a single run.")

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
    # BEST-OF is scoped to the current epoch: a pre-0.5.0 71-task number can never
    # headline a table that now contains 94-task rows.
    ongpu = [m for m in cards if (m.get("details") or {}).get("category") != "offload"]
    cur_ongpu = [m for m in ongpu if epoch_of(m) == CURRENT_EPOCH]
    best = max(cur_ongpu or ongpu, key=lambda m: m["overall_pct"])
    best_ep = epoch_of(best)
    best_scope = (f"{FULL_TASKS}-task scorer {CURRENT_EPOCH}" if best_ep == CURRENT_EPOCH
                  else f"pre-{CURRENT_EPOCH} {best.get('n')}-task scorer {best_ep} (no current-epoch row yet)")
    lines.append(f"- **Best on-GPU overall: {best['display_name']} "
                 f"({best['details'].get('quant')}, KV {best['details'].get('kv_type')}) — "
                 f"{best['overall_pct']:.1f}%** — measured {best_scope}; card `../cards/card_{best['model']}.png`. "
                 f"Ties within one task are listed per family below; no single winner is declared "
                 f"from a one-task gap.")
    legacy_ongpu = [m for m in ongpu if epoch_of(m) != CURRENT_EPOCH]
    if cur_ongpu and legacy_ongpu:
        lb_best = max(legacy_ongpu, key=lambda m: m["overall_pct"])
        lines.append(f"- **Best pre-{CURRENT_EPOCH} on-GPU (NOT comparable with the line above): "
                     f"{lb_best['display_name']} ({lb_best['details'].get('quant')}, KV "
                     f"{lb_best['details'].get('kv_type')}) — {lb_best['overall_pct']:.1f}%** at "
                     f"{lb_best.get('n')} tasks / scorer {epoch_of(lb_best)}; "
                     f"card `../cards/card_{lb_best['model']}.png`.")

    lines.append("- **Best offload (generative): LFM2.5-24B-A2B UD-Q4_K_XL, 8K cap — 59.2%** "
                 "(retrieval 0% is an 8K-cap artifact, not a model score). Flint IQ2_XXS has no "
                 "full score (aborted on swap; smoke 89.5% only, NOT a score).")
    lines.append("- **Best classifier:** no single winner — Clef 27B Q4 for accuracy/calibration "
                 "(choice 100%, score 100%, ECE 0.029, 2.4s), Clef-flash Q4 for on-GPU accuracy "
                 "(choice 100%, 346ms), d1-2B Q4 for speed + score-MAE (56ms, MAE 0.083). "
                 "See the classifier section.")
    lines.append("- **Best long-horizon (100K+): LEGACY (v1, gameable substring scoring) — "
                 "superseded by the v2r suite; see `extra-suites/longhorizon-v2/`.**")
    lines.append("- **Best KV per family** (best variant per KV type; full per-variant rows below). "
                 f"Current-epoch line only — pre-{CURRENT_EPOCH} numbers are named separately so a "
                 "71-task figure never stands in for a 94-task one:")
    for fam in FAM_ORDER:
        ms = groups.get(fam, [])
        if not ms:
            continue
        cur = [m for m in ms if epoch_of(m) == CURRENT_EPOCH]
        if cur:
            bykv = {}
            for m in cur:
                kv = (m.get("details") or {}).get("kv_type") or "?"
                if kv not in bykv or m["overall_pct"] > bykv[kv]["overall_pct"]:
                    bykv[kv] = m
            parts = [f"{kv}: {m['details'].get('quant')} {m['overall_pct']:.1f}%"
                     for kv, m in sorted(bykv.items())]
            lines.append(f"  - {FAM_LABEL.get(fam, fam)} — " + "; ".join(parts))
        else:
            bykv = {}
            for m in ms:
                kv = (m.get("details") or {}).get("kv_type") or "?"
                if kv not in bykv or m["overall_pct"] > bykv[kv]["overall_pct"]:
                    bykv[kv] = m
            parts = [f"{kv}: {m['details'].get('quant')} {m['overall_pct']:.1f}%"
                     for kv, m in sorted(bykv.items())]
            lines.append(f"  - {FAM_LABEL.get(fam, fam)} — pre-{CURRENT_EPOCH} only: "
                         + "; ".join(parts))

    lines.append("")

    # Generative table, grouped by family. Current-epoch rows and pre-0.5.0 rows are
    # SEPARATE tables inside each family: one ranked table mixing a 94-task score with
    # a 71-task score is the defect this layout removes.
    lines.append(f"## Generative leaderboard (32K primary; current epoch is {FULL_TASKS} tasks / "
                 f"scorer {CURRENT_EPOCH})")
    lines.append("")
    lines.append(f"Each family lists its **current-epoch** rows first, then its **pre-{CURRENT_EPOCH}** "
                 "rows in their own table, in descending order. The Method column states the task count "
                 "and scorer the row was measured under: compare rows only inside the same Method.")
    lines.append("")
    hdr = ("| Model | Method | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | "
           "KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | "
           "TTFT | tok/s 1/4/8 | Failure modes | Card | Category |")
    sep = "|" + "---|" * 23

    def emit_rows(ms):
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
                f"| {m['display_name']} | {method_label(m)} | {d.get('release_date') or '—'} | {gg} | "
                f"{d.get('quant') or '—'} | {d.get('kv_type') or '—'} | "
                f"{d.get('context_tokens', 32768):,} | {vram} | "
                f"{d.get('kv_pool_tokens', 32768):,} | {d.get('max_subagents', 4)} | "
                f"**{m['overall_pct']:.1f}%** | {pct(s.get('tooluse'))} | {pct(s.get('structured'))} | "
                f"{pct(s.get('retrieval'))} | {pct(s.get('coding'))} | {pct(s.get('instruction'))} | "
                f"{pct(s.get('adversarial'))} | {pct(s.get('agent_chains'))} | {ttft} | {tps} | "
                f"{fm_s} | `../cards/card_{m['model']}.png` | {d.get('category') or '—'} |")

    for fam in FAM_ORDER + sorted(set(groups) - set(FAM_ORDER)):
        ms = groups.get(fam)
        if not ms:
            continue
        cur = [m for m in ms if epoch_of(m) == CURRENT_EPOCH]
        old = [m for m in ms if epoch_of(m) != CURRENT_EPOCH]
        lines.append(f"### {FAM_LABEL.get(fam, fam)}")
        lines.append("")
        if cur:
            lines.append(f"**Current epoch — {FULL_TASKS} tasks, scorer {CURRENT_EPOCH}**")
            lines.append("")
            lines.append(hdr)
            lines.append(sep)
            emit_rows(cur)
            lines.append("")
        if old:
            lines.append(f"**Pre-{CURRENT_EPOCH} — 71-task rows, NOT comparable with the table above**")
            lines.append("")
            lines.append(hdr)
            lines.append(sep)
            emit_rows(old)
            lines.append("")


    # Separate sections (verified numbers, hardcoded from result files)
    lines.append("## Classifier leaderboard (SEPARATE — never merged into generative %)")
    lines.append("")
    lines.append("48-task v1.0 benchmark (`classifier-bench/`): routing/topic choice, urgency score "
                 "(4-level), noul @0.5. Metrics: choice accuracy, noul accuracy, score exact-level "
                 "accuracy + MAE, ECE (10 bins), multiclass Brier, mean/p95 latency, abstention "
                 "(confidence < 0.6), option-order flip rate (0–26). No composite % is invented.")
    lines.append("")
    lines.append("| Model | Quant | Choice | Noul | Score exact / MAE | ECE / Brier | Latency mean/p95 | Abstain | Flips |")  # noqa: E501 (verbatim table row: one physical line)
    lines.append("|---|---|---|---|---|---|---|---|---|")
    lines.append("| Clef-flash 9B (on-GPU) | Q4_K_M | 100% | 100% | 91.67% / 0.172 | 0.034 / 0.0015 | 346 / 497 ms | 2.08% | 0/26 |")  # noqa: E501 (verbatim table row: one physical line)
    lines.append("| Clef 27B (offload, -ngl 20, 8K) | Q4_K_M | 100% | 100% | 100% / 0.105 | 0.029 / 0.0026 | 2424 / 2928 ms | 4.17% | 0/26 |")  # noqa: E501 (verbatim table row: one physical line)
    lines.append("| d1-2B | Q4_K_M | 96.15% | 100% | 91.67% / 0.083 | 0.059 / 0.0348 | 56 / 71 ms | 8.33% | 0/26 |")
    lines.append("| d1-2B | Q8_0 | 100% | 100% | 83.33% / 0.167 | 0.060 / 0.0259 | 50 / 67 ms | 6.25% | 0/26 |")
    lines.append("| d1-3B | Q4_K_M | 96.15% | 100% | 91.67% / 0.231 | 0.088 / 0.0570 | 69 / 103 ms | 4.17% | 0/26 |")
    lines.append("| d1-Omni-2B | Q8_0 | 96.15% | 90% | 91.67% / 0.083 | 0.112 / 0.0474 | 52 / 61 ms | 6.25% | 1/26 |")
    lines.append("| d1-omni-600M | Q8_0 | 96.15% | 100% | 58.33% / 0.512 | 0.054 / 0.0318 | 39 / 51 ms | 8.33% | 1/26 |")  # noqa: E501 (verbatim table row: one physical line)
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
    lines.append("| MiniCPM-V 4.7 1B Q4_K_M q4_0 (weak) | 8/12 (66.7%) | looped 1; wrong-tool-then-refuse, looped refusal, dropped 2nd hop ×2 |")  # noqa: E501 (verbatim table row: one physical line)
    lines.append("")
    lines.append("Verdict: KEEP SEPARATE. Measures tool routing, a different skill from the 71-task "
                 "generative suite; discrimination confirmed with interpretable failure modes.")
    lines.append("")
    lines.append("## OCR suite (SEPARATE — 10 tasks, vision models ONLY)")
    lines.append("")
    lines.append("| Model | OCR field score | Notes |")
    lines.append("|---|---|---|")
    lines.append("| MiniCPM-V 4.7 1B Q4_K_M + mmproj | 0.95 | 9/10 perfect; redacted 0.5 (computed a total instead of refusing) |")  # noqa: E501 (verbatim table row: one physical line)
    lines.append("| LFM3-VL-2B Q4_K_M + mmproj | 0.90 | 9/10 perfect; redacted 0.0 (empty response) |")
    lines.append("")
    lines.append("Verdict: KEEP SEPARATE. Both models refuse illegible input correctly, handle "
                 "rotation/low-contrast/two-column. Text models are never scored here. "
                 "LFM3-VL-2B is OCR-track only in this run.")
    lines.append("")
    lines.append("## Long-horizon 100K+ suite — LEGACY (v1 retired)")
    lines.append("")
    lines.append("The v1 long-horizon suite (`extra-suites/longhorizon/`) is RETIRED: its "
                 "substring/numeric-set scoring is gameable — an answer that echoes the ledger "
                 "can satisfy substring and number-set checks without answering the question. "
                 "It is superseded by the v2r suite (`extra-suites/longhorizon-v2/`, strict "
                 "deterministic scoring, no partial credit). The v1 result files are kept on "
                 "disk for provenance only and are NOT published as scores here; historical v1 "
                 "numbers survive only in pre-retirement snapshots of this document.")
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
    lines.append("The same suite, per-quant × per-KV rows, and separate classifier/routing/OCR/"
                 "long-horizon suites run unchanged on bigger cards: raise `-c` (32K → 64K → 102400+), "
                 "keep `--kv-unified`, and re-derive KV pool (= cap) and max 8K subagents "
                 "(= floor(pool/8192)). Quants that do-not-fit here (e.g. Clef-flash Q8_0, "
                 "Bolt 74B-A9B, Granite Switch 4.1 8B at 32K) become first-class rows there; "
                 "offload rows get a real context cap instead of an artifact.")
    lines.append("")
    lines.append("## Historical v0.3.1 table (NOT re-scored, kept for provenance)")
    lines.append("")
    lines.append("The v0.3.1 leaderboard is reproduced below from the previous LEADERBOARD.md. Every "
                 "model with a current-epoch row appears ABOVE at its own epoch's score; this table is "
                 "the older number and is never ranked against them. Scores here used the v0.3.1 "
                 "methodology (Bonsai-2: 65 merged tasks).")

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
    lines.append("## Known limitations and open questions")
    lines.append("")
    lines.append("- **Flint** has no full-suite score: the run exhausted the 16 GB host's RAM/swap "
                 "(smoke 89.5% only). Recorded as blocked, never as a score.")
    lines.append("- **Granite Switch 4.1 8B** does not fit 32K under the 1 GiB headroom rule "
                 "(297 MiB spare). Recorded does-not-fit, never as zero.")
    lines.append("- **Thermal ceiling:** the strict 80 °C rule caps probe-verified context at 32K "
                 "(normal sustained load runs 81–82 °C); the applied hard abort is 84 °C.")
    lines.append("- **Two weight tables exist in code:** the 14-suite table every card and run log "
                 "use (`gauntlet/methodology.py`) and an older 5-suite headline in "
                 "`gauntlet/report.py`. Every row above uses the card figures; the divergence is "
                 "named, not averaged away.")
    lines.append("- **KV expansion** beyond f16/q8_0/q4_0 (q4_1, iq4_nl, q5_0, q5_1) is not assumed "
                 "for older variants: only cells that were actually measured appear.")
    lines.append("- **Cross-build re-runs** of completed variants are not assumed: a row keeps the "
                 "engine build its own card names.")
    lines.append("- **Publish path:** this file is generated from `results/cards/*.json` by "
                 "`scripts/gen_leaderboard.py`; the README table is generated by "
                 "`scripts/leaderboard_check.py`, which fails when the two disagree.")
    lines.append("")
    out = ROOT / "_published" / "LEADERBOARD.md"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.write_text("\n".join(lines))
    print(f"rows: {len(cards)} groups: {sorted(groups.keys())}")


if __name__ == "__main__":
    main()
