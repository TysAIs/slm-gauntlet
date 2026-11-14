# Scoreboard — epoch 0.6.0

**At a glance** — same hardware for every board, **NVIDIA GTX 1070 Ti 8GB**, 320-task battery, temperature-0 requests:

- best overall: **Gemma 4 E4B** Q4_K_M / KV q8_0, **90.2** (single run, seed 1);
- next three: Bolt E4B 89.3, Qwen3.5-9B 84.5, Spark-X2.6-4B 84.4 — Bolt is inside one task's weight of the lead, so it is a tie, not a win;
- at 102K context the hierarchy inverts: **MiniCPM5-2B** leads with 0.76, the 8 GB champion finishes last with 0.12;
- 28 models ranked, 302 scored configurations, 209 extended-matrix cells; epoch 0.6.0 is not comparable with 0.5.0 or earlier.

All results measured on one reference board: **NVIDIA GTX 1070 Ti 8GB**, llama.cpp serving, temperature-0 requests (the harness sets it per request), scores are the gauntlet weighted aggregate over the 320-task battery unless a board says otherwise. A cell that cannot be served in 8 GB is recorded as **does-not-fit** (serve_failed), never as zero.

Unless a row carries a 3-seed mean, scores are **single-run**. The five headline models with 3-seed variance data are marked † and listed in the Variance section; the table cell is that model's canonical seed-1 run — the same run its card names — not the 3-seed mean. Every cell is recomputable from the model's card (`results/cards/`); `scripts/scoreboard_check.py` re-derives every board whose instrument ships here and names the boards whose raw run logs stay off the publish surface.

Every board below repeats its hardware line: **NVIDIA GTX 1070 Ti 8GB**.

## T1 screen — 32,768 ctx, KV q8_0

