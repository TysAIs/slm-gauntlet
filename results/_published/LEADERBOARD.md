# SLM Gauntlet v0.3 — Leaderboard

All runs on a single GTX 1070 Ti (8 GB), zero offload, `-ngl 99`, seed 1, temp 0.
Gauntlet v0.3 = 71 tasks / 7 suites (adds instruction-hard, structured-hard, tooluse-hard).
Bonsai-2: 65 merged tasks across the 7 suites (ran before the hard-suite expansion).
Voxel Pagoda = headlessly-graded 3D voxel garden build (execution-graded in Chromium).

| # | Model | Quant | Gauntlet % | Tests | tok/s (1 stream) | Voxel Pagoda |
|---|-------|-------|-----------:|------:|-----------------:|-------------:|
| 1 | Gemma 4 · E4B | Q4_K_M | **85.1%** | 71 | 13.8 | 14% |
| 2 | MiniCPM-V 5 · 2B | Q8_0 | **84.8%** | 71 | 26.3 | 29% |
| 3 | Ternary Bonsai-2 · 27B | PTQ1_0 | **83.3%** | 65 | — | — |
| 4 | MiniCPM-V 5 · 2B | Q4_K_M | **82.7%** | 71 | 31.7 | 29% |
| 5 | MiMo V2.6 · 9B | Q4_K_M | **73.9%** | 71 | 13.0 | — |
| 6 | Ornith 1.5 · 9B | Q4_K_M | **72.8%** | 71 | 10.2 | — |
| 7 | Gemma 4 · 12B | UD-Q2_K_XL | **69.8%** | 71 | 7.0 | 57% |
| 8 | LFM 2.5 · 2.6B | Q8_0 | **68.5%** | 71 | 25.9 | — |
| 9 | LFM 2.5 · 2.6B | Q4_K_M | **66.7%** | 71 | 34.5 | 43% |
| 10 | Qwen 3.5 · 4B | Q4_K_M | **65.4%** | 71 | 15.6 | 86% |
| 11 | Gemma 4 · 12B | IQ3_XXS | **65.1%** | 71 | 6.5 | — |
| 12 | Sharp-Spark X2.5 · 4B | Q4_K_XL | **63.6%** | 71 | 16.7 | 43% |
| 13 | Gemma 3n · E4B | Q4_K_M | **56.3%** | 71 | 13.1 | — |

## Voxel Pagoda ranking (limits test)

Writing a working 3D voxel engine from scratch is the hardest thing we ask.

| Model | Voxel % | Voxels | Floors |
|-------|--------:|-------:|-------:|
| Qwen 3.5 · 4B (Q4_K_M) | 86% | 320 | 4 |
| Gemma 4 · 12B (UD-Q2_K_XL) | 57% | 111,872 | 0 |
| LFM 2.5 · 2.6B (Q4_K_M) | 43% | 0 | 0 |
| Sharp-Spark X2.5 · 4B (Q4_K_XL) | 43% | 0 | 0 |
| MiniCPM-V 5 · 2B (Q8_0) | 29% | 0 | 0 |
| MiniCPM-V 5 · 2B (Q4_K_M) | 29% | 0 | 0 |
| Gemma 4 · E4B (Q4_K_M) | 14% | 0 | 0 |

## Verdicts

- **#1 Gemma 4 · E4B (Q4_K_M)** — Accuracy king of v0.3. Slower than MiniCPM but the best all-round brain; PaT arch runs well under 8GB.
- **#2 MiniCPM-V 5 · 2B (Q8_0)** — Best speed/accuracy balance. Daily-driver material; only soft spot is the voxel build suite.
- **#3 Ternary Bonsai-2 · 27B (PTQ1_0)** — Reasoning specialist: perfect adversarial+chains, near-perfect tooluse. 3 tok/s keeps it out of daily-driver duty.
- **#4 MiniCPM-V 5 · 2B (Q4_K_M)** — Nearly matches Q8 at higher speed. The value pick if every tok/s counts.
- **#5 MiMo V2.6 · 9B (Q4_K_M)** — Strong reasoner, decent speed; context capped at 8K on this card.
- **#6 Ornith 1.5 · 9B (Q4_K_M)** — Solid mid-pack brain; 10 tok/s single-stream.
- **#7 Gemma 4 · 12B (UD-Q2_K_XL)** — The 12B fits! Q2 quant costs accuracy but voxel building is the best of any model here.
- **#8 LFM 2.5 · 2.6B (Q8_0)** — Fast and efficient; mid-pack accuracy.
- **#9 LFM 2.5 · 2.6B (Q4_K_M)** — Fastest useful model tested; accuracy trails the leaders.
- **#10 Qwen 3.5 · 4B (Q4_K_M)** — THE VOXEL CHAMPION — 86% on the code pagoda. Accuracy mid-pack.
- **#11 Gemma 4 · 12B (IQ3_XXS)** — 12B squeezed to IQ3: runs but accuracy drops below 4B leaders.
- **#12 Sharp-Spark X2.5 · 4B (Q4_K_XL)** — Mid-pack across the board; nothing stands out.
- **#13 Gemma 3n · E4B (Q4_K_M)** — Last place on v0.3 — the older 3n arch can't keep up.
