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
# 0. gate: is the lane benchmarkable RIGHT NOW? (unit, endpoint with a real completion, card on the
#    GPU and unthrottled, nobody else on it, cool, pinned). One exit code; every leg refuses
#    separately. This also runs automatically as the first step of pve_sweep.py.
GRUNT_HOST=<test-box> python3 scripts/preflight_lane.py            # 0 = benchmarkable
GRUNT_HOST=<test-box> python3 scripts/preflight_lane.py --json     # machine-readable receipt
#    prove the gate itself against the real box (seeds one fault per leg, restores the lane,
#    ~10 min: it really does stop the unit and heat the card). Receipt under results/_preflight/.
GRUNT_HOST=<test-box> python3 scripts/preflight_seeded_faults.py

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
* **Start on a card that is not benchmarkable.** `scripts/preflight_lane.py` runs before the
  first config and the driver reports a `REFUSED <leg>` line instead of scoring anything. Its
  rule set is written out in that file's header; the two rules that matter most, and why they
  are written down rather than left to judgement:
  * the throttle mask is a bitmask with a legit idle bit (`0x1 GPU_IDLE`, the measured state of
    this card at 139 of 1911 MHz / 9.7 W / 0 %), so the gate only refuses on the slowdown bits
    (`HW_SLOWDOWN 0x8`, `SW_THERMAL 0x20`, `HW_THERMAL 0x40`, `HW_POWER_BRAKE 0x80`) and never
    on a clock-versus-max comparison;
  * temperature comes from the PVE HOST (`nvidia-smi --query-gpu=temperature.gpu`) because
    inside LXC 100 the same query answers `[Function Not Found]`, and the refuse line is 80 C
    against the card's 83 C target (thermal slowdown fired on 8.8-17.4 % of loaded samples in
    the 13-minute reference run).
  A leg that cannot be asked (ssh/`pct exec`/nvidia-smi failure) exits 8 - "cannot ask" - and is
  never recorded as a fault.
* **Trust the gate's rules without proving them.** `scripts/preflight_seeded_faults.py` seeds one
  REAL fault per leg on the box (stop the unit, point at a dead port, run a genuine `-ngl 0`
  engine, hold the card with `llama-bench`, burn it past 80 C, raise the power limit), runs the
  shipped gate, and quotes its exit code per leg; it restores the lane and then requires the
  unseeded state to return 0. Two findings from running it are now baked into the gate:
  a `-ngl 0` engine still holds **169 MiB** of CUDA context (a 100 MiB floor called that healthy),
  so the CPU-fallback floor is 256 MiB against a measured 1796 MiB for a real 2B `-ngl 99`
  offload; and a stopped unit keeps its VRAM resident for a moment, so a seed must wait for the
  card to be released before judging it. Offline rule proofs stay in
  `tests/test_preflight_lane.py` (recorded samples) and
  `tests/test_preflight_seeded_faults.py` (expectations cross-checked against the gate's exit
  contract).

## Cost model (measured, not estimated)

Per config the driver does: unit swap + load (≈40-60 s for a 4B at 32K), then the suite.
At 38.7 tok/s decode with a 2-slot server, a 94-task run is tens of minutes, not minutes.
A 48-config sweep is therefore an overnight job; it is detached (`setsid`), streams each
run to `results/_sweep_logs/<alias>-kv<type>.log`, and records one JSON line per config in
`results/_sweep_state.jsonl`, so an interrupted sweep resumes instead of restarting.

## When a config cannot serve: causes, logs, exclusions (measured 2026-11-07)

Seven configs were recorded `serve_failed` in one day and left **nothing** behind to diagnose —
no engine log, no exit code, only `server never came up as <alias>`. The engine had in fact
printed the reason in under a second. The driver now makes a failure self-explaining:

* every serve attempt, successful or not, streams the unit's own stdout/stderr into
  `results/_sweep_logs/<alias>-kv<ctk>.serve.log` (captured by following the unit's journal
  from *before* the restart, because the first error line lands ~150 ms after start);
* the state line for a failure carries `serve_cause`, `serve_detail`, `serve_log`, `serve_tail`,
  `serve_exec_status`, `serve_active_state`, `serve_restarts`;
* a unit that has already crashed is concluded in ~25 s instead of being polled for the full
  600 s (`FASTFAIL_RESTARTS`), and the unit is then stopped so it stops re-running the loader;
* the driver stops the previous config's server, then waits (bounded, 45 s) for the PVE host to
  report the card free before starting the next one, logging what it saw (`--no-vram-gate` keeps an
  isolated probe usable when something else legitimately owns the GPU). Two configs whose
  engine-accounted requirement fits the card (3703 MiB and 5576 MiB of 8106) failed their first
  `cudaMalloc` 0.15-0.9 s after start, so a start that races the previous process's VRAM release is
  not a model verdict;
* the pre-flight probe sends `chat_template_kwargs.enable_thinking=false` and accepts a
  non-empty `reasoning_content` as proof of a live engine. Without that lever a healthy thinking
  model answers into the reasoning channel with `content: ''` at `max_tokens=8` and was being
  called dead (`ornith-9b-q4_K_M`, `qwen35-9b-q4km` on 2026-11-07).

