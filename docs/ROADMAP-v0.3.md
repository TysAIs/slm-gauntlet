# slm-gauntlet v0.3 Roadmap (research-backed)

## Source research
- SparkBench (github.com/Weschera/spark-bench (Weschera)) — v6.8.0 Uncapped: 76 scenarios / 12 domains,
  expert agentic tier with deterministic tool-failure injection + retry gates, TrueScore =
  0.55*Quality + 0.25*Calibration + 0.15*Reliability + 0.05*Efficiency/Responsiveness.
  KEY CORRECTION: their "pagoda" is a single-file Three.js VOXEL CODE-GEN benchmark (graded by
  window.__VOXEL__ = {voxelCount, fps, pagodaFloors}, <700KB, no external assets) — creative CODE, not prose.
  Our original prose pagoda (keyword-presence scoring) was REMOVED 2026-09-26: it scored every model
  100% because mentioning common words like "stone"/"gate"/"light" passed every element — zero
  discrimination. Only the execution-graded voxel code pagoda (pagoda-code) remains, which is the
  version that actually separates models (14%-86% spread).
- Hard-task research: GAIA, tau2-bench, BFCL v3/v4, IFEval/IFBench, MuSR, TravelPlanner, JSONSchemaBench,
  Multi-IF, LiveCodeBench. Grading ladder: regex < jsonschema < AST tool-match < execution < state-diff.

## New suites to build (priority order)
1. tooluse-hard: parallel multi-call arg binding; tool-result validation + self-repair; multi-turn
   slot carry-over (state-transition grading); unknown-tool abstention; branching on prior result;
   clarification-before-action.
2. instruction-hard: format-locked long outputs w/ stacked constraints (IFBench-style); system-vs-user
   conflict hierarchy; multi-turn constraint persistence; exact-count/negative constraints; verbatim copy.
3. structured-hard: strict JSON-schema (free-gen vs GBNF-constrained delta); format hygiene under decoys.
4. plan: TravelPlanner-lite — 3-day itinerary, >=5 global constraints, arithmetic grading.
5. coding-hard: execution-graded synthesis + bug-repair against failing test (sandbox subprocess).
6. creative-code: DONE — voxel pagoda (pagoda_code_cli), execution-graded in Chromium.
7. calibration: confidence + escalation after N failures (stop instead of thrash).

## Scoring upgrades
- Partial credit per-constraint (3/5 constraints = 0.60), progress-rate for chains (3/5 hops = 0.6).
- Report prompt-level AND instruction-level accuracy; log every failure verbatim.
- Free-gen vs constrained structured delta reported separately.

## DSpark drafter A/B (TESTED 2026-09-26 — negative result)
openbmb MiniCPM5-2B-DSpark drafter on the Q4_K_M target, llama.cpp draft-dspark,
-ngl 99 -ngld 99, fa on, GTX 1070 Ti:
- single-stream: baseline 79.1 tok/s vs 64.8 (n-max 7) / 77-87 (n-max 4) — wash
- 4-way concurrent: 55.2 tok/s/stream baseline vs 46.0 with drafter = **-17% aggregate**
- draft acceptance ~0.40. Root cause: the drafter (2.6B BF16) is BIGGER than the 2B target.
Speculative decoding needs target >> drafter (8B+). Verdict: skip for 2B; keep for future
bigger targets on this card. Full data: results/dspark_ab_test.json

## Gemma 4 candidates (VERIFIED on HF, live API)
| candidate | file | size | note |
|---|---|---|---|
| unsloth/gemma-4-12b-it-GGUF | gemma-4-12b-it-UD-Q2_K_XL.gguf | 4.66 GB | 12B on 8GB, fits w/ 32k+ ctx |
| unsloth/gemma-4-12b-it-GGUF | gemma-4-12b-it-UD-IQ2_M.gguf | 4.21 GB | max headroom variant |
| bartowski/gemma-4-12B-it-GGUF | gemma-4-12B-it-IQ3_XXS.gguf | 5.15 GB | Q3 step-up A/B |
| bartowski/google_gemma-4-E4B-it-GGUF | google_gemma-4-E4B-it-Q4_K_M.gguf | 5.41 GB | pragmatic sweet spot |
| google/gemma-4-12B-it-qat-q4_0-gguf | gemma-4-12b-it-qat-q4_0.gguf | 6.98 GB | QAT, borderline 8k-16k only |

Caveats: Gemma4Unified arch needs recent llama.cpp; IQ kernels on sm_61 are slow; quality at 2-bit is the
real limiter, not VRAM (32k KV = 0.43 GiB at q8_0 thanks to sliding-window attention).
