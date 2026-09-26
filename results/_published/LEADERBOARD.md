# SLM Gauntlet v0.3.1 — Leaderboard

All runs on a single GTX 1070 Ti (8 GB), zero offload, `-ngl 99`, seed 1, temp 0.
71 tasks / 7 suites (v0.3 hard suites included). Bonsai-2: 65 merged tasks (ran in suite batches).
v0.3.1: fixed a broken structured-hard grader that zeroed 2 tasks for every model; all scores re-audited.

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

## Verdicts

- **#1 Gemma 4 · E4B (Q4_K_M)** — Accuracy king of v0.3.1 by a hair. PaT arch punches above its size; stacked-constraint instruction following is its one gap.
- **#2 MiniCPM-V 5 · 2B (Q8_0)** — Statistically tied with #1 (0.2pp) at DOUBLE the speed. The practical daily-driver pick.
- **#3 Ternary Bonsai-2 · 27B (PTQ1_0)** — Reasoning specialist: perfect adversarial, agent chains and structured. 3 tok/s keeps it out of daily-driver duty.
- **#4 MiniCPM-V 5 · 2B (Q4_K_M)** — Value pick: 85.6% at the fastest useful speed (32 tok/s).
- **#5 Ornith 1.5 · 9B (Q4_K_M)** — Solid mid-pack brain at 10 tok/s single-stream.
- **#6 MiMo V2.6 · 9B (Q4_K_M)** — Strong reasoner; context capped at 8K by its VRAM footprint on this card.
- **#7 Gemma 4 · 12B (UD-Q2_K_XL)** — The 12B fits in 8GB. Q2 quant costs accuracy vs the E4B — prefer E4B unless you need the bigger model.
- **#8 LFM 2.5 · 2.6B (Q8_0)** — Fast and efficient; accuracy trails the leaders.
- **#9 LFM 2.5 · 2.6B (Q4_K_M)** — Fastest useful model tested; accuracy trails.
- **#10 Qwen 3.5 · 4B (Q4_K_M)** — Mid-pack accuracy; aced coding while staying fast.
- **#11 Gemma 4 · 12B (IQ3_XXS)** — 12B squeezed to IQ3: runs, but below the 4B leaders. UD-Q2 is the better 12B quant.
- **#12 Sharp-Spark X2.5 · 4B (Q4_K_XL)** — Mid-pack across the board.
- **#13 Gemma 3n · E4B (Q4_K_M)** — Last place — the older 3n arch can't keep up with the v0.3 hard suites.
