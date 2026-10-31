# SLM Gauntlet — Leaderboard (updated Oct 31, 2026)

All runs on a single PVE GTX 1070 Ti (8 GB), `-ngl 99`, seed 1, temp 0, 71 tasks / 7 suites, 32K primary unless noted. KV labels are exact: q8_0 is NOT FP8, q4_0 is NOT FP4. FP8/FP4 KV cache is NOT supported by the llama.cpp builds used (blocked, recorded).

## Method notes (read before ranking)

- **Scores use CLI 7-suite weights** (tool .30, structured .15, retrieval .15, coding .10, instruction .10, adversarial .10, agent_chains .10) — the same figures as every model card and the run log. `gauntlet/report.py` defines a different 5-suite headline (tool .40, structured .20, retrieval .20, coding .10, instruction .10; adversarial/chains excluded); e.g. Bolt Q4 q4_0 is 85.5% here vs 87.9% under report.py weights. Unifying the weighting is an open decision; no score below was recomputed to hide the gap.
- **Ties:** scores within one task of each other are ties, stated plainly. A winner must win on the full 71-task suite with per-suite breakdown — never from a smoke test, perf alone, or a single run.
- **Perf:** TTFT + tok/s as measured. † = baseline looks prefix-cache-affected (completion_tokens < 50 AND TTFT < 1.0s); those baselines are NOT comparable for ranking — see the run log per-variant notes. `decode_tok_s` fields are a script artifact and are never shown. Concurrency aggregates are shown as measured; cache-fast concurrency figures are flagged in the run log.
- **Categories:** on-GPU ≤12B is the primary scope; >12B / MoE-offload rows are scored separately and never merged. Classifier, routing, OCR, and long-horizon suites have their own sections below — never merged into the generative headline.
- **Cards:** every row links its regenerated card (new template: release date, GGUF file/size, quant, KV, context, VRAM used/total, KV pool, max subagents, failure modes, server build, category). VRAM 'not recorded' means the run log did not record a 32K serve figure for that variant — it was not guessed.
- **LFM2.5-8B-A1B perf is degenerate** (reasoning-format issue: 1-token completions, 0.43 tok/s baseline) — do NOT use its tok/s row as speed. Its accuracy row (56.1%) stands as measured; the failure mode is empty_response 29 (reasoning-only output not landing in the harness final-text field), not a server failure.

## BEST-OF

- **Best on-GPU overall: Spark-X2.6 4B (IQ3_M, KV FP16) — 91.5%** — card `cards/card_spark-x2.6-4b-iq3m-bartowski.png`. Ties within one task are listed per family below; no single winner is declared from a one-task gap.
- **Best offload (generative): LFM2.5-24B-A2B UD-Q4_K_XL, 8K cap — 59.2%** (retrieval 0% is an 8K-cap artifact, not a model score). Flint IQ2_XXS has no full score (aborted on swap; smoke 89.5% only, NOT a score).
- **Best classifier:** no single winner — Clef 27B Q4 for accuracy/calibration (choice 100%, score 100%, ECE 0.029, 2.4s), Clef-flash Q4 for on-GPU accuracy (choice 100%, 346ms), d1-2B Q4 for speed + score-MAE (56ms, MAE 0.083). See the classifier section.
- **Best long-horizon (100K+): Qwen3.5-9B Q4_K_M q4_0 KV — 0.875 (7/8)** (both hard aggregation tasks exact). 32K rank does NOT predict 100K rank: Spark best-at-32K falls to 0.50 at 100K, MiniCPM best to 0.19. See the long-horizon section.
- **Best KV per family** (best variant per KV type; full per-variant rows below):
  - Spark-X2.6-4B — FP16: IQ3_M 91.5%; q4_0: Q5_K_S 89.9%; q8_0: Q4_K_L 90.2%
  - Spark-X2.6-1.7B — FP16: Q6_K 81.3%; q4_0: Q8_0 81.0%; q8_0: Q5_K_S 79.8%
  - Bolt E4B — FP16: UD-Q5_K_XL 88.2%; q4_0: UD-IQ3_XXS 89.1%; q8_0: UD-Q4_K_XL 89.1%
  - LFM3-1.7B — FP16: IQ4_NL 86.3%; q4_0: Q5_K_M 85.1%; q8_0: Q5_K_S 84.4%
  - MiniCPM-V 4.7 1B — FP16: IQ4_XS 74.5%; q4_0: Q4_K_S 72.4%; q8_0: IQ4_XS 72.9%
  - MiniCPM-V 4.7 1B — q4_0: Q5_K_M 72.7%; q8_0: Q5_K_M 68.6%
  - Dory 1.0 4B — q4_0: Q5_K_M 87.5%; q8_0: Q5_K_M 88.7%
  - Qwen3.5-9B — FP16: Q4_K_M 86.7%
  - LFM2.5-8B-A1B — FP16: UD-Q4_K_M 56.1%
  - LFM2.5-1.2B — FP16: Q8_0 65.2%
  - LFM2.5-24B-A2B (offload) — FP16: UD-Q4_K_XL 59.2%

## Generative leaderboard (71 tasks, 32K primary)

