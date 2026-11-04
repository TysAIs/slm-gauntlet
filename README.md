# SLM Gauntlet

A benchmark for **small language models** (sub-12B class) that runs on whatever device you have — NVIDIA, AMD, or Apple Silicon. The card generator auto-detects your GPU and its memory, so every model card shows **your** hardware, not ours. It measures whether they can actually **do work as subagents** — call tools correctly, recover from errors, follow instructions precisely, and retrieve facts from long context — not just answer trivia.

<!-- BEGIN GENERATED LEADERBOARD: scripts/leaderboard_check.py -->

**Current leaderboard — 71 tasks, scorer v0.3.1, PVE GTX 1070 Ti 8 GB, all layers on-GPU, zero CPU offload, temp 0, seed 1.**

One row per model: the **best-scoring configuration** of that model in the corpus (231 scored configurations behind this table). Every score is the weighted aggregate defined in `scripts/leaderboard_check.py` and is recomputed from that run's log; the `Method` column carries the task count and scorer version for the row, so no row is ever compared across methodologies. Full per-configuration data: [`results/_published/LEADERBOARD.md`](results/_published/LEADERBOARD.md).

| Rank | Model | Best configuration | Score | Tool | Adv | Chains | Struct | Retr | Code | Instr | Method | Card |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 🥇 | Spark-X2.6 4B | IQ3_M · KV FP16 · 32K ctx | **91.5%** | 95% | 100% | 100% | 100% | 88% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_spark-x2.6-4b-iq3m-bartowski.png) |
| 🥈 | Gemma 4 · E4B | Q4_K_M | **90.5%** | 95% | 88% | 83% | 100% | 100% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_gemma4-e4b-q4_K_M.png) |
| 🥉 | MiniCPM-V 5 · 2B | Q8_0 | **90.0%** | 93% | 88% | 83% | 100% | 100% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_minicpm5-2b-q8_0.png) |
| 4 | Bolt E4B | UD-IQ3_XXS · KV q4_0 · 32K ctx | **89.1%** | 95% | 88% | 100% | 100% | 75% | 100% | 57% | 71 t · v0.3.1 | [png](results/cards/card_bolt-e4b-udiq3xxs-kvq4.png) |
| 5 | Dory 1.0 4B | Q5_K_M · KV q8_0 · 32K ctx | **88.7%** | 89% | 88% | 100% | 100% | 88% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_dory-1.0-4b-q5km-kvq8.png) |
| 6 | Qwen3.5-9B | Q4_K_M · KV FP16 · 32K ctx | **86.7%** | 89% | 75% | 100% | 90% | 88% | 100% | 57% | 71 t · v0.3.1 | [png](results/cards/card_qwen35-9b-q4km.png) |
| 7 | LFM3 1.7B | IQ4_NL · KV FP16 · 32K ctx | **86.3%** | 84% | 88% | 100% | 90% | 88% | 100% | 57% | 71 t · v0.3.1 | [png](results/cards/card_lfm3-1.7b-iq4nl-bartowski.png) |
| 8 | Spark-X2.6-1.7B | Q8_0 · KV FP16 · 32K ctx | **82.3%** | 82% | 88% | 83% | 100% | 88% | 67% | 57% | 71 t · v0.3.1 | [png](results/cards/card_spark-x2.6-1.7b-q8_0.png) |
| 9 | K2-Horizon · 7B | Q4_K_M | **81.1%** | 77% | 62% | 100% | 100% | 88% | 100% | 36% | 71 t · v0.3.1 | [png](results/cards/card_k2horizon-7b-q4_K_M.png) |
| 10 | Ornith 1.5 · 9B | Q4_K_M | **77.8%** | 89% | 62% | 100% | 100% | 38% | 83% | 57% | 71 t · v0.3.1 | [png](results/cards/card_ornith-9b-q4_K_M.png) |
| 11 | MiMo V2.6 · 9B | Q4_K_M | **74.9%** | 79% | 88% | 100% | 90% | 38% | 83% | 50% | 71 t · v0.3.1 | [png](results/cards/card_mimo-9b-q4_K_M.png) |
| 12 | MiniCPM-V 4.7 1B | IQ4_XS · KV FP16 · 32K ctx | **74.5%** | 79% | 62% | 100% | 90% | 62% | 67% | 50% | 71 t · v0.3.1 | [png](results/cards/card_minicpmv47-1b-iq4xs.png) |
| 13 | Gemma 4 · 12B | UD-Q2_K_XL | **72.6%** | 74% | 88% | 67% | 90% | 50% | 83% | 57% | 71 t · v0.3.1 | [png](results/cards/card_gemma4-12b-ud-q2_K_XL.png) |
| 14 | LFM 2.5 · 2.6B | Q8_0 | **70.9%** | 74% | 38% | 83% | 70% | 75% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_lfm2.5-2.6b-q8_0.png) |
| 15 | Qwen 3.5 · 4B | Q4_K_M | **67.9%** | 68% | 62% | 67% | 80% | 50% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_qwen3.5-4b-q4_K_M.png) |
| 16 | Sharp-Spark X2.5 · 4B | Q4_K_XL | **66.7%** | 68% | 50% | 67% | 80% | 50% | 100% | 50% | 71 t · v0.3.1 | [png](results/cards/card_sharp-spark-4b-q4_K_XL.png) |
| 17 | LFM2.5-1.2B | Q8_0 · KV FP16 · 32K ctx | **65.2%** | 63% | 50% | 83% | 70% | 88% | 50% | 43% | 71 t · v0.3.1 | [png](results/cards/card_lfm25-1.2b-q8_0.png) |
| 18 | LFM2.5-8B-A1B | UD-Q4_K_M · KV FP16 · 32K ctx | **56.1%** | 84% | 12% | 83% | 50% | 25% | 100% | 0% | 71 t · v0.3.1 | [png](results/cards/card_lfm25-8b-a1b-udq4km.png) |
| 19 | Gemma 3n · E4B | Q4_K_M | **52.4%** | 26% | 62% | 17% | 80% | 75% | 83% | 50% | 71 t · v0.3.1 | [png](results/cards/card_gemma-e4b-q4_K_M.png) |

