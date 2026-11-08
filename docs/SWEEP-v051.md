# Sweep — 0.5.1 epoch (task set + serving conditions)

The 0.5.0 sweep procedure and its receipts live in `docs/SWEEP-v050.md` and still apply:
preflight the lane, swap one config at a time with a systemd drop-in, wait for
`/props.model_path` AND `/v1/models[0].id` to match, run the full suite, append a state
line, restore the shipped unit. This file records only what differs for 0.5.1 and why.

## What differs

| | 0.5.0 | 0.5.1 |
|---|---|---|
| task set | 94 tasks (20 realworld scenarios as 20 composite tasks) | 140 tasks (20 realworld scenarios as 58 sub-answer units, 47 changed/hardened tasks), see `docs/AUDIT-TASK-VALIDITY-v0.5.1.md` |
| methodology | 0.5.0 | 0.5.1 (0.5.0 frozen at 94 tasks; epochs never share a table) |
| configuration rows | 48 (5 excluded: architecture the engine cannot load) | the same 48 rows, same quant/KV/ctx values |
| serve flags | `-fa on --reasoning-budget 0` | the same **plus `-cram 0`** (see below) |
| state file | `results/_sweep_state.jsonl` | `results/_sweep_state_v051.jsonl` (a new file; reusing the old one would make the resume logic skip every config) |

## `-cram 0`: why the epoch adds a serving flag

Measured 2026-11-08 on the PVE 1070 Ti lane, first attempt at the 0.5.1 sweep:

* one configuration served, answered the liveness probe, and then **stalled a task for the
  full 600 s client timeout** while the GPU sat at 0 % and 8.9 W. The server's own log for
  that minute is nothing but prompt-cache eviction:

  ```
  W srv alloc: - making room for prompt cache entry, removing oldest entry (size = 81.191 MiB)
  ... 13 identical lines ...
  I slot print_timing: id 0 | task 11374 | prompt eval time = 48832.10 ms / 26267 tokens
  ```

  i.e. a 26 K-token retrieval prompt finished, and the next request spent the cache budget
  evicting entries. The default host prompt cache is 8 GiB (`--cache-ram`, default 8192) and
  a 140-task suite with a 24 K-token retrieval ladder plus 58 short repeated prompts is
  enough to thrash it.
* the same configuration with `-cram 0` (host prompt cache disabled) finished **140 tasks in
  458 s with zero cancelled tasks** (`results/_test_state.jsonl`,
  `results/_sweep_logs/test_cram0.log`).

`-cram 0` affects KV prefix reuse only: it does not change the prompt, the sampling, the
context size or the KV types. It does mean every task re-prefills its prompt, which is slower
but identical in what it measures. A timeout is not a model verdict, so a flag that removes
timeouts is the right trade.

Consequence for comparability, stated plainly: 0.5.1 rows are comparable with each other and
with nothing else. 0.5.1 already differs from 0.5.0 in its task set, so the flag does not
create a new incomparability — it inherits the one that already exists.

## Gates this epoch ran before spending the sweep

1. `scripts/preflight_lane.py --host …` — benchmarkable (unit, endpoint with a real
   completion, GPU not throttled, no foreign load, cool, 120 W pin).
2. `scripts/replay_rescore.py --base-rev 067208f` — re-scores the recorded 0.5.0 answers
   with the 0.5.1 asserts for every task whose prompt did not change; reproduces the 0.5.0
   audit exactly (13 at 0/n, 12 at n/n).
3. `scripts/build_probe_dir.py` + `scripts/pve_sweep.py --tasks-dir tasks_probe` — the 47
   changed tasks on all 43 configurations (72.5 min), then a 4-configuration retrieval probe
   for the generated needle ladder (9.8 min). Result: no task at 0 %, one free row
   (`adv_tool_abuse__no_delete`), see the table in the audit doc.
4. `pytest tests -q` — 278 passed, including a gold and a near-miss per scored unit.

## Commands

```
# probe (changed tasks only; never published)
.venv/bin/python scripts/build_probe_dir.py
.venv/bin/python scripts/pve_sweep.py --host <test-box> \
    --manifest scripts/probe_manifest_v051.tsv --state results/_probe_state_v051.jsonl \
    --tasks-dir tasks_probe --restore-on-exit

# the epoch (resume-safe; re-running the same command continues where it stopped)
.venv/bin/python scripts/pve_sweep.py --host <test-box> \
    --manifest scripts/sweep_manifest_v051.tsv --state results/_sweep_state_v051.jsonl \
    --restore-on-exit

# cards + published table
.venv/bin/python scripts/cards_from_runs.py --from-sweep --state results/_sweep_state_v051.jsonl
.venv/bin/python scripts/make_cards.py results/cards/manifest.json
.venv/bin/python scripts/leaderboard_check.py --write
.venv/bin/python scripts/leaderboard_check.py          # must exit 0

# discrimination of the new corpus (the acceptance gate for the task repair)
.venv/bin/python scripts/audit_task_discrimination.py \
    --state results/_sweep_state_v051.jsonl --json results/_published/discrimination_0.5.1.json
```

## Failure evidence

Unchanged from 0.5.0: a config that cannot serve records `serve_cause`, `serve_detail` and a
tail of the engine log in its state line (`results/_sweep_logs/<alias>-kv<ctk>.serve.log`), so
a missing row can be explained without re-serving it.