### Spark-X2.6-4B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_M.gguf (2.23 GB) | IQ3_M | FP16 | 32,768 | 4,003 / 8,192 | 32,768 | 4 | **91.5%** | 94.7 | 100.0 | 87.5 | 100.0 | 50.0 | 100.0 | 100.0 | 4.02s | 15/37/44 | error 1 | `cards/card_spark-x2.6-4b-iq3m-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_K_L.gguf (2.81 GB) | Q4_K_L | q8_0 | 32,768 | not recorded | 32,768 | 4 | **90.2%** | 89.5 | 90.0 | 87.5 | 100.0 | 57.1 | 100.0 | 100.0 | 4.56s | 15/38/47 | error 1 | `cards/card_spark-x2.6-4b-q4kl-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_M.gguf (2.23 GB) | IQ3_M | q8_0 | 32,768 | 3,337 / 8,192 | 32,768 | 4 | **89.9%** | 94.7 | 100.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.55s | 15/34/41 | error 1 | `cards/card_spark-x2.6-4b-iq3m-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q5_K_S.gguf (2.88 GB) | Q5_K_S | q4_0 | 32,768 | 3,541 / 8,192 | 32,768 | 4 | **89.9%** | 94.7 | 100.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.32s | 15/40/45 | error 1 | `cards/card_spark-x2.6-4b-q5ks-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6-4B | Oct 2026 | Spark-X2.6-4B-Q8_0.gguf (4.38 GB) | Q8_0 | q4_0 | 32,768 | 4,959 / 8,192 | 32,768 | 4 | **89.4%** | 87.7 | 100.0 | 87.5 | 100.0 | 50.0 | 100.0 | 100.0 | 5.48s | 12/36/50 | error 1 | `cards/card_spark-x2.6-4b-q8-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6-4B | Oct 2026 | Spark-X2.6-4B-Q4_K_M.gguf (3.54 GB) | Q4_K_M | q8_0 | 32,768 | 3,937 / 8,192 | 32,768 | 4 | **89.1%** | 94.7 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 100.0 | 4.41s | 15/39/46 | error 1 | `cards/card_spark-x2.6-4b-q4km-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q6_K_S.gguf (3.45 GB) | Q6_K_S | q4_0 | 32,768 | 4,091 / 8,192 | 32,768 | 4 | **89.0%** | 89.5 | 90.0 | 87.5 | 100.0 | 50.0 | 100.0 | 100.0 | 4.97s | 13/36/48 | error 1 | `cards/card_spark-x2.6-4b-q6ks-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q6_K.gguf (3.38 GB) | Q6_K | q4_0 | 32,768 | 4,019 / 8,192 | 32,768 | 4 | **88.4%** | 94.7 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.85s | 14/36/49 | error 1 | `cards/card_spark-x2.6-4b-q6k-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_1.gguf (2.64 GB) | Q4_1 | q4_0 | 32,768 | 3,317 / 8,192 | 32,768 | 4 | **87.9%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 3.80s | 17/46/61 | error 1 | `cards/card_spark-x2.6-4b-q41-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_K_L.gguf (2.81 GB) | Q4_K_L | FP16 | 32,768 | not recorded | 32,768 | 4 | **87.9%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.15s | 16/41/49 | error 1 | `cards/card_spark-x2.6-4b-q4kl-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q5_K_M.gguf (2.98 GB) | Q5_K_M | q4_0 | 32,768 | 3,637 / 8,192 | 32,768 | 4 | **87.9%** | 89.5 | 90.0 | 87.5 | 100.0 | 57.1 | 87.5 | 100.0 | 4.46s | 15/39/45 | error 1 | `cards/card_spark-x2.6-4b-q5km-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ4_NL.gguf (2.62 GB) | IQ4_NL | FP16 | 32,768 | 4,373 / 8,192 | 32,768 | 4 | **87.8%** | 89.5 | 100.0 | 87.5 | 100.0 | 57.1 | 87.5 | 83.3 | 4.02s | 17/46/57 | error 1 | `cards/card_spark-x2.6-4b-iq4nl-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6-4B | Oct 2026 | Spark-X2.6-4B-Q4_K_M.gguf (3.54 GB) | Q4_K_M | q4_0 | 32,768 | 3,527 / 8,192 | 32,768 | 4 | **87.6%** | 84.2 | 90.0 | 87.5 | 100.0 | 57.1 | 100.0 | 100.0 | 4.49s | 14/39/47 | error 1 | `cards/card_spark-x2.6-4b-q4km-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q6_K.gguf (3.38 GB) | Q6_K | q8_0 | 32,768 | 4,429 / 8,192 | 32,768 | 4 | **87.5%** | 89.5 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 100.0 | 4.74s | 14/36/48 | error 1 | `cards/card_spark-x2.6-4b-q6k-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q6_K.gguf (3.38 GB) | Q6_K | FP16 | 32,768 | 5,095 / 8,192 | 32,768 | 4 | **87.5%** | 89.5 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 100.0 | 4.62s | 14/38/51 | error 1 | `cards/card_spark-x2.6-4b-q6k-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q6_K_L.gguf (3.78 GB) | Q6_K_L | q8_0 | 32,768 | 4,811 / 8,192 | 32,768 | 4 | **87.5%** | 89.5 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 100.0 | 5.21s | 13/35/47 | error 1 | `cards/card_spark-x2.6-4b-q6kl-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_M.gguf (2.23 GB) | IQ3_M | q4_0 | 32,768 | 2,927 / 8,192 | 32,768 | 4 | **87.4%** | 94.7 | 100.0 | 87.5 | 83.3 | 50.0 | 75.0 | 100.0 | 4.41s | 15/35/42 | error 1 | `cards/card_spark-x2.6-4b-iq3m-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_1.gguf (2.64 GB) | Q4_1 | FP16 | 32,768 | 4,393 / 8,192 | 32,768 | 4 | **87.4%** | 94.7 | 90.0 | 87.5 | 66.7 | 57.1 | 100.0 | 100.0 | 3.93s | 18/49/64 | error 1 | `cards/card_spark-x2.6-4b-q41-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q4_K_S.gguf (2.43 GB) | Q4_K_S | q8_0 | 32,768 | 3,521 / 8,192 | 32,768 | 4 | **87.4%** | 94.7 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 83.3 | 4.57s | 17/29/48 | error 1 | `cards/card_spark-x2.6-4b-q4ks-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q4_K_S.gguf (2.43 GB) | Q4_K_S | FP16 | 32,768 | 4,187 / 8,192 | 32,768 | 4 | **87.4%** | 94.7 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 83.3 | 3.79s | 17/45/50 | error 1 | `cards/card_spark-x2.6-4b-q4ks-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q3_K_L.gguf (2.39 GB) | Q3_K_L | q4_0 | 32,768 | 3,077 / 8,192 | 32,768 | 4 | **87.3%** | 84.2 | 100.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.53s | 15/37/43 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-q3kl-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q3_K_L.gguf (2.39 GB) | Q3_K_L | q8_0 | 32,768 | 3,487 / 8,192 | 32,768 | 4 | **87.3%** | 89.5 | 100.0 | 87.5 | 83.3 | 57.1 | 100.0 | 83.3 | 4.44s | 15/36/42 | error 1 | `cards/card_spark-x2.6-4b-q3kl-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_0.gguf (2.41 GB) | Q4_0 | q4_0 | 32,768 | 3,097 / 8,192 | 32,768 | 4 | **87.2%** | 89.5 | 100.0 | 87.5 | 66.7 | 50.0 | 100.0 | 100.0 | 3.95s | 17/46/59 | error 1 | `cards/card_spark-x2.6-4b-q40-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_0.gguf (2.41 GB) | Q4_0 | q8_0 | 32,768 | 3,507 / 8,192 | 32,768 | 4 | **87.2%** | 89.5 | 100.0 | 87.5 | 66.7 | 50.0 | 100.0 | 100.0 | 3.73s | 17/46/58 | error 1 | `cards/card_spark-x2.6-4b-q40-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_XS.gguf (1.91 GB) | IQ3_XS | q8_0 | 32,768 | 3,031 / 8,192 | 32,768 | 4 | **87.1%** | 94.7 | 90.0 | 87.5 | 100.0 | 50.0 | 87.5 | 83.3 | 4.43s | 15/32/40 | error 1 | `cards/card_spark-x2.6-4b-iq3xs-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ4_NL.gguf (2.62 GB) | IQ4_NL | q4_0 | 32,768 | 3,297 / 8,192 | 32,768 | 4 | **87.1%** | 89.5 | 100.0 | 87.5 | 83.3 | 50.0 | 87.5 | 100.0 | 4.18s | 16/43/55 | error 1 | `cards/card_spark-x2.6-4b-iq4nl-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ4_NL.gguf (2.62 GB) | IQ4_NL | q8_0 | 32,768 | 3,707 / 8,192 | 32,768 | 4 | **87.1%** | 89.5 | 100.0 | 87.5 | 100.0 | 50.0 | 87.5 | 83.3 | 4.00s | 16/42/53 | error 1 | `cards/card_spark-x2.6-4b-iq4nl-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q3_K_L.gguf (2.39 GB) | Q3_K_L | FP16 | 32,768 | 4,153 / 8,192 | 32,768 | 4 | **87.1%** | 89.5 | 100.0 | 87.5 | 100.0 | 50.0 | 87.5 | 83.3 | 4.29s | 15/39/45 | error 1 | `cards/card_spark-x2.6-4b-q3kl-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q6_K_L.gguf (3.78 GB) | Q6_K_L | q4_0 | 32,768 | 4,401 / 8,192 | 32,768 | 4 | **86.8%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 5.31s | 13/36/49 | error 1 | `cards/card_spark-x2.6-4b-q6kl-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q6_K_S.gguf (3.45 GB) | Q6_K_S | q8_0 | 32,768 | 4,501 / 8,192 | 32,768 | 4 | **86.8%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.93s | 14/35/46 | error 1 | `cards/card_spark-x2.6-4b-q6ks-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q6_K_S.gguf (3.45 GB) | Q6_K_S | FP16 | 32,768 | 5,167 / 8,192 | 32,768 | 4 | **86.8%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 4.69s | 14/38/49 | error 1 | `cards/card_spark-x2.6-4b-q6ks-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ4_XS.gguf (2.34 GB) | IQ4_XS | q4_0 | 32,768 | 3,027 / 8,192 | 32,768 | 4 | **86.7%** | 84.2 | 90.0 | 87.5 | 100.0 | 50.0 | 87.5 | 100.0 | 3.75s | 18/42/47 | error 1 | `cards/card_spark-x2.6-4b-iq4xs-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ4_XS.gguf (2.34 GB) | IQ4_XS | FP16 | 32,768 | 4,103 / 8,192 | 32,768 | 4 | **86.3%** | 89.5 | 90.0 | 87.5 | 100.0 | 57.1 | 87.5 | 83.3 | 3.79s | 19/45/49 | error 1 | `cards/card_spark-x2.6-4b-iq4xs-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_1.gguf (2.64 GB) | Q4_1 | q8_0 | 32,768 | 3,727 / 8,192 | 32,768 | 4 | **86.2%** | 89.5 | 90.0 | 87.5 | 66.7 | 50.0 | 100.0 | 100.0 | 3.77s | 18/45/59 | error 1 | `cards/card_spark-x2.6-4b-q41-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q6_K_L.gguf (3.78 GB) | Q6_K_L | FP16 | 32,768 | 5,477 / 8,192 | 32,768 | 4 | **85.9%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 100.0 | 4.99s | 13/37/50 | error 1 | `cards/card_spark-x2.6-4b-q6kl-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_0.gguf (2.41 GB) | Q4_0 | FP16 | 32,768 | 4,173 / 8,192 | 32,768 | 4 | **85.8%** | 84.2 | 100.0 | 87.5 | 66.7 | 57.1 | 100.0 | 100.0 | 3.65s | 18/49/62 | error 1 | `cards/card_spark-x2.6-4b-q40-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q5_K_M.gguf (2.98 GB) | Q5_K_M | q8_0 | 32,768 | 4,047 / 8,192 | 32,768 | 4 | **85.8%** | 89.5 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 83.3 | 4.35s | 15/39/45 | error 1 | `cards/card_spark-x2.6-4b-q5km-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q4_K_L.gguf (2.81 GB) | Q4_K_L | q4_0 | 32,768 | not recorded | 32,768 | 4 | **85.7%** | 89.5 | 90.0 | 87.5 | 66.7 | 50.0 | 100.0 | 100.0 | 4.42s | 15/39/47 | error 1 | `cards/card_spark-x2.6-4b-q4kl-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q5_K_S.gguf (2.88 GB) | Q5_K_S | q8_0 | 32,768 | 3,951 / 8,192 | 32,768 | 4 | **85.6%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 83.3 | 4.26s | 15/39/43 | error 1 | `cards/card_spark-x2.6-4b-q5ks-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q3_K_M.gguf (2.17 GB) | Q3_K_M | q8_0 | 32,768 | 3,271 / 8,192 | 32,768 | 4 | **85.4%** | 94.7 | 90.0 | 87.5 | 83.3 | 50.0 | 87.5 | 83.3 | 4.22s | 15/37/44 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-q3km-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6-4B | Oct 2026 | Spark-X2.6-4B-Q8_0.gguf (4.38 GB) | Q8_0 | q8_0 | 32,768 | 5,369 / 8,192 | 32,768 | 4 | **85.2%** | 84.2 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 100.0 | 5.39s | 12/36/49 | error 1 | `cards/card_spark-x2.6-4b-q8-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q5_K_M.gguf (2.98 GB) | Q5_K_M | FP16 | 32,768 | 4,713 / 8,192 | 32,768 | 4 | **85.1%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 100.0 | 83.3 | 4.20s | 16/41/46 | error 1 | `cards/card_spark-x2.6-4b-q5km-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ4_XS.gguf (2.34 GB) | IQ4_XS | q8_0 | 32,768 | 3,437 / 8,192 | 32,768 | 4 | **85.0%** | 89.5 | 90.0 | 87.5 | 100.0 | 57.1 | 75.0 | 83.3 | 3.85s | 18/42/46 | error 1 | `cards/card_spark-x2.6-4b-iq4xs-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q3_K_M.gguf (2.17 GB) | Q3_K_M | FP16 | 32,768 | 3,937 / 8,192 | 32,768 | 4 | **84.6%** | 89.5 | 90.0 | 87.5 | 83.3 | 57.1 | 87.5 | 83.3 | 4.07s | 16/39/47 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-q3km-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q5_K_S.gguf (2.88 GB) | Q5_K_S | FP16 | 32,768 | 4,617 / 8,192 | 32,768 | 4 | **84.3%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 100.0 | 83.3 | 4.10s | 16/41/46 | error 1 | `cards/card_spark-x2.6-4b-q5ks-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_XS.gguf (1.91 GB) | IQ3_XS | FP16 | 32,768 | 3,697 / 8,192 | 32,768 | 4 | **83.9%** | 89.5 | 90.0 | 87.5 | 83.3 | 50.0 | 87.5 | 83.3 | 4.75s | 15/34/43 | error 1 | `cards/card_spark-x2.6-4b-iq3xs-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_XS.gguf (1.91 GB) | IQ3_XS | q4_0 | 32,768 | 2,621 / 8,192 | 32,768 | 4 | **82.4%** | 89.5 | 80.0 | 87.5 | 83.3 | 50.0 | 87.5 | 83.3 | 4.43s | 15/33/41 | error 1 | `cards/card_spark-x2.6-4b-iq3xs-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_XXS.gguf (1.80 GB) | IQ3_XXS | q8_0 | 32,768 | 2,925 / 8,192 | 32,768 | 4 | **81.9%** | 78.9 | 100.0 | 87.5 | 83.3 | 42.9 | 75.0 | 100.0 | 4.14s | 16/35/41 | error 1 | `cards/card_spark-x2.6-4b-iq3xxs-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_XXS.gguf (1.80 GB) | IQ3_XXS | FP16 | 32,768 | 3,591 / 8,192 | 32,768 | 4 | **81.9%** | 78.9 | 100.0 | 87.5 | 83.3 | 42.9 | 75.0 | 100.0 | 3.97s | 16/37/43 | error 1 | `cards/card_spark-x2.6-4b-iq3xxs-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q3_K_M.gguf (2.17 GB) | Q3_K_M | q4_0 | 32,768 | 2,861 / 8,192 | 32,768 | 4 | **80.5%** | 78.9 | 90.0 | 87.5 | 83.3 | 50.0 | 75.0 | 83.3 | 4.33s | 15/37/44 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-q3km-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q3_K_S.gguf (1.90 GB) | Q3_K_S | q8_0 | 32,768 | 3,023 / 8,192 | 32,768 | 4 | **79.6%** | 73.7 | 90.0 | 87.5 | 100.0 | 50.0 | 75.0 | 83.3 | 4.33s | 16/36/43 | error 3 · looped 2 | `cards/card_spark-x2.6-4b-q3ks-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q3_K_S.gguf (1.90 GB) | Q3_K_S | FP16 | 32,768 | 3,689 / 8,192 | 32,768 | 4 | **79.6%** | 73.7 | 90.0 | 87.5 | 100.0 | 50.0 | 75.0 | 83.3 | 4.10s | 16/38/45 | error 3 · looped 2 | `cards/card_spark-x2.6-4b-q3ks-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q3_K_S.gguf (1.90 GB) | Q3_K_S | q4_0 | 32,768 | 2,613 / 8,192 | 32,768 | 4 | **79.4%** | 73.7 | 100.0 | 87.5 | 83.3 | 50.0 | 75.0 | 83.3 | 4.36s | 15/36/43 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-q3ks-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ3_XXS.gguf (1.80 GB) | IQ3_XXS | q4_0 | 32,768 | 2,515 / 8,192 | 32,768 | 4 | **78.4%** | 73.7 | 90.0 | 87.5 | 66.7 | 50.0 | 75.0 | 100.0 | 4.39s | 15/35/41 | error 1 | `cards/card_spark-x2.6-4b-iq3xxs-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ2_M.gguf (1.57 GB) | IQ2_M | FP16 | 32,768 | 3,367 / 8,192 | 32,768 | 4 | **73.5%** | 73.7 | 60.0 | 87.5 | 66.7 | 42.9 | 100.0 | 83.3 | 4.06s | 18/38/43 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-iq2m-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ2_M.gguf (1.57 GB) | IQ2_M | q8_0 | 32,768 | 2,701 / 8,192 | 32,768 | 4 | **71.9%** | 78.9 | 50.0 | 87.5 | 50.0 | 42.9 | 100.0 | 83.3 | 4.22s | 17/36/41 | error 1 | `cards/card_spark-x2.6-4b-iq2m-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-IQ2_M.gguf (1.57 GB) | IQ2_M | q4_0 | 32,768 | 2,291 / 8,192 | 32,768 | 4 | **71.8%** | 78.9 | 60.0 | 87.5 | 50.0 | 42.9 | 100.0 | 66.7 | 3.95s | 17/35/40 | error 1 · looped 1 | `cards/card_spark-x2.6-4b-iq2m-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q2_K.gguf (1.61 GB) | Q2_K | q4_0 | 32,768 | 2,333 / 8,192 | 32,768 | 4 | **57.7%** | 31.6 | 90.0 | 62.5 | 83.3 | 28.6 | 87.5 | 33.3 | 3.41s | 19/32/42 | error 1 · looped 3 · timeout 4 | `cards/card_spark-x2.6-4b-q2k-bartowski-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q2_K.gguf (1.61 GB) | Q2_K | q8_0 | 32,768 | 2,743 / 8,192 | 32,768 | 4 | **57.6%** | 52.6 | 80.0 | 62.5 | 50.0 | 28.6 | 87.5 | 33.3 | 3.22s | 20/36/44 | error 1 · looped 1 · max_turns 1 · timeout 3 | `cards/card_spark-x2.6-4b-q2k-bartowski-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B-Q2_K.gguf (1.61 GB) | Q2_K | FP16 | 32,768 | 3,409 / 8,192 | 32,768 | 4 | **53.0%** | 42.1 | 80.0 | 62.5 | 50.0 | 21.4 | 75.0 | 33.3 | 3.13s | 21/38/46 | error 1 · looped 2 · timeout 2 | `cards/card_spark-x2.6-4b-q2k-bartowski.png` | on-GPU ≤12B |
| Spark-X2.6 4B | Oct 2026 | Spark-X2.6-4B.Q4_K_S.gguf (2.43 GB) | Q4_K_S | q4_0 | 32,768 | 3,111 / 8,192 | 32,768 | 4 | **0.0%** | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | error 79 | `cards/card_spark-x2.6-4b-q4ks-xhtoken-kvq4.png` | on-GPU ≤12B |