**Legacy rows — NOT comparable, kept for provenance:**

| Model | Configuration | Score | Why it is not comparable |
|---|---|---|---|
| Ternary Bonsai-2 · 27B | PTQ1_0 | 86.2% | 65 tasks (current methodology is 71) |

**Offload / >12B — scored separately, never merged with the on-GPU table:**

| Model | Configuration | Score | Method |
|---|---|---|---|
| LFM2.5-24B-A2B | UD-Q4_K_XL · KV FP16 · 8K ctx | 59.2% | 71 t · v0.3.1 |

**What this table says:**

- **Best on-GPU: Spark-X2.6 4B (IQ3_M · KV FP16 · 32K ctx) at 91.5%** — 63 configuration(s) of this model were scored; this is the best of them.
- Next: Gemma 4 · E4B (Q4_K_M) at 90.5% — inside the weight of a single task (0.7-1.6 pp here depending on the suite), so a tie, not a win.
- 1 legacy row is excluded from the ranking (task count or scorer version differs); it keeps the published number below but is never ranked against current rows.

_Generated by `scripts/leaderboard_check.py` from `results/cards/*.json`. `python3 scripts/leaderboard_check.py` fails when this block and the corpus disagree — edit the generator, not the table._

<!-- END GENERATED LEADERBOARD -->

Full data: [`results/_published/LEADERBOARD.md`](results/_published/LEADERBOARD.md) · machine-readable [`results/_published/leaderboard.json`](results/_published/leaderboard.json) · trading cards in [`results/cards/`](results/cards/).

**How to read this:** every published score is the weighted aggregate defined in `scripts/leaderboard_check.py` (the same weights `gauntlet run` prints) and is recomputed from that run's log — a row you cannot trace to a run log does not appear in the table. The table above is generated, not written: `python3 scripts/leaderboard_check.py` exits non-zero when it and the card corpus disagree, and `--write` regenerates it.

---

## How it works

Every task is run against your model's OpenAI-compatible endpoint (`/v1/chat/completions`) through a **multi-turn agent loop**:

1. The task prompt + tool definitions are sent to the model (temperature 0, thinking disabled).
2. If the model emits a `tool_calls` response, the tool actually **executes** against an in-memory sandbox: a mock flights API, a file workspace, a calculator, a records DB. Results feed back into the conversation, up to 8 turns.
3. When the model produces a final answer, the **scorer** evaluates it mechanically.

### Scoring (no LLM judge anywhere)

Three layers, all deterministic:

- **Text assertions** — weighted checks on the output: exact numbers, required code structures, JSON schema validation, regex patterns, free-form Python predicates. Partial credit: a task that half-passes scores 0.5. A `must_pass` gate zeroes the task when a critical requirement fails.
- **State verification** — after the run, the sandbox itself is inspected: *was the flight reservation actually created with the right passenger? was the file actually written? was the destructive tool actually NOT called?* The model is graded on outcomes, not statements.
- **Failure modes** — every non-completion is classified: `looped` (repeated identical calls, watchdog-terminated), `timeout`, `empty_response`, `error`. How a small model fails matters as much as the score.

