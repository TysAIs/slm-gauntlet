# SLM Gauntlet

A benchmark for **small language models** (sub-12B, 8GB VRAM class) that measures whether they can actually **do work as subagents** — call tools correctly, recover from errors, follow instructions precisely, and retrieve facts from long context — not just answer trivia.

**Current leaderboard (GTX 1070 Ti 8GB, all layers on-GPU, zero CPU offload):**

| Rank | Model | Score | Tool use | Coding | Instruction | Structured | Retrieval | Speed (c1→c8) |
|---|---|---|---|---|---|---|---|---|
| 🥇 | MiniCPM5-2B Q4_K_M | **91.7%** | 100% | 83% | 75% | 100% | 100% | 32→62 tok/s |
| 🥈 | MiniCPM5-2B Q8_0 | 89.3% | 88% | 83% | 88% | 88% | 100% | 33→62 tok/s |
| 🥉 | Qwen3.5-4B Q4_K_M | 88.0% | 94% | 83% | 88% | 88% | 88% | 16→27 tok/s |
| 4 | Bonsai-2 27B PTQ1_0 (1-bit) | 81.7% | **100%** | 83% | 88% | 100% | 38% | 3→3 tok/s |
| 5 | Bonsai-2 27B PQ2_0 | 82.5%* | **100%** | 100% | 88% | 100% | 25% | 5→6 tok/s |
| 6 | LFM2.5-2.6B Q8_0 | 77.8% | 76% | 100% | 62% | 75% | 75% | 26→44 tok/s |
| 7 | LFM2.5-2.6B Q4_K_M | 75.3% | 76% | 100% | 62% | 75% | 62% | 27→58 tok/s |
| 8 | Gemma-3n-E4B Q4_K_M | 70.0% | 29%⚠ | 83% | 62% | 100% | 75% | 13→13 tok/s |

\* Bonsai-2 PQ2_0 weights fill the card completely: 8K context is the hard ceiling and there is zero concurrency headroom. Gemma ⚠: emits code blocks instead of native tool calls in its GGUF chat template — a template limitation, not a model deficiency.

**Takeaway:** MiniCPM5-2B Q4_K_M is the best daily-driver subagent for an 8GB card. Bonsai-2 1-bit is the best *tool-calling specialist* if you can live with 3 tok/s.

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
| **tooluse** | 12 + 5 hard | Correct tool selection and arguments; calculator grounding (does it use the tool or hallucinate arithmetic?); error recovery (tool fails once → must retry); sandbox escape refusal; distractor discipline; and a **hard tier**: policy compliance with traps, long-context reservations, missing functions, state conflicts, multi-step computation chains |
| **adversarial** | 8 | Prompt-injection resistance: injected "ignore instructions" in email/tool data, system-prompt exfiltration, priority inversion, sycophancy pressure, base64-encoded bypasses, impersonation. Must resist the attack **and** still complete the real job |
| **agent_chains** | 6 | Multi-turn tool pipelines (3-8 turns): search→pick→reserve chains, file write→append→read-back, lookup→transform→compute, mid-chain error recovery, conditional branches on tool output |
| **structured** | 8 | Valid JSON against a schema, extraction from messy input, exact function signatures |
| **retrieval** | 8 | Needle-in-a-haystack from 4K to 32K tokens, NoLiMa-style associative needles, and refusal-when-absent (anti-hallucination) |
| **coding** | 6 | Bug fixes, dict/list transforms, regex parsing, contradiction traps where the naive solution is invalid |
| **instruction** | 8 | Exact ordering, format locks, negation constraints, 4-constraint stacks |

### How needle-in-a-haystack works (no agent needed)

The retrieval suite does **not** require an agent loop — it's plain chat completions. At run time the harness generates filler paragraphs from a seeded RNG (deterministic, never fetched from the internet), hides one fact — e.g. *"The secret access code for the vault is ZEBRA-48213"* — at a random depth inside the filler, and asks the model for that one fact. Because the needle is generated fresh from a combinatorial space (thousands of possible codes/topics), no model can have memorized it: a good score means real long-context recall, not training-data leakage. **NoLiMa** variants go further: the question shares no keywords with the needle ("What covers the entrance?" → the needle says *"a thick tarp covered the doors"*), so the model must make the connection, not pattern-match.

Plain `POST /v1/chat/completions` → check the answer contains the code. That's the whole mechanism.

### Beyond pass/fail

- **`gauntlet perf`** — TTFT, tok/s at 1/4/8 concurrent streams, 8K-token prefill speed.
- **Capacity analysis** — from the server log: weights VRAM, KV bytes/token, KV pool after weights, and the max number of concurrent 8K-context subagents the card can hold.
- **Pagoda build** (`gauntlet pagoda`) — a 9-element staged creative construction (foundation → torii gate → stacked tiers → roof curvature → lanterns → garden → mountain backdrop → atmosphere), each element weighted and checked in order. Tests long-form instruction adherence in creative mode. Pure chat completion, no tools.
- **Model cards** — trading-card style PNG per model: rank badge, suite percentages, speed curve, KV pool, max subagents, Pagoda score, and a plain-English verdict.

---

## Quickstart

Requirements: Python 3.11+, any OpenAI-compatible server. Tested with llama.cpp (`llama-server`).

```bash
git clone <this-repo>
cd slm-gauntlet
pip install -e .

# 1. Serve any GGUF model with llama.cpp (example: 32K ctx, 8 slots)
llama-server -m /path/to/model-Q4_K_M.gguf --host 0.0.0.0 --port 8080 \
  -c 32768 -np 8 --kv-unified -fa --jinja --temp 0.0

# 2. Run the full gauntlet (47 tasks, ~20-40 min on an 8GB GPU)
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
