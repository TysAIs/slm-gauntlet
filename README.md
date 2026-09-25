# SLM Gauntlet

A gauntlet benchmark for **small language models** (sub-12B, sub-8GB VRAM) that measures whether they can actually do work as **subagents** — not just answer trivia.

## Why

Static benchmarks (MMLU-style) are saturated and contamination-ridden, and they don't measure what matters for a model serving as a subagent: multi-turn tool execution, error recovery, refusing bad tool calls, schema discipline, retrieval fidelity, and instruction following under constraint stacks. The gauntlet scores exactly those, deterministically.

## Design principles

1. **Real agent loop, real tools.** Tasks run through a multi-turn loop where tool calls actually execute against a sandboxed environment (mock flights API, file workspace, calculator, records DB). Tool results feed back. No one-shot completion scoring.
2. **Deterministic, layered scoring.** Three layers, all mechanical:
   - **Text rubric** — weighted partial credit per check (Vals-AI / Anthropic pattern). A task that half-scores shows 0.5, not FAIL. `must_pass` gates zero the task when a critical requirement fails.
   - **State verification** — BFCL V3-style outcome checks against the sandbox *after* the run: was the reservation actually created with the right passenger? Was the file actually written? Was the distractor tool actually *not* called? "Did the model achieve the right outcome," not "did it say the right thing."
   - **Perfect / partial split** — binary all-checks-pass and weighted rubric score reported side by side.
   No LLM judge anywhere in scored paths. Same model + seed → same result.
3. **Contamination-resistant.** Retrieval tasks (needle-in-haystack) are **generated at run time** from seeded combinatorial space with canary GUIDs embedded — models cannot have memorized them. Includes **NoLiMa-style** needles with zero lexical overlap between question and answer. Classic benchmarks (if any) are labeled `contamination_risk: known` and are sanity floors only.
4. **pass^k, not just pass@1.** Flaky-prone tasks repeat 3×; the headline reports both pass@1 (any-rep rate) and pass^3 (all-reps rate) — τ-bench-style reliability.
5. **Loop watchdog.** A no-progress detector terminates repeated identical tool calls / near-identical outputs and records the task as `looped` — a scored failure and a reported failure mode.
6. **Universal recipes.** One canonical llama.cpp load recipe per model×quant (`runtimes/recipes/*.yaml`): context, slots, KV cache, jinja, temperature. Comparable runs, fixable in one place.

## Suites

| Suite | Tasks | What it measures | Weight |
|---|---|---|---|
| tooluse | 12 | multi-turn tool execution, error recovery (500→retry), irrelevant-tool refusal, schema-violation handling, path-escape handling, state across turns | 40% |
| structured | 8 | strict JSON schema compliance, JSON repair, CSV/extraction, transforms | 20% |
| retrieval | 8+ | needle-in-haystack at 2K–32K tokens, NoLiMa needles, multi-hop, anti-hallucination refusal | 20% |
| coding | 6 | bugfix, bug identification, regex/log parsing, transforms | 10% |
| instruction | 8 | strict formats, word limits, 4-constraint stacks, contradiction traps | 10% |

**Subagent Capability Score** = weighted pass@1 across suites (weights renormalized over suites present). The leaderboard also classifies each model: `generalist | generalist-lite | subagent-specialist | coding-specialist | weak-general`.

## Quickstart

```bash
pip install -e .

# 1. serve a model (llama.cpp)
./runtimes/llama-vanilla.sh /path/to/model-Q4_K_M.gguf 8080 32768 8

# 2. run the gauntlet
gauntlet run --endpoint http://localhost:8080/v1 --model my-model --suite all

# 3. throughput (TTFT + tok/s at c=1/4/8)
gauntlet perf --endpoint http://localhost:8080/v1 --model my-model

# 4. leaderboard
gauntlet report
```

Or with Docker (serves + benches in one command):

```bash
MODEL_DIR=/path/to/ggufs MODEL_ID=my-model docker compose up --build
```

Results land in `results/<model>_<timestamp>.json` with per-task attempts, tool-call logs, failure modes, and token usage.

## Leaderboard

Populated from our hardware runs — see `gauntlet report` output / `results/_published/`.

*(table populated as models complete the gauntlet)*

## Repo hygiene

This repo must never contain personal information or private infrastructure details. `scripts/hygiene-check.sh` scans every tracked file (and optionally full git history with `--history`) for identity/IP patterns and runs as a **blocking CI step** on every push. Pattern list is assembled from fragments at runtime so the checker can't leak what it screens for.

## Scope

Models up to ~12B parameters that fit in 8GB VRAM at Q4_K_M or better. Quant matrix tested per model: Q8_0 (ceiling), Q5_K_M, Q4_K_M. No sub-4-bit quants (quality cliff for small models).

## License

MIT