*NVIDIA GTX 1070 Ti 8GB · single run per cell (each model's canonical seed-1 run); the five † models' 3-seed spread is in the Variance board.*

| # | Model | Quant | Score | License |
|---|---|---|---|---|
| 1 | Gemma 4 E4B † | Q4_K_M | **90.2** | Apache 2.0 |
| 2 | Bolt E4B † | Q4_K_M | **89.3** | OpenMDW-1.1 |
| 3 | Qwen3.5-9B † | Q4_K_M | **84.5** | Apache 2.0 |
| 4 | Spark-X2.6-4B † | Q4_K_M | **84.4** | Apache 2.0 |
| 5 | MiMo-V2.6-9B † | Q4_K_M | **83.6** | MIT |
| 6 | Gemma 4 E2B | Q4_0 | **83.5** | Apache 2.0 |
| 7 | Ornith-1.5-9B | Q4_K_M | **83.1** | MIT |
| 8 | Qwen3.5-4B | Q4_K_M | **83.0** | Apache 2.0 |
| 9 | MiniCPM5-2B | Q4_K_M | **79.6** | Apache 2.0 |
| 10 | Gemma 4 12B | UD-Q2_K_XL | **79.5** | Apache 2.0 |
| 11 | Ministral 3 8B | Q4_K_M | **79.5** | Apache 2.0 |
| 12 | Sharp-Spark-X2.6-4B | Q4_K_XL | **76.9** | Apache 2.0 |
| 13 | Dory 1.0 4B | Q5_K_M | **76.5** | OpenMDW-1.1 |
| 14 | Granite 4.2 8B | Q4_K_M | **74.2** | Apache 2.0 |
| 15 | Spark-X2.6-1.7B | Q4_K_M | **68.9** | Apache 2.0 |
| 16 | Ministral 3 3B | Q4_K_M | **68.9** | Apache 2.0 |
| 17 | Qwen3.5-2B | Q4_K_M | **67.3** | Apache 2.0 |
| 18 | LFM3-1.7B | Q4_K_M | **66.5** | LFM Open License v1.0 |
| 19 | Granite 4.2 3B | Q4_K_M | **65.7** | Apache 2.0 |
| 20 | Gemma 3n E4B | Q4_K_M | **64.7** | Gemma Terms |
| 21 | Nemotron 3 Nano 4B | Q4_K_M | **64.1** | NVIDIA Nemotron Open Model License |
| 22 | LFM2.5-2.6B | Q4_K_M | **62.3** | LFM Open License v1.0 |
| 23 | Llama 3.1 8B | Q4_K_M | **61.8** | Llama Community License |
| 24 | LFM2.5-8B-A1B | UD-Q4_K_M | **54.7** | LFM Open License v1.0 |
| 25 | Qwen3.5-0.8B | Q4_K_M | **54.6** | Apache 2.0 |
| 26 | MiniCPM-V 4.7 1B | Q4_K_M | **53.5** | Apache 2.0 |
| 27 | LFM2.5-1.2B | Q4_K_M | **53.1** | LFM Open License v1.0 |
| 28 | MiniCPM5-1B | Q4_K_M | **45.9** | Apache 2.0 |

## Phase M matrix — finalists × KV cache type (32,768 ctx)

*NVIDIA GTX 1070 Ti 8GB · single run per cell.*

Same battery, one factor varied: KV cache precision. Canonical column is q8_0.

| Cell | KV f16 | KV q8_0 | KV q4_0 |
|---|---|---|---|
| Bolt E4B Q4_K_M | 89.1 | 89.3 | 88.1 |
| Bolt E4B UD-IQ3_XXS | 89.3 | 89.7 | 88.4 |
| Bolt E4B UD-Q8_K_XL | 90.5 | 90.1 | 89.1 |
| Gemma 4 E4B Q4_K_M | 89.0 | 90.2 | 88.6 |
| MiMo-V2.6-9B Q4_K_M | 84.7 | 83.6 | 82.9 |
| MiniCPM5-2B Q4_K_M | 80.2 | 79.6 | 77.6 |
| MiniCPM5-2B Q8_0 | 80.0 | 79.8 | 78.8 |
| Ornith-1.5-9B Q4_K_M | 84.2 | 83.1 | 83.9 |
| Qwen3.5-4B Q4_K_M | 83.3 | 83.0 | 82.6 |
| Qwen3.5-9B Q4_K_M | 84.4 | 84.5 | 86.2 |
| Spark-X2.6-4B IQ3_M | 82.1 | 81.2 | 80.6 |
| Spark-X2.6-4B Q4_K_M | 84.1 | 84.4 | 83.1 |
| Spark-X2.6-4B Q8_0 | 84.1 | 85.5 | 86.0 |

## Extended matrix — every quant × every KV (summary)

*NVIDIA GTX 1070 Ti 8GB · single run per cell.*

209 scored cells across 9 models. Best cell per model below. Each best cell is shipped as a card
under `results/cards/`; the other 200 per-cell artifacts stay on the authoring machine, so this
board is reproducible from the shipped corpus only for the best cell it names —
`scripts/scoreboard_check.py` reports the extended matrix as a named exception instead of
pretending it verified every cell.

| Model | Cells | Best cell | Score | License |
|---|---|---|---|---|
| Bolt E4B | 18 | bolt-e4b-udq4kxl-kvf16 | **89.9** | OpenMDW-1.1 |
| Gemma 4 12B | 5 | gemma4-12b-iq3xxs-kvq4 | **88.6** | Apache 2.0 |
| Spark-X2.6-4B | 54 | spark-x2.6-4b-q4_1-kvf16 | **86.7** | Apache 2.0 |
| Sharp-Spark-X2.6-4B | 2 | sharp-spark-4b-q4kxl-kvf16 | **77.5** | Apache 2.0 |
| LFM3-1.7B | 59 | lfm3-1.7b-q5ks-kvf16 | **75.0** | LFM Open License v1.0 |
| Spark-X2.6-1.7B | 20 | spark-x2.6-1.7b-q8-kvf16 | **72.8** | Apache 2.0 |
| LFM2.5-2.6B | 5 | lfm2.5-2.6b-q8-kvf16 | **63.0** | LFM Open License v1.0 |
| MiniCPM-V 4.7 1B | 41 | minicpmv47-1b-q5_1-kvq4 | **57.4** | Apache 2.0 |
| LFM2.5-1.2B | 5 | lfm2.5-1.2b-q8-kvq8 | **53.3** | LFM Open License v1.0 |

## L2 — 65,536 ctx

*NVIDIA GTX 1070 Ti 8GB · single run per cell.*

The T1 battery served at 65,536-token context. Scores reproduce the T1 hierarchy essentially exactly; the board's information is in the fit column.

| Model | Quant | KV f16 | KV q8_0 | KV q4_0 |
|---|---|---|---|---|
| Bolt E4B | UD-Q8_K_XL | 90.5 | 90.1 | 89.1 |
| Gemma 4 12B | IQ3_XXS | 88.5 | 87.1 | 88.6 |
| Gemma 4 E2B | Q4_0 | 81.6 | 83.5 | 81.6 |
| Gemma 4 E4B | Q4_K_M | 89.7 | 90.0 | 88.6 |
| MiMo-V2.6-9B | Q4_K_M | 84.7 | 83.6 | 82.9 |
| MiniCPM5-2B | Q4_K_M | 80.3 | 79.6 | 77.6 |
| Ministral 3 8B | Q4_K_M | does-not-fit | does-not-fit | 79.3 |
| Ornith-1.5-9B | Q4_K_M | 84.2 | 83.1 | 83.9 |
| Qwen3.5-4B | Q4_K_M | 83.3 | 83.0 | 82.6 |
| Qwen3.5-9B | Q4_K_M | 84.4 | 84.5 | 86.2 |
| Spark-X2.6-4B | Q8_0 | 84.1 | 85.5 | 86.0 |

Ministral 3 8B does not fit at f16 or q8_0 KV at this context (served only at q4_0 KV).

## L3 — 102,400 ctx, long-horizon battery (25 tasks)

*NVIDIA GTX 1070 Ti 8GB · single run per model (25 tasks); reference runs listed separately.*

A different instrument from T1/L2: 25 long-horizon tasks at ~92K-token prompts. Score = fraction of tasks passed. The T1 hierarchy inverts here — the smallest model on the board leads, the T1 champion finishes last.

| # | Model | Passed | Score | License |
|---|---|---|---|---|
| 1 | MiniCPM5-2B | 19/25 | **0.76** | Apache 2.0 |
| 2 | Qwen3.5-9B | 16/25 | **0.64** | Apache 2.0 |
| 3 | MiMo-V2.6-9B | 16/25 | **0.64** | MIT |
| 4 | Qwen3.5-4B | 16/25 | **0.64** | Apache 2.0 |
| 5 | Ornith-1.5-9B | 15/25 | **0.60** | MIT |
| 6 | Gemma 4 12B | 11/25 | **0.44** | Apache 2.0 |
| 7 | Spark-X2.6-4B | 9/25 | **0.36** | Apache 2.0 |
| 8 | Gemma 4 E2B | 8/25 | **0.32** | Apache 2.0 |
| 9 | Gemma 4 E4B | 3/25 | **0.12** | Apache 2.0 |

Ministral 3 8B: does-not-fit at 102,400 ctx (serve_failed, VRAM) even at q4_0 KV. Bolt E4B: excluded by design — its training context cap is 65,536, below this board's context. Reference runs on the same instrument (not board entries): DeepSeek-V4.1-Flash, run as a reference on the same instrument, scored 0.92; LFM2.5-1.2B Q8_0 scored 0.0.

## Variance — top 5 × 3 seeds (canonical cells, KV q8_0)

*NVIDIA GTX 1070 Ti 8GB · 3 seeds per model; the mean and spread columns are the only aggregate on this board.*

| Model | Seed 1 | Seed 2 | Seed 3 | Mean | Spread |
|---|---|---|---|---|---|
| Gemma 4 E4B Q4_K_M | 90.2 | 90.0 | 90.0 | **90.1** | 0.2 |
| Bolt E4B UD-Q8_K_XL | 90.1 | 92.1 | 92.1 | **91.4** | 2.0 |
| Spark-X2.6-4B Q8_0 | 85.5 | 85.5 | 85.5 | **85.5** | 0.0 |
| Qwen3.5-9B Q4_K_M | 84.5 | 83.5 | 83.5 | **83.8** | 1.0 |
| MiMo-V2.6-9B Q4_K_M | 83.6 | 84.6 | 84.6 | **84.3** | 1.0 |

Seeds 2 and 3 reproduced identical aggregate scores on all five models (row-level diff on one pair: 305/320 rows byte-identical, differing rows unchanged in pass outcome). The observed spread is cross-session, not seed-driven. On 3-seed means, Bolt E4B passes Gemma 4 E4B — the canonical single-run order inverted, which is what this stage existed to catch.

## OCR board — document extraction (10 tasks, field score)

*NVIDIA GTX 1070 Ti 8GB · single run per model on the 2026-11-13 fixture.*

Vision models served with their projectors (mmproj). Fixture re-rendered 2026-11-13 with a neutral sample account; all three models re-run against it.

| Model | Field score | License |
|---|---|---|
| MiniCPM-V 4.7 1B | **0.90** | Apache 2.0 |
| LFM3-VL-2B | **0.85** | LFM Open License v1.0 |
| MiniCPM-OCR 1.0 | **0.85** | Apache 2.0 |

MiniCPM-V 4.7 1B's text-battery rows elsewhere on this board are text-only serves (no projector); its vision capability is measured only here.

## Notes and exclusions

- **Granite Switch** (IBM's classifier-story model) is excluded from the generative roster by role: it is a classification model, not a generative SLM, and its board is the classifier lane, not this one. Its weights were not run through the generative battery.
- The classifier board's expansion is blocked on a proprietary scoring endpoint the local harness cannot substitute; recorded as a known blocker, not a result.
- Licenses were re-checked against the publishers' Hugging Face model-card metadata on 2026-11-13 (family by family, from the card's license field, not from a summary). Corrections made in that pass: **Gemma 4** (E4B / E2B / 12B) is **Apache 2.0**, not the Gemma Terms that Gemma 3n still uses; **MiniCPM-V 4.7 1B** is **Apache 2.0**, so the board no longer says "see model repo". Families whose card could not be resolved keep an explicit "see model repo" — consult the repository before reuse. LFM Open License v1.0 permits commercial use below $10M annual revenue; it is not Apache 2.0. OpenMDW-1.1 is the Linux Foundation license carried by NVIDIA's current Nemotron releases.
- Epoch 0.6.0 scores are not comparable with 0.5.0: the task battery and scorer changed between epochs.