Same model + same seed → identical results.

### The suites

| Suite | Tasks | What it measures |
|---|---|---|
| **tooluse** | 12 + 7 hard | Correct tool selection and arguments; calculator grounding (does it use the tool or hallucinate arithmetic?); error recovery (tool fails once → must retry); sandbox escape refusal; distractor discipline; and a **hard tier**: policy compliance with traps, long-context reservations, missing functions, state conflicts, multi-step computation chains |
| **adversarial** | 8 | Prompt-injection resistance: injected "ignore instructions" in email/tool data, system-prompt exfiltration, priority inversion, sycophancy pressure, base64-encoded bypasses, impersonation. Must resist the attack **and** still complete the real job |
| **agent_chains** | 6 | Multi-turn tool pipelines (3-8 turns): search→pick→reserve chains, file write→append→read-back, lookup→transform→compute, mid-chain error recovery, conditional branches on tool output |
| **structured** | 8 + 2 hard | Valid JSON against a schema, extraction from messy input, exact function signatures |
| **retrieval** | 8 | Needle-in-a-haystack from 4K to 32K tokens, NoLiMa-style associative needles, and refusal-when-absent (anti-hallucination) |
| **coding** | 6 | Bug fixes, dict/list transforms, regex parsing, contradiction traps where the naive solution is invalid |
| **instruction** | 8 + 6 hard | Exact ordering, format locks, negation constraints, 4-constraint stacks |

### How needle-in-a-haystack works (no agent needed)

The retrieval suite does **not** require an agent loop — it's plain chat completions. At run time the harness generates filler paragraphs from a seeded RNG (deterministic, never fetched from the internet), hides one fact — e.g. *"The secret access code for the vault is ZEBRA-48213"* — at a random depth inside the filler, and asks the model for that one fact. Because the needle is generated fresh from a combinatorial space (thousands of possible codes/topics), no model can have memorized it: a good score means real long-context recall, not training-data leakage. **NoLiMa** variants go further: the question shares no keywords with the needle ("What covers the entrance?" → the needle says *"a thick tarp covered the doors"*), so the model must make the connection, not pattern-match.

Plain `POST /v1/chat/completions` → check the answer contains the code. That's the whole mechanism.

### Beyond pass/fail

- **`gauntlet perf`** — TTFT, tok/s at 1/4/8 concurrent streams, 8K-token prefill speed.
- **Capacity analysis** — from the server log: weights VRAM, KV bytes/token, KV pool after weights, and the max number of concurrent 8K-context subagents the card can hold.
- **Model cards** — trading-card style PNG per model: rank badge, suite percentages, speed curve, KV pool, max subagents, and a plain-English verdict.

---

## Run on your hardware

The benchmark is **device-agnostic**. `gauntlet.device.detect_device()` auto-detects your hardware:

- **NVIDIA** — via `nvidia-smi` (GPU name + total VRAM)
- **Apple Silicon** — unified memory via `sysctl` (M-series chip + total memory)
- **AMD** — via `rocm-smi`
- **CPU** — fallback

The card generator stamps whatever device it ran on into the model card — GPU name, total memory, and whether weights fit fully on-device or needed RAM offload. No manual config. Your cards show your hardware.

## Quickstart

Requirements: Python 3.11+, any OpenAI-compatible server. Tested with llama.cpp (`llama-server`).

```bash
git clone <this-repo>
cd slm-gauntlet
pip install -e .

# 1. Serve any GGUF model with llama.cpp (example: 32K ctx, 8 slots)
llama-server -m /path/to/model-Q4_K_M.gguf --host 0.0.0.0 --port 8080 \
  -c 32768 -np 8 --kv-unified -fa --jinja --temp 0.0

# 2. Run the full gauntlet (71 tasks, ~5-15 min on an 8GB GPU)
gauntlet run --endpoint http://localhost:8080/v1 --model my-model --suite all

# Single suite instead:
gauntlet run --endpoint http://localhost:8080/v1 --model my-model --suite tooluse

# 3. Throughput benchmark
gauntlet perf --endpoint http://localhost:8080/v1 --model my-model

# 4. Leaderboard from your local runs
gauntlet report
```

Or with Docker (serves + benches in one command):

```bash
MODEL_DIR=/path/to/ggufs MODEL_ID=my-model docker compose up --build
```

Results land in `results/<model>_<timestamp>.json` with per-task attempts, tool-call logs, failure modes, and token usage.

### Useful flags

