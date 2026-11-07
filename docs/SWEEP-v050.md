# v0.5.0 measurement program — how the re-run is executed and what it costs

This is the runbook for phase 3 + phase 6 of the v0.5.0 program: re-measuring the published
corpus on the new suite, and the new-model intake the card asks for. Everything runs on the
**PVE GTX 1070 Ti test box only**; the GB10 nodes are not touched (TESTING RULE).

## What changed in the suite (why old rows cannot be compared to new ones)

`tasks/realworld.yaml` grew from 10 to 20 tasks, so the methodology task count is now
**94** (87 YAML + 7 generated retrieval) instead of 84. `gauntlet/methodology.py` publishes
that as epoch **0.5.0**; 0.4.0 is frozen at the 84 tasks it was authored with. The
publisher only ever prints rows from one epoch, so a 0.5.0 row is never ranked against a
v0.3.1 card — the old table stays visible as the published table until 0.5.0 rows exist,
then it moves wholesale.

## Hardware and lane facts (measured, not assumed)

| fact | value | how it was measured |
|---|---|---|
| test box | PVE CT100, `llama-worker@8891.service`, GTX 1070 Ti 8 GB | `systemctl list-units` in the CT |
| single-stream decode | **38.7 tok/s** (prefill 471 tok/s) | one `/v1/chat/completions` with `timings` |
| VRAM at 32K ctx, f16 KV, 4B IQ3_M | 3.7 GiB, GPU 78 % | `nvidia-smi` during the run |
| thermal start | 28 C | `gauntlet run` preflight line |
| ceiling | 89 C — the run refuses to start above it | `gauntlet/thermal.py` |

## Commands

```bash
# 1. inventory of what is actually on the box (no invented quants)
ssh pve 'pct exec 100 -- find /mnt/data/models -name "*.gguf" -printf "%s\t%p\n"' > /tmp/inv.tsv

# 2. manifest: 18 re-runnable ranked rows + 30 Nemotron quant x KV configs
.venv/bin/python scripts/build_sweep_manifest.py --inventory /tmp/inv.tsv

# 3. smoke one config end to end, then restore the shipped unit
GRUNT_HOST=<test-box> .venv/bin/python scripts/pve_sweep.py --limit 1 \
    --only spark-x2.6-4b-iq3m-bartowski --restore-on-exit

# 4. the sweep (resume-safe; re-running the same command continues where it stopped)
GRUNT_HOST=<test-box> setsid .venv/bin/python scripts/pve_sweep.py \
    > results/_sweep_logs/sweep.out 2>&1 < /dev/null &

# 5. after the sweep: cards + published table
.venv/bin/python gen-leaderboard.py
.venv/bin/python scripts/make_cards.py results/cards/manifest.json
.venv/bin/python scripts/leaderboard_check.py --write
.venv/bin/python scripts/leaderboard_check.py     # must exit 0
```

`--host` (or `GRUNT_HOST`) exists because a tailnet address is the operator's, not the
repo's: the hygiene gate rejects address literals in tracked files.

## What the driver refuses to do

* **Serve the wrong model.** It waits for BOTH `/props.model_path` and `/v1/models[0].id` to
  match the intended config. A stale server answers every liveness check, which is how a
  queue once wrote results labelled for model A while server B served them.
* **Guess a weights file.** `build_sweep_manifest.py` resolves each row to exactly one file
  on the box; 4 rows needed an explicit alias table (Gemma 3n vs Gemma 4, LFM 2.6B vs 1.2B,
  Qwen 4B vs 9B) and `k2horizon-7b` is refused outright because its gguf is not on the box.
* **Publish a dead endpoint.** Every run's attempt health goes through
  `gauntlet/run_health.py`; the publisher will not rank a card whose source log is a
  transport failure (see audit F16).

## Cost model (measured, not estimated)

Per config the driver does: unit swap + load (≈40-60 s for a 4B at 32K), then the suite.
At 38.7 tok/s decode with a 2-slot server, a 94-task run is tens of minutes, not minutes.
A 48-config sweep is therefore an overnight job; it is detached (`setsid`), streams each
run to `results/_sweep_logs/<alias>-kv<type>.log`, and records one JSON line per config in
`results/_sweep_state.jsonl`, so an interrupted sweep resumes instead of restarting.

## Serving finding that changes the driver: one slot, not two

The first driver version used `-np 2` at 32K with f16 KV (two slots). Measured on the lane:
a 22K-token prompt did not finish inside the client's 420-second ceiling, and the server
journal showed tasks being cancelled at the 240 s timeout (`stop: cancel task`). Isolating
one variable at a time on the same weights and window:

| slots | flash attention | 20K-token prompt | prefill | decode |
|---|---|---|---|---|
| 2 | on | **> 420 s, cancelled** | — | — |
| 1 | on | 30.4 s | 675 tok/s | 40.7 tok/s |
| 1 | off | 29.8 s | 672 tok/s | 40.6 tok/s |

So the two-slot configuration was the defect (it halves the effective KV on an 8 GB card),
not flash attention. The manifest now runs `-np 1` for every 32K config and the client
timeout is 600 s. A config that cannot finish is recorded as a failure, not retried forever.

## Phase 4 — context: what the ladder can honestly claim

The suite's long-context rungs top out at 24K because a 32K *target* tokenizes to ~35K real
tokens and every request 400s against a 32,768-token window (measured in the audit; 230 of
276 attempts were client errors, so the 32K cell measured nothing). Raising it is a serving
question, not a task-authoring one: the run above holds 32K with f16 KV in **3.7 GiB of the
card's 8 GiB**, so a 40,960-token window (and therefore a real 32K rung) fits for the
≤4B class — but not necessarily for the 12B class at Q4, and a config-dependent task count
would make rows incomparable.

Decision for 0.5.0: keep **one** served window (32K) and one ladder (max 24K) across every
configuration, so all rows are measured on the same instrument. A 32K rung is the v0.5.1
candidate, gated on a per-class context ceiling measured the same way for each size class.

## Honest gaps in this runbook

* The 30 Nemotron configs run at 32K ctx / 2 slots for comparability; that is a *standard*
  setting, not a per-model optimum, and the table must say so.
* `np=2` at 32K f16 KV is close to the 8 GB card's limit for a 4B. Configs that fail to
  serve are recorded as `serve_failed`, not dropped silently — a missing row is data.
* The sweep takes the test lane for hours. Nothing else may use `grunt-pve` meanwhile; the
  shipped unit is restored (and proven with a real completion) at the end.