Cause taxonomy the driver can name: `unsupported_arch`, `vram_oom`, `load_error`, `bad_flags`,
`port_busy`, `unit_failed`, `no_answer` (driver/probe defect — never a model verdict),
`transport_blocked` (the unit answers on `127.0.0.1` inside the container but not on the
sweep's endpoint: firewall/route/tailnet, measured 2026-11-07 — see below).

Measured causes on this lane (llama.cpp `a2878d3`, 2026-09-11 build):

| alias | cause | evidence |
|---|---|---|
| `dory-1.0-4b-q5km-kvq8` (+ its 3 KV rows) | `unsupported_arch`: `unknown model architecture: 'dory'`, exit 1 in 0.2 s | excluded in the manifest |
| `lfm3-1.7b-iq4nl-bartowski` | `unsupported_arch`: `'lfm3'`, exit 1 in 0.2 s | excluded in the manifest |
| `minicpm5-2b-q8_0` | `vram_oom` at 32K f16 KV **while another server held 6.4 GiB**: a single 2279.73 MiB weights buffer failed against 1.6-1.8 GiB free (`common_fit_params ... n_gpu_layers already set by user to 99, abort`) | needs ~4.3 GiB total (2550 MiB weights + 1344 MiB f16 KV at 32K + compute), so it is a **retry**, not an exclusion |
| `ornith-9b-q4_K_M`, `qwen35-9b-q4km` | probe defect, servers were live and correctly named | fixed by the probe lever above |

**Exclusions are manifest rows, not deletions.** A line beginning with `!` is
`!<alias><TAB><reason>`: the config row stays visible, the driver prints
`skip (excluded) <alias>: <reason>` and never spends 600 s on it again. `scripts/build_sweep_manifest.py`
emits them from `EXCLUDE_GGUF`, keyed by GGUF basename so every KV row of that file is covered,
and they are re-enablement-gated on an engine upgrade — not on a retry.

**The engine upgrade they were gated on now exists** (2026-11-07): `/opt/llama.cpp-dory`
(pinned PR ggml-org/llama.cpp#30306, commit `1c3cdd2`, CUDA sm_61) loads **both** `dory` and
`lfm3`. Verified as serving, not just as source support: Dory Q5_K_M answered a chat completion
on 127.0.0.1:8892 (alias `dory-1.0-4b-q5km`, `system_fingerprint b1-1c3cdd2`) and
LFM3-1.7B-IQ2_M answered too. Build/serve/VRAM notes: `/opt/llama.cpp-dory/README.fleet.md` on
the 1070 Ti container. This does **not** retro-change the running campaign: its engine stays
`a2878d3` so all 48 configs stay comparable. On the next sweep, point the worker at the dory
build and drop the `dory`/`lfm3` rows from `EXCLUDE_GGUF` — that is a configuration change
(new engine), so label those scores engine-vs-engine, never as a pure KV/quant comparison.
Dory is also expensive on 8 GB: `dory.num_loops=4` with `per_loop` KV costs ~4x normal KV per
token, so its 32K rows need q8_0/q4_0 KV.

Note: the manifest is read once at driver start, so an edit to it (or to this driver) applies to
the **next** sweep invocation, not to a sweep already running.

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
  serve are recorded as `serve_failed` **with a named cause and the engine's own log**
  (`results/_sweep_logs/<alias>-kv<ctk>.serve.log`) — a missing row is data, but only if it
  says why.
* The sweep takes the test lane for hours. Nothing else may use `grunt-pve` meanwhile; the
  shipped unit is restored (and proven with a real completion) at the end.

## The lane itself can be the failure: ufw (measured 2026-11-07 22:04 MST)

Half-way through the 0.5.0 sweep, every new TCP connection from the sweep host to
`<box>:8891` stopped completing: `ss` showed **SYN-SENT**, `curl` from the host timed out with
exit 28, while the same `curl` **inside** the container returned 200. The unit was healthy and
the model innocent. Cause: a `ufw-before6-guard.py` repair on the test container re-inserted the
`-A INPUT -j ufw-before-input` jump (`journalctl -u ufw`: "REPAIR half-loaded IPv4 INPUT"), which
re-armed the container's default-deny policy. The container is a Tailscale node with no LAN
address and ufw had no rule for `tailscale0`, so only already-`ESTABLISHED` connections kept
working — which is why the sweep looked alive while every new config died.

Fix (persistent, applied on the container):

```
ufw allow in on tailscale0 comment 'tailnet test lane (grunt)'
```

After that, 3/3 `curl` attempts from the sweep host returned 200 and the sweep resumed.

Lessons that are now in the driver:

* a config whose unit is `active` but never answers is classified `transport_blocked` only when
  loopback answers — the check runs **before** the unit is stopped, because a stopped unit cannot
  testify;
* `no_answer` therefore keeps meaning "driver/probe defect", and neither label can ever be
  blamed on a model;
* five configs (`gemma4-12b-ud-q2_K_XL`, `q8-k-xl-kvq4`, and the three `q4-k-m` rows) were lost
  to this window and are re-run rather than recorded as model failures.