### Spark-X2.6-1.7B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q6_K.gguf (1.41 GB) | Q6_K | FP16 | 32,768 | 2,185 / 8,192 | 32,768 | 4 | **81.3%** | 78.9 | 100.0 | 87.5 | 66.7 | 42.9 | 75.0 | 100.0 | 2.24s | 29/70/85 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q6k-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6-1.7B | Oct 2026 | Spark-X2.6-1.7B-Q8_0.gguf (1.82 GB) | Q8_0 | q4_0 | 32,768 | 2,157 / 8,192 | 32,768 | 4 | **81.0%** | 80.7 | 90.0 | 87.5 | 50.0 | 64.3 | 87.5 | 100.0 | 3.69s | 23/67/81 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q8-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q5_K_S.gguf (1.22 GB) | Q5_K_S | q8_0 | 32,768 | 1,743 / 8,192 | 32,768 | 4 | **79.8%** | 89.5 | 90.0 | 87.5 | 50.0 | 71.4 | 75.0 | 66.7 | 2.23s | 30/69/78 | error 1 | `cards/card_spark-x2.6-1.7b-q5ks-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6-1.7B | Oct 2026 | Spark-X2.6-1.7B-Q8_0.gguf (1.82 GB) | Q8_0 | q8_0 | 32,768 | 2,317 / 8,192 | 32,768 | 4 | **79.5%** | 84.2 | 100.0 | 87.5 | 50.0 | 57.1 | 87.5 | 66.7 | 3.54s | 29/76/99 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q8-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6-1.7B | Oct 2026 | Spark-X2.6-1.7B-Q4_K_M.gguf (1.77 GB) | Q4_K_M | q4_0 | 32,768 | 1,595 / 8,192 | 32,768 | 4 | **78.5%** | 78.9 | 90.0 | 87.5 | 66.7 | 57.1 | 75.0 | 83.3 | 3.25s | 4/31/28 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q4km-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q6_K.gguf (1.41 GB) | Q6_K | q8_0 | 32,768 | 1,927 / 8,192 | 32,768 | 4 | **78.5%** | 78.9 | 80.0 | 87.5 | 66.7 | 50.0 | 75.0 | 100.0 | 2.43s | 28/65/81 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q6k-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q5_K_S.gguf (1.22 GB) | Q5_K_S | q4_0 | 32,768 | 1,583 / 8,192 | 32,768 | 4 | **78.1%** | 73.7 | 90.0 | 87.5 | 66.7 | 64.3 | 75.0 | 66.7 | 2.33s | 29/71/78 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q5ks-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6-1.7B | Oct 2026 | Spark-X2.6-1.7B-Q4_K_M.gguf (1.77 GB) | Q4_K_M | q8_0 | 32,768 | 1,755 / 8,192 | 32,768 | 4 | **75.3%** | 73.7 | 90.0 | 87.5 | 33.3 | 57.1 | 75.0 | 100.0 | 0.19s† | 7/24/32 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q4km-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q3_K_M.gguf (0.94 GB) | Q3_K_M | q8_0 | 32,768 | 1,479 / 8,192 | 32,768 | 4 | **74.7%** | 89.5 | 50.0 | 87.5 | 33.3 | 64.3 | 75.0 | 100.0 | 1.81s | 22/67/98 | error 1 | `cards/card_spark-x2.6-1.7b-q3km-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q5_K_S.gguf (1.22 GB) | Q5_K_S | FP16 | 32,768 | 2,001 / 8,192 | 32,768 | 4 | **73.5%** | 78.9 | 90.0 | 87.5 | 50.0 | 57.1 | 75.0 | 50.0 | 2.02s | 32/74/82 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q5ks-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q4_K_S.gguf (1.04 GB) | Q4_K_S | q8_0 | 32,768 | 1,581 / 8,192 | 32,768 | 4 | **72.2%** | 73.7 | 90.0 | 75.0 | 33.3 | 57.1 | 75.0 | 83.3 | 1.60s | 40/96/110 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q4ks-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q6_K.gguf (1.41 GB) | Q6_K | q4_0 | 32,768 | 1,767 / 8,192 | 32,768 | 4 | **72.1%** | 78.9 | 90.0 | 87.5 | 16.7 | 42.9 | 75.0 | 83.3 | 1.97s | 26/58/58 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q6k-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q3_K_L.gguf (1.02 GB) | Q3_K_L | q8_0 | 32,768 | 1,557 / 8,192 | 32,768 | 4 | **71.7%** | 73.7 | 70.0 | 87.5 | 50.0 | 64.3 | 62.5 | 83.3 | 0.29s† | 26/71/103 | error 1 | `cards/card_spark-x2.6-1.7b-q3kl-xhtoken-kvq8.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q4_K_S.gguf (1.04 GB) | Q4_K_S | q4_0 | 32,768 | 1,421 / 8,192 | 32,768 | 4 | **71.4%** | 63.2 | 90.0 | 75.0 | 33.3 | 57.1 | 87.5 | 83.3 | 1.77s | 39/59/83 | error 1 · looped 1 | `cards/card_spark-x2.6-1.7b-q4ks-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q3_K_M.gguf (0.94 GB) | Q3_K_M | q4_0 | 32,768 | 1,319 / 8,192 | 32,768 | 4 | **71.2%** | 78.9 | 50.0 | 87.5 | 50.0 | 50.0 | 75.0 | 83.3 | 1.99s | 23/64/94 | error 1 · looped 1 | `cards/card_spark-x2.6-1.7b-q3km-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q4_K_S.gguf (1.04 GB) | Q4_K_S | FP16 | 32,768 | 1,839 / 8,192 | 32,768 | 4 | **70.7%** | 68.4 | 80.0 | 75.0 | 50.0 | 50.0 | 75.0 | 83.3 | 1.48s | 43/102/116 | error 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q4ks-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q3_K_L.gguf (1.02 GB) | Q3_K_L | FP16 | 32,768 | 1,815 / 8,192 | 32,768 | 4 | **68.7%** | 68.4 | 60.0 | 87.5 | 50.0 | 64.3 | 62.5 | 83.3 | 0.27s† | 23/68/105 | error 1 · looped 2 | `cards/card_spark-x2.6-1.7b-q3kl-xhtoken.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q3_K_L.gguf (1.02 GB) | Q3_K_L | q4_0 | 32,768 | 1,397 / 8,192 | 32,768 | 4 | **68.4%** | 68.4 | 50.0 | 87.5 | 66.7 | 50.0 | 62.5 | 83.3 | 0.27s† | 27/81/69 | error 1 | `cards/card_spark-x2.6-1.7b-q3kl-xhtoken-kvq4.png` | on-GPU ≤12B |
| Spark-X2.6 1.7B | Oct 2026 | Spark-X2.6-1.7B.Q3_K_M.gguf (0.94 GB) | Q3_K_M | FP16 | 32,768 | 1,737 / 8,192 | 32,768 | 4 | **68.4%** | 68.4 | 50.0 | 87.5 | 33.3 | 64.3 | 75.0 | 100.0 | 2.11s | 34/89/109 | error 1 · looped 1 · max_turns 1 | `cards/card_spark-x2.6-1.7b-q3km-xhtoken.png` | on-GPU ≤12B |

