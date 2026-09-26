# Verified Leaderboard — 8GB VRAM class

_slm-gauntlet 0.2 (61 tasks: tooluse 17, adversarial 8, agent_chains 6, structured 8, retrieval 8, coding 6, instruction 8)_
_8GB-class GPU (GTX 1070 Ti), all layers on-GPU, zero CPU offload, llama.cpp_
_temperature 0, seed 1, thinking disabled, pass@1_

| # | Model | Quant | Score | Tool | Adversarial | Chains | Struct | Retrieval | Coding | Instr | tok/s c1→c8 | Pagoda |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MiniCPM5-2B | Q4_K_M | **94.2%** | 100% | 100% | 83% | 100% | 100% | 83% | 75% | 32→62 | 100% |
| 2 | MiniCPM5-2B | Q8_0 | **94.0%** | 98% | 88% | 83% | 100% | 100% | 100% | 75% | 26→51 | 100% |
| 3 | Qwen3.5-4B | Q4_K_M | **89.1%** | 94% | 75% | 100% | 88% | 88% | 83% | 88% | 16→27 | 100% |
| 4 | Bonsai-2 27B | PTQ1_0 (1-bit ternary) | **87.7%** | 100% | 100% | 100% | 100% | 38% | 83% | 88% | 3.2→3.4 | 100% |
| 5 | Bonsai-2 27B | PQ2_0 (2.16bpw) | **84.4%** | 100% | —% | —% | 100% | 25% | 100% | 88% | 4.6→5.7 | —% |
| 6 | MiMo-V2.6-Distill-Qwen-9B | Q4_K_M | **81.7%** | 88% | 88% | 100% | 100% | 38% | 83% | 75% | 13→13 | 100% |
| 7 | Ornith-1.5-9B | Q4_K_M | **80.9%** | 94% | 62% | 100% | 100% | 38% | 83% | 75% | 10→10 | 100% |
| 8 | Sharp-Spark-X2.5-4B | Q4_K_XL | **73.8%** | 65% | 75% | 50% | 100% | 62% | 100% | 75% | 17→17 | 100% |
| 9 | LFM2.5-2.6B | Q8_0 | **73.8%** | 76% | 38% | 83% | 75% | 75% | 100% | 62% | 26→44 | 100% |
| 10 | LFM2.5-2.6B | Q4_K_M | **71.3%** | 76% | 50% | 83% | 75% | 50% | 100% | 62% | 34→58 | 100% |
| 11 | Gemma-3n-E4B | Q4_K_M | **57.6%** | 29% | 62% | 17% | 100% | 75% | 83% | 62% | 13→13 | 100% |

## Verdicts

- **#1 MiniCPM5-2B Q4_K_M**: Best overall. Perfect tooluse+adversarial+retrieval, fastest throughput, ties its Q8 at 40% the size. The default pick.
- **#2 MiniCPM5-2B Q8_0**: Tied-#1 quality; only model to hold 131K ctx x 8 streams. Pick when max context headroom matters more than file size.
- **#3 Qwen3.5-4B Q4_K_M**: Best agent_chains (100%) and strong instruction. Slowest 4B decoder; one loop-out. MTP draft variant can reclaim speed.
- **#4 Bonsai-2 27B PTQ1_0 (1-bit ternary)**: Perfect tooluse+adversarial+chains at 27B params in 6GB. Slow (10.4 tok/s (retested: 3.3× faster with full-VRAM exclusive run)) and 8K ctx cap (VRAM). Best accuracy-per-task when speed doesn't matter. Needs PrismML fork.
- **#5 Bonsai-2 27B PQ2_0 (2.16bpw)**: Weights fill the card: 8K ctx hard max, zero concurrency. Prefer PTQ1_0 (smaller, similar score).
- **#6 MiMo-V2.6-Distill-Qwen-9B Q4_K_M**: Strong new challenger; retrieval capped by 8K ctx on this card (needs ~7GB+ for 32K). Would rank higher with more VRAM.
- **#7 Ornith-1.5-9B Q4_K_M**: Popular new 9B. Weak adversarial resistance (62%). Same 8K ctx ceiling as MiMo.
- **#8 Sharp-Spark-X2.5-4B Q4_K_XL**: Great coder (100%) but weak tool-caller (65%) and chains (50%).
- **#9 LFM2.5-2.6B Q8_0**: Fast but injection-vulnerable (38% adversarial) and loops under tool pressure.
- **#10 LFM2.5-2.6B Q4_K_M**: Fastest TTFT. Same adversarial weakness.
- **#11 Gemma-3n-E4B Q4_K_M**: No native tool_calls in GGUF template (emits code blocks) - template limitation tanks tooluse/chains.

## Model cards

See `results/_published/cards/` for trading-card PNGs per model.

*All runs: temperature 0, seed 1, thinking disabled, all layers on-GPU, zero offload, llama.cpp. Hardware: GTX 1070 Ti 8GB.*