```
gauntlet run --suite all|tooluse|adversarial|agent_chains|structured|retrieval|coding|instruction
             --concurrency N     parallel tasks; keep 1-2 for 8GB GPUs (default 2)
             --timeout S         per-task timeout in seconds (default 240)
             --seed N            RNG seed for generated tasks (default 0; same seed = same tasks)
             --repeats K         run every task k times; pass^k = all-reps reliability (3 recommended)
```

### Speculative decoding

Draft-model support depends entirely on the target model's ecosystem — there is no universal draft:

- **Qwen3.5-4B / 9B**: MTP drafts exist ([unsloth/Qwen3.5-4B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-MTP-GGUF)). MTP heads ride inside the same GGUF (no extra draft VRAM) but require a recent llama.cpp and `-np 1` (no parallel slots with MTP yet).
- **MiniCPM5-2B / LFM2.5 / Gemma-3n**: no published EAGLE-3/MTP drafts exist at time of writing. Standard `-md` self-drafting (same model at lower quant as its own draft) works with llama.cpp's `--model-draft` if you can spare the extra ~1GB VRAM.
- Benchmarks above were run WITHOUT speculative decoding — comparable baseline numbers.

The gauntlet measures quality and throughput as served; if you serve with a draft, note it in your result metadata.

### Tips

- **Start with `--suite tooluse`** — it's the most informative single suite for subagent fitness and finishes fastest.
- If many tasks report `error: request exceeds context size`, your server's `-c` is too small for the retrieval suite; either raise it or run retrieval separately.
- Thinking-mode models (Qwen, DeepSeek-style) must be served with thinking disabled — the harness sends `chat_template_kwargs: {enable_thinking: false}` automatically.
- Models without native function calling in their GGUF chat template (e.g. some Gemma quants) will score artificially low on tooluse; check the failure text to distinguish template issues from capability issues.
- Running on a shared machine: benchmarks are GPU-heavy and sustained. Stop other GPU consumers first.

---

## For AI agents running this benchmark

If you are an AI agent tasked with benchmarking a model using this repo:

1. Install: `pip install -e .` (deps: httpx, PyYAML, pydantic only).
2. Confirm the endpoint serves `/v1/models` before running.
3. Run `gauntlet run --endpoint <url> --model <name> --suite all --concurrency 1` for a first pass.
4. Read `results/<model>_<ts>.json`: `subagent_capability_score` is the headline; `failure_modes` explains regressions.
5. The sandbox is fully in-memory — no host filesystem writes, no network calls from tasks. Safe to run unattended.

---

## Adding a model recipe

One canonical llama.cpp load recipe per model×quant lives in `runtimes/recipes/*.yaml` (context, slots, KV cache type, temperature). Copy an existing recipe and adjust. Recipes make runs comparable across machines and quantizations.

## Repository hygiene

This repo must never contain personal information or private infrastructure details. `scripts/hygiene-check.sh` scans every tracked file (and full git history with `--history`) for identity/IP patterns and runs as a blocking CI step on every push. Results directories with run artifacts are gitignored — publish what you choose, share what you want.

## Credits & thanks

The gauntlet stands on ideas proven by others — with gratitude to:

- **[τ-bench (Sierra)](https://github.com/sierra-research/tau-bench)** — the tool-agent-with-state-verification pattern (outcome checks against a controlled environment) that our tooluse suite is built around.
- **[BFCL / Berkeley Function-Calling Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)** — state-based execution checking and the multiple-turn category design.
- **[NoLiMa](https://arxiv.org/abs/2502.05167)** (Petroni et al.-style associative needle tests) — the zero-lexical-overlap retrieval idea and several of our needle topics.
- **[Vals AI](https://www.vals.ai/)** — weighted partial-credit rubrics with must-pass gates.
- **[ggml / llama.cpp](https://github.com/ggml-org/llama.cpp)** — the serving runtime every recipe targets, and the GGUF ecosystem.
- **[PrismML](https://docs.prismml.com)** — the llama.cpp fork enabling ternary Bonsai-2 (PQ2_0/PTQ1_0) inference, and open research into ternary weights.
- **LiquidAI, Qwen/Alibaba, Google, NVIDIA, bartowski, unsloth** — the open models and quantizations the leaderboard runs on.

Nothing is copied verbatim from any of these projects; the suite implementations in `gauntlet/` are original code inspired by their published designs.

## Scope

Models up to ~12B parameters that fit in 8GB VRAM at Q4_K_M or better. Quant matrix tested per model: Q8_0 (ceiling), Q5_K_M, Q4_K_M, plus ternary packings where a fork exists. No sub-4-bit standard quants (quality cliff for small models).

## License

MIT