### Bolt E4B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bolt E4B | Oct 23 2026 | — | UD-IQ3_XXS | q4_0 | 32,768 | not recorded | 32,768 | 4 | **89.1%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 87.5 | 100.0 | 4.93s | 13/32/43 | none | `cards/card_bolt-e4b-udiq3xxs-kvq4.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q4_K_XL | q8_0 | 32,768 | not recorded | 32,768 | 4 | **89.1%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 87.5 | 100.0 | 5.03s | 13/38/46 | none | `cards/card_bolt-e4b-udq4xl-kvq8.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q4_K_XL | q4_0 | 32,768 | not recorded | 32,768 | 4 | **88.6%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 100.0 | 5.23s | 13/38/46 | none | `cards/card_bolt-e4b-udq4xl-kvq4.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q5_K_XL | q4_0 | 32,768 | not recorded | 32,768 | 4 | **88.6%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 100.0 | 5.74s | 11/36/47 | none | `cards/card_bolt-e4b-udq5xl-kvq4.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q5_K_XL | q8_0 | 32,768 | not recorded | 32,768 | 4 | **88.2%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 87.5 | 83.3 | 5.67s | 12/35/46 | none | `cards/card_bolt-e4b-udq5xl-kvq8.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q5_K_XL | FP16 | 32,768 | not recorded | 32,768 | 4 | **88.2%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 87.5 | 83.3 | 5.33s | 12/37/48 | none | `cards/card_bolt-e4b-udq5xl.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q4_K_XL | FP16 | 32,768 | not recorded | 32,768 | 4 | **87.9%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 75.0 | 100.0 | 4.81s | 14/40/48 | none | `cards/card_bolt-e4b-udq4xl.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-Q2_K_XL | q8_0 | 32,768 | not recorded | 32,768 | 4 | **87.4%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 87.5 | 83.3 | 4.78s | 14/32/43 | none | `cards/card_bolt-e4b-udq2xl-kvq8.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-Q2_K_XL | FP16 | 32,768 | not recorded | 32,768 | 4 | **87.4%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 87.5 | 83.3 | 4.78s | 14/34/44 | none | `cards/card_bolt-e4b-udq2xl.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-Q3_K_XL | FP16 | 32,768 | not recorded | 32,768 | 4 | **87.4%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 87.5 | 83.3 | 3.99s | 17/43/50 | none | `cards/card_bolt-e4b-udq3xl.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-IQ2_M | FP16 | 32,768 | not recorded | 32,768 | 4 | **87.2%** | 94.7 | 100.0 | 62.5 | 100.0 | 57.1 | 87.5 | 100.0 | 4.36s | 15/34/43 | error 1 | `cards/card_bolt-e4b-udiq2m.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q6_K_XL | q4_0 | 32,768 | not recorded | 32,768 | 4 | **86.9%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 83.3 | 6.15s | 11/36/53 | none | `cards/card_bolt-e4b-udq6xl-kvq4.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q6_K_XL | q8_0 | 32,768 | not recorded | 32,768 | 4 | **86.9%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 83.3 | 6.01s | 11/36/53 | none | `cards/card_bolt-e4b-udq6xl-kvq8.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q6_K_XL | FP16 | 32,768 | not recorded | 32,768 | 4 | **86.9%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 83.3 | 5.73s | 11/38/56 | none | `cards/card_bolt-e4b-udq6xl.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | — | UD-Q8_K_XL | FP16 | 32,768 | not recorded | 32,768 | 4 | **86.9%** | 94.7 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 83.3 | 5.91s | 11/37/55 | none | `cards/card_bolt-e4b-udq8xl.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf (6.18 GB) | Q4_K_M | q8_0 | 32,768 | 3,745 / 8,192 | 32,768 | 4 | **86.7%** | 94.7 | 100.0 | 75.0 | 100.0 | 50.0 | 87.5 | 83.3 | 4.76s | 14/41/50 | none | `cards/card_bolt-e4b-q4km-kvq8.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-IQ2_M | q4_0 | 32,768 | not recorded | 32,768 | 4 | **86.6%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 62.5 | 100.0 | 4.77s | 14/33/42 | error 2 | `cards/card_bolt-e4b-udiq2m-kvq4.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-IQ3_XXS | q8_0 | 32,768 | not recorded | 32,768 | 4 | **86.2%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 75.0 | 83.3 | 4.86s | 14/31/42 | none | `cards/card_bolt-e4b-udiq3xxs-kvq8.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-Q3_K_XL | q4_0 | 32,768 | not recorded | 32,768 | 4 | **86.2%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 75.0 | 83.3 | 4.25s | 16/41/49 | none | `cards/card_bolt-e4b-udq3xl-kvq4.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-Q3_K_XL | q8_0 | 32,768 | not recorded | 32,768 | 4 | **86.2%** | 94.7 | 100.0 | 75.0 | 100.0 | 57.1 | 75.0 | 83.3 | 4.09s | 16/41/48 | none | `cards/card_bolt-e4b-udq3xl-kvq8.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-IQ3_XXS | FP16 | 32,768 | not recorded | 32,768 | 4 | **85.6%** | 94.7 | 100.0 | 62.5 | 100.0 | 57.1 | 87.5 | 83.3 | 4.76s | 14/33/44 | error 2 | `cards/card_bolt-e4b-udiq3xxs.png` | on-GPU ≤12B |
| Nemotron 3.5 Bolt E4B | Oct 23 2026 | Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf (6.18 GB) | Q4_K_M | q4_0 | 32,768 | 3,573 / 8,192 | 32,768 | 4 | **85.5%** | 94.7 | 100.0 | 75.0 | 100.0 | 50.0 | 75.0 | 83.3 | 4.87s | 13/41/50 | none | `cards/card_bolt-e4b-q4km-kvq4.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-Q2_K_XL | q4_0 | 32,768 | not recorded | 32,768 | 4 | **85.4%** | 89.5 | 100.0 | 75.0 | 100.0 | 64.3 | 75.0 | 83.3 | 4.96s | 13/32/43 | none | `cards/card_bolt-e4b-udq2xl-kvq4.png` | on-GPU ≤12B |
| Bolt E4B | Oct 23 2026 | — | UD-IQ2_M | q8_0 | 32,768 | not recorded | 32,768 | 4 | **84.3%** | 94.7 | 100.0 | 62.5 | 83.3 | 57.1 | 75.0 | 100.0 | 4.67s | 14/33/42 | error 1 | `cards/card_bolt-e4b-udiq2m-kvq8.png` | on-GPU ≤12B |

### LFM3-1.7B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LFM3 1.7B | Oct 24 2026 | — | IQ4_NL | FP16 | 32,768 | 1,687 / 8,192 | 32,768 | 4 | **86.3%** | 84.2 | 90.0 | 87.5 | 100.0 | 57.1 | 87.5 | 100.0 | 0.24s† | 35/81/112 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq4nl-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q5_K_M.gguf (1.26 GB) | Q5_K_M | q4_0 | 32,768 | 1,557 / 8,192 | 32,768 | 4 | **85.1%** | 84.2 | 90.0 | 87.5 | 100.0 | 57.1 | 75.0 | 100.0 | 1.60s | 42/87/96 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q5km-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q4_0 | FP16 | 32,768 | 1,631 / 8,192 | 32,768 | 4 | **84.7%** | 84.2 | 100.0 | 75.0 | 100.0 | 57.1 | 75.0 | 100.0 | 1.40s | 45/100/110 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q40-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q5_K_M.gguf (1.26 GB) | Q5_K_M | FP16 | 32,768 | 1,823 / 8,192 | 32,768 | 4 | **84.6%** | 84.2 | 90.0 | 87.5 | 100.0 | 64.3 | 62.5 | 100.0 | 1.58s | 40/87/97 | error 1 · looped 1 | `cards/card_lfm3-1.7b-q5km.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_M | q4_0 | 32,768 | 1,239 / 8,192 | 32,768 | 4 | **84.5%** | 89.5 | 90.0 | 87.5 | 83.3 | 64.3 | 62.5 | 100.0 | 1.64s | 40/54/57 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq3m-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q5_K_S.gguf (1.23 GB) | Q5_K_S | q8_0 | 32,768 | 1,633 / 8,192 | 32,768 | 4 | **84.4%** | 84.2 | 90.0 | 87.5 | 100.0 | 50.0 | 75.0 | 100.0 | 1.59s | 41/87/96 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q5ks-prithiv-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q3_K_S | FP16 | 32,768 | 1,397 / 8,192 | 32,768 | 4 | **84.2%** | 89.5 | 90.0 | 62.5 | 100.0 | 57.1 | 87.5 | 100.0 | 1.82s | 39/77/89 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q3ks-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_M | q8_0 | 32,768 | 1,341 / 8,192 | 32,768 | 4 | **83.9%** | 84.2 | 80.0 | 87.5 | 83.3 | 64.3 | 87.5 | 100.0 | 1.22s | 9/54/74 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-iq3m-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q6_K_L | FP16 | 32,768 | 2,131 / 8,192 | 32,768 | 4 | **83.4%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 75.0 | 100.0 | 1.80s | 36/77/90 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q6kl-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q4_K_M.gguf (1.10 GB) | Q4_K_M | q8_0 | 32,768 | 1,507 / 8,192 | 32,768 | 4 | **83.2%** | 84.2 | 90.0 | 75.0 | 100.0 | 57.1 | 75.0 | 100.0 | 1.50s | 43/90/101 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q4km-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ4_NL | q8_0 | 32,768 | 1,523 / 8,192 | 32,768 | 4 | **83.1%** | 84.2 | 90.0 | 87.5 | 100.0 | 50.0 | 62.5 | 100.0 | 0.24s† | 37/93/104 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq4nl-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q4_0 | q4_0 | 32,768 | 1,365 / 8,192 | 32,768 | 4 | **83.1%** | 84.2 | 100.0 | 75.0 | 83.3 | 57.1 | 75.0 | 100.0 | 1.43s | 47/100/127 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q40-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q5_K_S.gguf (1.23 GB) | Q5_K_S | FP16 | 32,768 | 1,797 / 8,192 | 32,768 | 4 | **83.1%** | 84.2 | 90.0 | 87.5 | 100.0 | 50.0 | 62.5 | 100.0 | 1.52s | 42/88/98 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q5ks-prithiv.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q4_K_S.gguf (1.06 GB) | Q4_K_S | q4_0 | 32,768 | 1,363 / 8,192 | 32,768 | 4 | **83.0%** | 84.2 | 90.0 | 75.0 | 83.3 | 71.4 | 75.0 | 100.0 | 1.46s | 44/92/102 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q4ks-prithiv-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q4_K_S.gguf (1.06 GB) | Q4_K_S | q8_0 | 32,768 | 1,465 / 8,192 | 32,768 | 4 | **82.9%** | 78.9 | 90.0 | 75.0 | 100.0 | 57.1 | 87.5 | 100.0 | 1.48s | 44/91/102 | error 1 · looped 1 | `cards/card_lfm3-1.7b-q4ks-prithiv-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q6_K.gguf (1.43 GB) | Q6_K | q8_0 | 32,768 | 1,819 / 8,192 | 32,768 | 4 | **82.7%** | 84.2 | 90.0 | 87.5 | 83.3 | 50.0 | 75.0 | 100.0 | 1.69s | 38/83/96 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q6k-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q6_K.gguf (1.43 GB) | Q6_K | FP16 | 32,768 | 1,983 / 8,192 | 32,768 | 4 | **82.7%** | 84.2 | 90.0 | 87.5 | 83.3 | 50.0 | 75.0 | 100.0 | 1.69s | 39/82/98 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q6k.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ4_XS | q4_0 | 32,768 | 1,307 / 8,192 | 32,768 | 4 | **82.6%** | 78.9 | 90.0 | 87.5 | 100.0 | 35.7 | 87.5 | 100.0 | 1.51s | 48/98/96 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq4xs-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q4_K_S.gguf (1.06 GB) | Q4_K_S | FP16 | 32,768 | 1,629 / 8,192 | 32,768 | 4 | **82.4%** | 78.9 | 90.0 | 75.0 | 100.0 | 64.3 | 75.0 | 100.0 | 1.52s | 44/93/104 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q4ks-prithiv.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q5_K_S.gguf (1.23 GB) | Q5_K_S | q4_0 | 32,768 | 1,531 / 8,192 | 32,768 | 4 | **82.4%** | 78.9 | 90.0 | 87.5 | 83.3 | 50.0 | 87.5 | 100.0 | 1.55s | 42/80/97 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q5ks-prithiv-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q4_K_M.gguf (1.10 GB) | Q4_K_M | q4_0 | 32,768 | 1,405 / 8,192 | 32,768 | 4 | **82.3%** | 84.2 | 90.0 | 75.0 | 83.3 | 64.3 | 75.0 | 100.0 | 1.52s | 43/89/100 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q4km-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_M | FP16 | 32,768 | 1,505 / 8,192 | 32,768 | 4 | **82.2%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 62.5 | 100.0 | 1.62s | 40/78/94 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-iq3m-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q5_K_M.gguf (1.26 GB) | Q5_K_M | q8_0 | 32,768 | 1,659 / 8,192 | 32,768 | 4 | **82.2%** | 84.2 | 90.0 | 87.5 | 100.0 | 57.1 | 62.5 | 83.3 | 1.58s | 40/88/96 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q5km-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q6_K_L | q8_0 | 32,768 | 1,967 / 8,192 | 32,768 | 4 | **82.2%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 62.5 | 100.0 | 1.82s | 36/77/90 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q6kl-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q6_K_S | q8_0 | 32,768 | 1,847 / 8,192 | 32,768 | 4 | **82.2%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 62.5 | 100.0 | 1.76s | 37/81/94 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q6ks-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ4_NL | q4_0 | 32,768 | 1,421 / 8,192 | 32,768 | 4 | **82.1%** | 78.9 | 90.0 | 87.5 | 100.0 | 42.9 | 75.0 | 100.0 | 1.62s | 46/99/110 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq4nl-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q3_K_L.gguf (0.97 GB) | Q3_K_L | q8_0 | 32,768 | 1,381 / 8,192 | 32,768 | 4 | **81.9%** | 84.2 | 80.0 | 87.5 | 83.3 | 57.1 | 75.0 | 100.0 | 1.87s | 41/84/104 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q3kl-prithiv-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q3_K_M.gguf (0.91 GB) | Q3_K_M | FP16 | 32,768 | 1,495 / 8,192 | 32,768 | 4 | **81.6%** | 89.5 | 80.0 | 87.5 | 83.3 | 50.0 | 62.5 | 100.0 | 1.79s | 41/82/103 | error 1 · looped 1 | `cards/card_lfm3-1.7b-q3km-prithiv.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q6_K.gguf (1.43 GB) | Q6_K | q4_0 | 32,768 | 1,717 / 8,192 | 32,768 | 4 | **81.5%** | 84.2 | 90.0 | 87.5 | 83.3 | 50.0 | 62.5 | 100.0 | 1.69s | 38/85/101 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q6k-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q4_1 | FP16 | 32,768 | 1,715 / 8,192 | 32,768 | 4 | **81.3%** | 84.2 | 90.0 | 62.5 | 100.0 | 57.1 | 75.0 | 100.0 | 0.23s† | 29/87/104 | error 1 · looped 1 | `cards/card_lfm3-1.7b-q41-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q3_K_M.gguf (0.91 GB) | Q3_K_M | q4_0 | 32,768 | 1,229 / 8,192 | 32,768 | 4 | **81.2%** | 84.2 | 80.0 | 87.5 | 83.3 | 50.0 | 75.0 | 100.0 | 1.69s | 42/42/101 | error 1 · looped 1 | `cards/card_lfm3-1.7b-q3km-prithiv-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_XXS | q8_0 | 32,768 | 1,203 / 8,192 | 32,768 | 4 | **81.1%** | 84.2 | 90.0 | 75.0 | 100.0 | 35.7 | 75.0 | 100.0 | 1.69s | 40/76/89 | error 1 | `cards/card_lfm3-1.7b-iq3xxs-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q4_0 | q8_0 | 32,768 | 1,467 / 8,192 | 32,768 | 4 | **81.1%** | 84.2 | 100.0 | 75.0 | 83.3 | 50.0 | 62.5 | 100.0 | 1.41s | 45/98/115 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q40-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q6_K_S | FP16 | 32,768 | 2,011 / 8,192 | 32,768 | 4 | **80.9%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 50.0 | 100.0 | 1.75s | 38/82/96 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q6ks-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q8_0.gguf (1.85 GB) | Q8_0 | q4_0 | 32,768 | 2,117 / 8,192 | 32,768 | 4 | **80.9%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 50.0 | 100.0 | 1.94s | 33/81/81 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q8-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q8_0.gguf (1.85 GB) | Q8_0 | q8_0 | 32,768 | 2,219 / 8,192 | 32,768 | 4 | **80.9%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 50.0 | 100.0 | 1.97s | 33/78/95 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q8-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q8_0.gguf (1.85 GB) | Q8_0 | FP16 | 32,768 | 2,383 / 8,192 | 32,768 | 4 | **80.9%** | 84.2 | 90.0 | 87.5 | 83.3 | 57.1 | 50.0 | 100.0 | 2.00s | 33/78/95 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q3_K_S | q8_0 | 32,768 | 1,233 / 8,192 | 32,768 | 4 | **80.6%** | 89.5 | 90.0 | 62.5 | 83.3 | 50.0 | 75.0 | 100.0 | 1.84s | 39/76/94 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q3ks-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q3_K_L.gguf (0.97 GB) | Q3_K_L | FP16 | 32,768 | 1,545 / 8,192 | 32,768 | 4 | **80.3%** | 84.2 | 80.0 | 87.5 | 66.7 | 57.1 | 75.0 | 100.0 | 1.87s | 41/85/105 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q3kl-prithiv.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q2_K | q8_0 | 32,768 | 1,127 / 8,192 | 32,768 | 4 | **80.0%** | 84.2 | 80.0 | 87.5 | 100.0 | 50.0 | 62.5 | 83.3 | 1.39s | 48/81/105 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q2k-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q3_K_L.gguf (0.97 GB) | Q3_K_L | q4_0 | 32,768 | 1,279 / 8,192 | 32,768 | 4 | **80.0%** | 84.2 | 80.0 | 87.5 | 83.3 | 50.0 | 62.5 | 100.0 | 0.47s† | 47/80/99 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q3kl-prithiv-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q4_1 | q4_0 | 32,768 | 1,449 / 8,192 | 32,768 | 4 | **80.0%** | 89.5 | 90.0 | 62.5 | 83.3 | 57.1 | 62.5 | 100.0 | 0.32s† | 42/86/114 | error 1 | `cards/card_lfm3-1.7b-q41-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q4_1 | q8_0 | 32,768 | 1,551 / 8,192 | 32,768 | 4 | **80.0%** | 89.5 | 90.0 | 62.5 | 83.3 | 57.1 | 62.5 | 100.0 | 0.27s† | 35/84/109 | error 1 | `cards/card_lfm3-1.7b-q41-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ4_XS | FP16 | 32,768 | 1,573 / 8,192 | 32,768 | 4 | **79.7%** | 78.9 | 90.0 | 75.0 | 100.0 | 50.0 | 62.5 | 100.0 | 0.24s† | 27/65/98 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq4xs-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q3_K_S | q4_0 | 32,768 | 1,131 / 8,192 | 32,768 | 4 | **79.7%** | 89.5 | 80.0 | 75.0 | 83.3 | 50.0 | 62.5 | 100.0 | 1.63s | 40/73/95 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q3ks-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B-Q4_K_M.gguf (1.10 GB) | Q4_K_M | FP16 | 32,768 | not recorded | 32,768 | 4 | **79.6%** | 84.2 | 90.0 | 75.0 | 83.3 | 50.0 | 62.5 | 100.0 | 1.53s | 43/90/103 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q4km.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_XXS | FP16 | 32,768 | 1,367 / 8,192 | 32,768 | 4 | **79.5%** | 78.9 | 90.0 | 75.0 | 100.0 | 35.7 | 75.0 | 100.0 | 1.66s | 39/76/93 | error 1 | `cards/card_lfm3-1.7b-iq3xxs-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q6_K_L | q4_0 | 32,768 | 1,865 / 8,192 | 32,768 | 4 | **79.5%** | 84.2 | 90.0 | 87.5 | 83.3 | 42.9 | 50.0 | 100.0 | 1.87s | 36/70/89 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-q6kl-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_XS | FP16 | 32,768 | 1,397 / 8,192 | 32,768 | 4 | **79.4%** | 78.9 | 80.0 | 75.0 | 100.0 | 50.0 | 75.0 | 100.0 | 1.92s | 40/77/96 | error 1 · looped 1 | `cards/card_lfm3-1.7b-iq3xs-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | LFM3-1.7B.Q3_K_M.gguf (0.91 GB) | Q3_K_M | q8_0 | 32,768 | 1,331 / 8,192 | 32,768 | 4 | **79.2%** | 84.2 | 70.0 | 87.5 | 83.3 | 57.1 | 62.5 | 100.0 | 1.70s | 42/85/105 | error 1 · max_turns 1 | `cards/card_lfm3-1.7b-q3km-prithiv-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q2_K | FP16 | 32,768 | 1,291 / 8,192 | 32,768 | 4 | **78.4%** | 78.9 | 80.0 | 87.5 | 83.3 | 50.0 | 62.5 | 100.0 | 1.38s | 48/80/106 | error 1 · looped 1 · max_turns 2 | `cards/card_lfm3-1.7b-q2k-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_XS | q8_0 | 32,768 | 1,233 / 8,192 | 32,768 | 4 | **78.2%** | 78.9 | 80.0 | 75.0 | 100.0 | 50.0 | 62.5 | 100.0 | 1.92s | 39/75/94 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-iq3xs-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ4_XS | q8_0 | 32,768 | 1,409 / 8,192 | 32,768 | 4 | **78.0%** | 78.9 | 90.0 | 75.0 | 83.3 | 50.0 | 62.5 | 100.0 | 1.44s | 46/59/98 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq4xs-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q6_K_S | q4_0 | 32,768 | 1,745 / 8,192 | 32,768 | 4 | **78.0%** | 84.2 | 90.0 | 87.5 | 66.7 | 57.1 | 37.5 | 100.0 | 1.82s | 40/78/87 | error 1 · max_turns 1 | `cards/card_lfm3-1.7b-q6ks-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ2_M | FP16 | 32,768 | 1,243 / 8,192 | 32,768 | 4 | **76.9%** | 94.7 | 60.0 | 87.5 | 83.3 | 42.9 | 37.5 | 100.0 | 1.64s | 40/74/98 | error 1 · looped 1 | `cards/card_lfm3-1.7b-iq2m-bartowski.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ2_M | q8_0 | 32,768 | 1,079 / 8,192 | 32,768 | 4 | **76.8%** | 89.5 | 50.0 | 87.5 | 100.0 | 42.9 | 50.0 | 100.0 | 1.64s | 40/80/99 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq2m-bartowski-kvq8.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | Q2_K | q4_0 | 32,768 | 1,025 / 8,192 | 32,768 | 4 | **76.7%** | 78.9 | 70.0 | 75.0 | 100.0 | 50.0 | 62.5 | 100.0 | 2.27s | 65/82/105 | error 1 · looped 2 | `cards/card_lfm3-1.7b-q2k-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_XXS | q4_0 | 32,768 | 1,101 / 8,192 | 32,768 | 4 | **76.1%** | 68.4 | 90.0 | 75.0 | 100.0 | 35.7 | 62.5 | 100.0 | 1.23s | 57/79/97 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq3xxs-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ3_XS | q4_0 | 32,768 | 1,131 / 8,192 | 32,768 | 4 | **73.7%** | 78.9 | 70.0 | 87.5 | 83.3 | 42.9 | 37.5 | 100.0 | 2.90s | 80/73/75 | error 1 · looped 1 · max_turns 1 | `cards/card_lfm3-1.7b-iq3xs-bartowski-kvq4.png` | on-GPU ≤12B |
| LFM3 1.7B | Oct 24 2026 | — | IQ2_M | q4_0 | 32,768 | 977 / 8,192 | 32,768 | 4 | **63.6%** | 89.5 | 40.0 | 75.0 | 50.0 | 28.6 | 50.0 | 66.7 | 1.36s | 58/123/116 | error 1 · looped 2 | `cards/card_lfm3-1.7b-iq2m-bartowski-kvq4.png` | on-GPU ≤12B |

### MiniCPM-V 4.7 1B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ4_XS.gguf (0.64 GB) | IQ4_XS | FP16 | 32,768 | 1,219 / 8,192 | 32,768 | 4 | **74.5%** | 78.9 | 90.0 | 62.5 | 66.7 | 50.0 | 62.5 | 100.0 | 0.34s† | 38/126/158 | error 1 · looped 1 | `cards/card_minicpmv47-1b-iq4xs.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ4_XS.gguf (0.64 GB) | IQ4_XS | q8_0 | 32,768 | 1,075 / 8,192 | 32,768 | 4 | **72.9%** | 73.7 | 90.0 | 62.5 | 66.7 | 50.0 | 62.5 | 100.0 | 0.27s† | 43/118/158 | error 1 · looped 1 · max_turns 1 | `cards/card_minicpmv47-1b-iq4xs-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_K_S.gguf (0.65 GB) | Q4_K_S | q4_0 | 32,768 | 979 / 8,192 | 32,768 | 4 | **72.4%** | 68.4 | 90.0 | 62.5 | 66.7 | 50.0 | 62.5 | 100.0 | 0.24s† | 47/132/135 | error 1 · looped 3 | `cards/card_minicpmv47-1b-q4ks-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_0.gguf (0.74 GB) | Q5_0 | FP16 | 32,768 | 1,275 / 8,192 | 32,768 | 4 | **71.4%** | 68.4 | 90.0 | 62.5 | 50.0 | 50.0 | 75.0 | 100.0 | 0.23s† | 38/141/177 | error 1 · looped 1 · max_turns 1 | `cards/card_minicpmv47-1b-q50.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ4_XS.gguf (0.64 GB) | IQ4_XS | q4_0 | 32,768 | 979 / 8,192 | 32,768 | 4 | **71.2%** | 73.7 | 90.0 | 62.5 | 66.7 | 50.0 | 62.5 | 83.3 | 0.18s† | 47/123/151 | error 1 | `cards/card_minicpmv47-1b-iq4xs-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_0.gguf (0.64 GB) | Q4_0 | FP16 | 32,768 | 1,215 / 8,192 | 32,768 | 4 | **69.5%** | 78.9 | 60.0 | 62.5 | 50.0 | 50.0 | 75.0 | 100.0 | 0.36s† | 78/115/125 | error 1 · looped 1 | `cards/card_minicpmv47-1b-q40.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_1.gguf (0.79 GB) | Q5_1 | q8_0 | 32,768 | 1,161 / 8,192 | 32,768 | 4 | **69.1%** | 73.7 | 80.0 | 62.5 | 50.0 | 42.9 | 75.0 | 83.3 | 1.52s | 50/168/140 | error 1 | `cards/card_minicpmv47-1b-q51-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ4_NL.gguf (0.66 GB) | IQ4_NL | q4_0 | 32,768 | 989 / 8,192 | 32,768 | 4 | **68.9%** | 68.4 | 80.0 | 62.5 | 50.0 | 57.1 | 62.5 | 100.0 | 0.32s† | 57/139/161 | error 1 · looped 2 | `cards/card_minicpmv47-1b-iq4nl-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ4_NL.gguf (0.66 GB) | IQ4_NL | q8_0 | 32,768 | 1,085 / 8,192 | 32,768 | 4 | **68.5%** | 73.7 | 80.0 | 62.5 | 50.0 | 50.0 | 50.0 | 100.0 | 0.38s† | 57/151/169 | error 1 · looped 3 | `cards/card_minicpmv47-1b-iq4nl-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_0.gguf (0.64 GB) | Q4_0 | q8_0 | 32,768 | 1,071 / 8,192 | 32,768 | 4 | **68.4%** | 68.4 | 70.0 | 75.0 | 50.0 | 42.9 | 75.0 | 83.3 | 0.25s† | 44/112/149 | error 1 · looped 2 | `cards/card_minicpmv47-1b-q40-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_0.gguf (0.74 GB) | Q5_0 | q8_0 | 32,768 | 1,131 / 8,192 | 32,768 | 4 | **68.3%** | 73.7 | 70.0 | 62.5 | 50.0 | 50.0 | 75.0 | 83.3 | 0.22s† | 44/158/173 | error 1 · looped 3 | `cards/card_minicpmv47-1b-q50-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_1.gguf (0.79 GB) | Q5_1 | FP16 | 32,768 | 1,305 / 8,192 | 32,768 | 4 | **68.1%** | 68.4 | 80.0 | 62.5 | 50.0 | 50.0 | 62.5 | 100.0 | 1.85s | 55/116/174 | error 1 | `cards/card_minicpmv47-1b-q51.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_1.gguf (0.79 GB) | Q5_1 | q4_0 | 32,768 | 1,065 / 8,192 | 32,768 | 4 | **68.0%** | 68.4 | 90.0 | 62.5 | 50.0 | 50.0 | 62.5 | 83.3 | 0.36s† | 50/129/127 | error 1 | `cards/card_minicpmv47-1b-q51-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_K_S.gguf (0.65 GB) | Q4_K_S | FP16 | 32,768 | 1,219 / 8,192 | 32,768 | 4 | **67.9%** | 68.4 | 80.0 | 62.5 | 66.7 | 42.9 | 50.0 | 100.0 | 0.21s† | 42/146/185 | error 1 · looped 1 | `cards/card_minicpmv47-1b-q4ks.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_0.gguf (0.74 GB) | Q5_0 | q4_0 | 32,768 | 1,035 / 8,192 | 32,768 | 4 | **67.6%** | 63.2 | 80.0 | 62.5 | 50.0 | 50.0 | 62.5 | 100.0 | 0.19s† | 44/136/163 | error 1 · looped 2 · max_turns 1 | `cards/card_minicpmv47-1b-q50-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_K_S.gguf (0.74 GB) | Q5_K_S | q8_0 | 32,768 | 1,131 / 8,192 | 32,768 | 4 | **67.0%** | 78.9 | 70.0 | 62.5 | 50.0 | 42.9 | 75.0 | 66.7 | 0.21s† | 24/65/139 | error 1 | `cards/card_minicpmv47-1b-q5ks-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_K_S.gguf (0.65 GB) | Q4_K_S | q8_0 | 32,768 | 1,075 / 8,192 | 32,768 | 4 | **66.9%** | 68.4 | 70.0 | 62.5 | 66.7 | 42.9 | 50.0 | 100.0 | 0.21s† | 47/138/162 | error 1 · looped 1 | `cards/card_minicpmv47-1b-q4ks-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_1.gguf (0.69 GB) | Q4_1 | q8_0 | 32,768 | 1,101 / 8,192 | 32,768 | 4 | **66.3%** | 73.7 | 70.0 | 62.5 | 50.0 | 42.9 | 50.0 | 100.0 | 0.29s† | 53/135/170 | error 1 · looped 5 | `cards/card_minicpmv47-1b-q41-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ4_NL.gguf (0.66 GB) | IQ4_NL | FP16 | 32,768 | 1,229 / 8,192 | 32,768 | 4 | **65.8%** | 63.2 | 80.0 | 62.5 | 50.0 | 50.0 | 50.0 | 100.0 | 0.39s† | 51/132/191 | error 1 · looped 3 | `cards/card_minicpmv47-1b-iq4nl.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_1.gguf (0.69 GB) | Q4_1 | q4_0 | 32,768 | 1,005 / 8,192 | 32,768 | 4 | **64.9%** | 63.2 | 70.0 | 62.5 | 50.0 | 50.0 | 50.0 | 100.0 | 0.35s† | 57/140/181 | error 1 · looped 6 · max_turns 1 | `cards/card_minicpmv47-1b-q41-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_K_S.gguf (0.74 GB) | Q5_K_S | q4_0 | 32,768 | 1,035 / 8,192 | 32,768 | 4 | **64.3%** | 63.2 | 70.0 | 62.5 | 50.0 | 42.9 | 62.5 | 83.3 | 0.20s† | 32/69/121 | error 1 · looped 1 | `cards/card_minicpmv47-1b-q5ks-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_K_S.gguf (0.74 GB) | Q5_K_S | FP16 | 32,768 | 1,275 / 8,192 | 32,768 | 4 | **63.1%** | 68.4 | 70.0 | 62.5 | 50.0 | 42.9 | 62.5 | 66.7 | 0.34s† | 40/122/122 | error 1 · looped 1 · max_turns 1 | `cards/card_minicpmv47-1b-q5ks.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ3_M.gguf (0.56 GB) | IQ3_M | q8_0 | 32,768 | 1,027 / 8,192 | 32,768 | 4 | **62.9%** | 63.2 | 60.0 | 62.5 | 66.7 | 42.9 | 62.5 | 83.3 | 2.03s | 54/115/156 | error 1 · looped 1 | `cards/card_minicpmv47-1b-iq3m-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_1.gguf (0.69 GB) | Q4_1 | FP16 | 32,768 | 1,245 / 8,192 | 32,768 | 4 | **61.5%** | 57.9 | 70.0 | 62.5 | 50.0 | 42.9 | 50.0 | 100.0 | 0.37s† | 86/147/177 | error 1 · looped 8 | `cards/card_minicpmv47-1b-q41.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_0.gguf (0.64 GB) | Q4_0 | q4_0 | 32,768 | 975 / 8,192 | 32,768 | 4 | **60.5%** | 63.2 | 60.0 | 75.0 | 16.7 | 50.0 | 62.5 | 83.3 | 0.37s† | 66/145/126 | error 1 · looped 2 | `cards/card_minicpmv47-1b-q40-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ3_M.gguf (0.56 GB) | IQ3_M | FP16 | 32,768 | 1,171 / 8,192 | 32,768 | 4 | **59.6%** | 57.9 | 60.0 | 62.5 | 50.0 | 42.9 | 62.5 | 83.3 | 2.03s | 57/119/162 | error 1 · looped 1 | `cards/card_minicpmv47-1b-iq3m.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ3_XS.gguf (0.55 GB) | IQ3_XS | q8_0 | 32,768 | 1,017 / 8,192 | 32,768 | 4 | **59.0%** | 57.9 | 60.0 | 62.5 | 50.0 | 42.9 | 62.5 | 66.7 | 1.86s | 52/103/136 | error 1 | `cards/card_minicpmv47-1b-iq3xs-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ3_M.gguf (0.56 GB) | IQ3_M | q4_0 | 32,768 | 931 / 8,192 | 32,768 | 4 | **58.6%** | 52.6 | 60.0 | 62.5 | 50.0 | 42.9 | 62.5 | 83.3 | 1.98s | 53/115/159 | error 1 | `cards/card_minicpmv47-1b-iq3m-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ3_XS.gguf (0.55 GB) | IQ3_XS | q4_0 | 32,768 | 921 / 8,192 | 32,768 | 4 | **56.6%** | 68.4 | 60.0 | 62.5 | 16.7 | 42.9 | 62.5 | 50.0 | 1.62s | 44/92/125 | error 1 | `cards/card_minicpmv47-1b-iq3xs-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-IQ3_XS.gguf (0.55 GB) | IQ3_XS | FP16 | 32,768 | 1,161 / 8,192 | 32,768 | 4 | **55.7%** | 52.6 | 60.0 | 62.5 | 33.3 | 42.9 | 62.5 | 50.0 | 1.87s | 52/103/137 | error 1 · looped 1 | `cards/card_minicpmv47-1b-iq3xs.png` | on-GPU ≤12B |

### MiniCPM-V 4.7 1B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_K_M.gguf (0.75 GB) | Q5_K_M | q4_0 | 32,768 | 1,045 / 8,192 | 32,768 | 4 | **72.7%** | 71.9 | 100.0 | 62.5 | 50.0 | 42.9 | 75.0 | 100.0 | 1.87s | 38/97/106 | error 1 | `cards/card_minicpm-v-4.7-1b-q5km-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q6_K.gguf (0.84 GB) | Q6_K | q4_0 | 32,768 | 1,093 / 8,192 | 32,768 | 4 | **69.3%** | 73.7 | 90.0 | 62.5 | 50.0 | 42.9 | 50.0 | 100.0 | 1.80s | 41/106/129 | error 1 | `cards/card_minicpm-v-4.7-1b-q6k-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q5_K_M.gguf (0.75 GB) | Q5_K_M | q8_0 | 32,768 | 1,141 / 8,192 | 32,768 | 4 | **68.6%** | 63.2 | 90.0 | 62.5 | 50.0 | 42.9 | 75.0 | 100.0 | 0.17s† | 28/80/126 | error 1 · looped 1 | `cards/card_minicpm-v-4.7-1b-q5km-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q6_K.gguf (0.84 GB) | Q6_K | q8_0 | 32,768 | 1,189 / 8,192 | 32,768 | 4 | **68.3%** | 75.4 | 80.0 | 62.5 | 50.0 | 42.9 | 50.0 | 100.0 | 1.79s | 40/107/134 | error 1 | `cards/card_minicpm-v-4.7-1b-q6k-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q8_0.gguf (1.08 GB) | Q8_0 | q8_0 | 32,768 | 1,363 / 8,192 | 32,768 | 4 | **67.4%** | 68.4 | 80.0 | 62.5 | 50.0 | 42.9 | 62.5 | 100.0 | 2.20s | 46/127/158 | error 1 | `cards/card_minicpm-v-4.7-1b-q8-kvq8.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q8_0.gguf (1.08 GB) | Q8_0 | q4_0 | 32,768 | 1,267 / 8,192 | 32,768 | 4 | **66.3%** | 63.2 | 70.0 | 62.5 | 50.0 | 50.0 | 75.0 | 100.0 | 2.25s | 45/127/104 | error 1 | `cards/card_minicpm-v-4.7-1b-q8-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_K_M.gguf (0.67 GB) | Q4_K_M | q4_0 | 32,768 | 999 / 8,192 | 32,768 | 4 | **65.0%** | 59.6 | 70.0 | 62.5 | 66.7 | 42.9 | 62.5 | 100.0 | 0.26s† | 43/100/133 | error 1 · max_turns 1 | `cards/card_minicpm-v-4.7-1b-q4km-kvq4.png` | on-GPU ≤12B |
| MiniCPM-V 4.7 1B | Oct 12 2026 | MiniCPM-V-4_7-1B-Q4_K_M.gguf (0.67 GB) | Q4_K_M | q8_0 | 32,768 | 1,095 / 8,192 | 32,768 | 4 | **61.6%** | 59.6 | 70.0 | 62.5 | 50.0 | 42.9 | 62.5 | 83.3 | 0.21s† | 39/88/137 | error 1 · looped 2 | `cards/card_minicpm-v-4.7-1b-q4km-kvq8.png` | on-GPU ≤12B |

### Dory 1.0 4B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dory 1.0 4B | Oct 2026 | NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf (3.67 GB) | Q5_K_M | q8_0 | 32,768 | 6,113 / 8,192 | 32,768 | 4 | **88.7%** | 89.5 | 100.0 | 87.5 | 100.0 | 50.0 | 87.5 | 100.0 | 8.60s | 8/23/27 | error 1 | `cards/card_dory-1.0-4b-q5km-kvq8.png` | on-GPU ≤12B |
| Dory 1.0 4B | Oct 2026 | NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf (3.67 GB) | Q5_K_M | q4_0 | 32,768 | 4,733 / 8,192 | 32,768 | 4 | **87.5%** | 94.7 | 90.0 | 87.5 | 100.0 | 50.0 | 75.0 | 100.0 | 8.61s | 8/23/26 | error 1 | `cards/card_dory-1.0-4b-q5km-kvq4.png` | on-GPU ≤12B |

### Qwen3.5-9B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3.5-9B | Feb–Mar 2026 | Qwen3.5-9B-Q4_K_M.gguf (5.68 GB) | Q4_K_M | FP16 | 32,768 | 6,527 / 8,192 | 32,768 | 4 | **86.7%** | 89.5 | 90.0 | 87.5 | 100.0 | 57.1 | 75.0 | 100.0 | 6.55s | 10/26/29 | error 1 | `cards/card_qwen35-9b-q4km.png` | on-GPU ≤12B |

### LFM2.5-8B-A1B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LFM2.5-8B-A1B | May 28 2026 | LFM2.5-8B-A1B-UD-Q4_K_M.gguf (5.32 GB) | UD-Q4_K_M | FP16 | 32,768 | 5,657 / 8,192 | 32,768 | 4 | **56.1%** | 84.2 | 50.0 | 25.0 | 100.0 | 0.0 | 12.5 | 83.3 | 2.34s | 0/1/14 | empty_response 29 · error 1 | `cards/card_lfm25-8b-a1b-udq4km.png` | on-GPU ≤12B |

### LFM2.5-1.2B

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LFM2.5-1.2B | Jan 2026 | LFM2.5-1.2B-Instruct-Q8_0.gguf (1.25 GB) | Q8_0 | FP16 | 32,768 | 1,781 / 8,192 | 32,768 | 4 | **65.2%** | 63.2 | 70.0 | 87.5 | 50.0 | 42.9 | 50.0 | 83.3 | 0.30s† | 44/125/194 | error 1 | `cards/card_lfm25-1.2b-q8_0.png` | on-GPU ≤12B |
| LFM2.5-1.2B | Jan 2026 | LFM2.5-1.2B-Instruct-Q4_K_M.gguf (0.73 GB) | Q4_K_M | FP16 | 32,768 | 1,289 / 8,192 | 32,768 | 4 | **63.5%** | 57.9 | 50.0 | 87.5 | 66.7 | 42.9 | 62.5 | 83.3 | 0.97s | 72/176/210 | error 1 | `cards/card_lfm25-1.2b-q4km.png` | on-GPU ≤12B |

### LFM2.5-24B-A2B (offload)

| Model | Release | GGUF file (size) | Quant | KV | Ctx | VRAM used / total | KV pool | Max subagents | Full % | Tool | Struct | Retr | Coding | Instr | Adv | Chains | TTFT | tok/s 1/4/8 | Failure modes | Card | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LFM2.5-24B-A2B | Oct 2026 | LFM2.5-24B-A2B-UD-Q4_K_XL.gguf (14.88 GB) | UD-Q4_K_XL | FP16 | 8,192 | 1,293 / 8,192 | 8,192 | 1 | **59.2%** | 84.2 | 70.0 | 0.0 | 100.0 | 21.4 | 12.5 | 100.0 | 11.44s | 0/0/0 | empty_response 21 · error 5 · looped 1 · max_turns 1 | `cards/card_lfm25-24b-a2b-udq4xl.png` | offload |

## Classifier leaderboard (SEPARATE — never merged into generative %)

48-task v1.0 benchmark (`classifier-bench/`): routing/topic choice, urgency score (4-level), noul @0.5. Metrics: choice accuracy, noul accuracy, score exact-level accuracy + MAE, ECE (10 bins), multiclass Brier, mean/p95 latency, abstention (confidence < 0.6), option-order flip rate (0–26). No composite % is invented.

| Model | Quant | Choice | Noul | Score exact / MAE | ECE / Brier | Latency mean/p95 | Abstain | Flips |
|---|---|---|---|---|---|---|---|---|
| Clef-flash 9B (on-GPU) | Q4_K_M | 100% | 100% | 91.67% / 0.172 | 0.034 / 0.0015 | 346 / 497 ms | 2.08% | 0/26 |
| Clef 27B (offload, -ngl 20, 8K) | Q4_K_M | 100% | 100% | 100% / 0.105 | 0.029 / 0.0026 | 2424 / 2928 ms | 4.17% | 0/26 |
| d1-2B | Q4_K_M | 96.15% | 100% | 91.67% / 0.083 | 0.059 / 0.0348 | 56 / 71 ms | 8.33% | 0/26 |
| d1-2B | Q8_0 | 100% | 100% | 83.33% / 0.167 | 0.060 / 0.0259 | 50 / 67 ms | 6.25% | 0/26 |
| d1-3B | Q4_K_M | 96.15% | 100% | 91.67% / 0.231 | 0.088 / 0.0570 | 69 / 103 ms | 4.17% | 0/26 |
| d1-Omni-2B | Q8_0 | 96.15% | 90% | 91.67% / 0.083 | 0.112 / 0.0474 | 52 / 61 ms | 6.25% | 1/26 |
| d1-omni-600M | Q8_0 | 96.15% | 100% | 58.33% / 0.512 | 0.054 / 0.0318 | 39 / 51 ms | 8.33% | 1/26 |
| Laya 421M | Q8_0 | 88.46% | 100% | 50.00% / 0.682 | 0.112 / 0.1473 | 47 / 58 ms | 14.58% | 1/26 |

Notes: Clef-flash Q8_0 does-not-fit on-GPU (9.4 GB weights > 8 GB VRAM). d1-omni-600M, d1-Omni-2B, and Laya have NO Q4 GGUF (Q8_0 used). Clef vendor inference code defaults max_length 16,384 with silent trimming — benchmarks must pass max_length explicitly. Candidate identification, Oct 31: Julia-1 (SupersonicLabs/Julia-1, Sep 23 2026; GGUF Oct 1), Kev-4B (jaredpalmer/kev-4b, Sep 19 2026; GGUF Oct 1), Strands Decider (StrandsAgents, Oct 2026 variants), s1-llm-auto-router (system1models Oct 2 / decisionmodels Oct 15 2026), Sieve family (sthanika-ai, Oct 2026) all EXIST on HF, but their type (classifier vs generative), weights/format for decision serving, size, and PVE fit are NOT verified and they are NOT benched — do not assume them. 'lev' remains ambiguous (no confident classifier match).

## Routing suite (SEPARATE — 12 tasks, validated on 2 models)

| Model | Routing | Failure modes |
|---|---|---|
| Spark-X2.6-4B Q8_0 q4_0 (strong) | 12/12 (100%) | none |
| MiniCPM-V 4.7 1B Q4_K_M q4_0 (weak) | 8/12 (66.7%) | looped 1; wrong-tool-then-refuse, looped refusal, dropped 2nd hop ×2 |

Verdict: KEEP SEPARATE. Measures tool routing, a different skill from the 71-task generative suite; discrimination confirmed with interpretable failure modes.

## OCR suite (SEPARATE — 10 tasks, vision models ONLY)

| Model | OCR field score | Notes |
|---|---|---|
| MiniCPM-V 4.7 1B Q4_K_M + mmproj | 0.95 | 9/10 perfect; redacted 0.5 (computed a total instead of refusing) |
| LFM3-VL-2B Q4_K_M + mmproj | 0.90 | 9/10 perfect; redacted 0.0 (empty response) |

Verdict: KEEP SEPARATE. Both models refuse illegible input correctly, handle rotation/low-contrast/two-column. Text models are never scored here. LFM3-VL-2B is OCR-track only in this run.

## Long-horizon 100K+ suite (SEPARATE — 8 tasks, ~95K–100K prompt tokens)

Shared 71,438-word ledger; buried policies (exclude [INTERNAL] transfers; ISO dates); multi-hop sum, buried-policy total, retrieval at distance, multi-turn state, distractor, count, ISO date, amendment. Bench max_tokens 4096 = harness standard. Per-model prompt tokens recorded (tokenizer-dependent). Never overwrites 32K scores.

| Model | Context / KV | VRAM @102400 | Prompt tokens | LH score | Notes |
|---|---|---|---|---|---|
| Qwen3.5-9B Q4_K_M q4_0 KV | 102400 / q4_0 | 6,847 MiB (spare 1,345) | ~93.5K | **0.875 (7/8)** | 100K LEADER; both hard aggregation tasks exact; only multihop-sum empty; FP16 KV-OOM at 102400 |
| LFM3-1.7B IQ4_NL FP16 | 102400 / FP16 | 2,571 MiB | ~98.1K | 0.75 (6/8) | Failures are wrong values ($149K vs $164K; count 3 vs 7) |
| Spark-X2.6-4B IQ3_M FP16 | 102400 / FP16 | 6,519 MiB (spare 1,673) | ~100.6K | 0.50 (4/8) | Aggregation tasks empty (full reasoning, no answer); run-to-run unstable |
| MiniCPM-V 4.7 1B IQ4_XS FP16 | 102400 / FP16 | 2,103 MiB | ~93.5K | 0.1875 (1.5/8) | Near-total collapse; date policy violated; amendment took original budget |
| Dory 1.0 4B Q5_K_M q4_0 | 102400 / q4_0 | 6,909 MiB (spare 1,283) | 103.3K | does-not-fit | Tokenizer needs 103,328+ tokens > 102400 cap (clean 400s, server healthy). q8_0 KV also fails at 102400 (KV alloc OOM): Dory does-not-fit at 100K+ for both KVs |
| Bolt E4B Q4_K_M | 102400 req. / FP16 | 5,153 MiB | 93,154 | does-not-fit | Model context capped at 65,536 (training); prompt exceeds cap. Model-level cap (all Bolt quants share the architecture/config): Bolt does-not-fit at 100K+ as a model, not just Q4_K_M |
| Spark-X2.6-1.7B Q8_0 FP16 | 102400 / FP16 | 3,599 MiB (spare 4,593) | ~100.7K | 0.625 (5/8) | Pass multihop, multiturn, distractor, date, amendment. Fail (all EMPTY, fast ~36s): buried-total, distance, count. Beats Spark 4B best (0.50) at 100K |
| LFM2.5-8B-A1B UD-Q4_K_M FP16 | 102400 / FP16 | 6,549 MiB (spare 1,643) | ~98.1K | 0.1875 (1.5/8) | Pass amendment; distance partial 0.5. Fail: multihop refusal after 138s reasoning; buried/distractor/date EMPTY (~62s); multiturn 'I don't know'; count boxed 9 (truth 7). Genuine reasoning failures, not the 8B 71-task format artifact (LH reads content directly) |
| LFM2.5-1.2B Q8_0 FP16 | 102400 / FP16 | 2,673 MiB (spare 5,519) | ~100.7K | 0.0 (0/8) | Complete collapse, worst in the set: 6/8 EMPTY (fast); multihop EMPTY after 110.8s; count + date-policy echoed ledger boilerplate instead of answering |

Finding: 32K rank does NOT predict 100K rank. Best-per-model LH coverage is now complete (Qwen, LFM3, Spark 4B, Spark 1.7B, MiniCPM, LFM2.5-8B, LFM2.5-1.2B scored; Dory + Bolt does-not-fit with distinct reasons). Remaining per-variant LH rows (every other fitting quant/KV) are a documented continuation queue, not silently dropped (fit test: 102400 serve + spare ≥1 GiB + tokenizer prompt ≤ cap + model context cap ≥ prompt).

## 71-task audit (Oct 28, 2026)

Core 71 kept unchanged for comparability: overwhelmingly real subagent work (tool calls, error recovery, instruction following, long-context retrieval, structured output, coding, agent chains). Mock-domain tasks (flights, records) are real skill with synthetic data — flagged, not dropped. Weakest items are trivial-arithmetic discipline checks (defensible as tool-use probes). Harder / real-domain tasks belong in new separate suites (routing, OCR, long-horizon above), validated on ≥2 models before any merge decision.

## Future-proofing (scaling to bigger cards)

The same 71-task suite, per-quant × per-KV rows, and separate classifier/routing/OCR/long-horizon suites run unchanged on bigger cards: raise `-c` (32K → 64K → 102400+), keep `--kv-unified`, and re-derive KV pool (= cap) and max 8K subagents (= floor(pool/8192)). Quants that do-not-fit here (e.g. Clef-flash Q8_0, Bolt 74B-A9B, Granite Switch 4.1 8B at 32K) become first-class rows there; offload rows get a real context cap instead of an artifact. No AREO 3090 testing was done in this run (PVE 1070 Ti only, per directive).

## Pre-existing repo results (v0.3.1, NOT re-scored this run)

The v0.3.1 leaderboard below is reproduced verbatim from the previous LEADERBOARD.md (backed up as `LEADERBOARD.md.bak-v031`). These models were already tested before this run and were NOT re-run, re-carded, or merged into the rows above; their legacy card images remain in `results/cards/`. Scores here used the v0.3.1 methodology (Bonsai-2: 65 merged tasks).

| # | Model | Quant | Gauntlet % | Tests | tok/s (1 stream) |
|---|-------|-------|-----------:|------:|-----------------:|
| 🥇 | Gemma 4 · E4B | Q4_K_M | **87.9%** | 71 | 13.8 |
| 🥈 | MiniCPM-V 5 · 2B | Q8_0 | **87.7%** | 71 | 26.3 |
| 🥉 | Ternary Bonsai-2 · 27B | PTQ1_0 | **86.2%** | 65 | — |
| 4 | MiniCPM-V 5 · 2B | Q4_K_M | **85.6%** | 71 | 31.7 |
| 5 | Ornith 1.5 · 9B | Q4_K_M | **75.7%** | 71 | 10.2 |
| 6 | MiMo V2.6 · 9B | Q4_K_M | **75.3%** | 71 | 13.0 |
| 7 | Gemma 4 · 12B | UD-Q2_K_XL | **72.6%** | 71 | 7.0 |
| 8 | LFM 2.5 · 2.6B | Q8_0 | **69.9%** | 71 | 25.9 |
| 9 | LFM 2.5 · 2.6B | Q4_K_M | **69.6%** | 71 | 34.5 |
| 10 | Qwen 3.5 · 4B | Q4_K_M | **68.2%** | 71 | 15.6 |
| 11 | Gemma 4 · 12B | IQ3_XXS | **68.0%** | 71 | 6.5 |
| 12 | Sharp-Spark X2.5 · 4B | Q4_K_XL | **66.4%** | 71 | 16.7 |
| 13 | Gemma 3n · E4B | Q4_K_M | **56.3%** | 71 | 13.1 |

## Blocks and open decisions (for Tyler)

- Flint full suite: blocked on host RAM/swap (16 GB RAM, 8 GB swap); smoke 89.5% only. Needs a bigger host, a Flint-only swap waiver, or smoke-only status.
- Granite Switch 4.1 8B: does-not-fit 32K within the 1 GiB rule (spare 297 MiB). Needs a headroom relaxation, an 8K score, or a does-not-fit ruling.
- Thermal threshold: strict 80C caps probe-verified context at 32K (normal sustained load is 81–82C); applied deviation is hard abort at 84C. Needs a confirmed threshold.
- Score weighting: CLI 7-suite weights (cards/log) vs report.py 5-suite headline differ (example above). Needs a unification ruling; leaderboard uses card figures.
- Full KV expansion (q4_1, iq4_nl, q5_0, q5_1) for the older 39 variants: NOT assumed; needs a Tyler decision.
- Full re-runs of completed variants on the new build: NOT assumed (~40 full suites); needs explicit instruction. Completed variants keep their build's scores, labeled per card.
- GitHub push: gated on Tyler signing in on AREO via Hermes + separate approval. Everything here is local and push-ready.
- Card footer version discrepancy: footer says v0.3.1, code says 0.1.0, log says v0.4. Flagged, not silently picked.
