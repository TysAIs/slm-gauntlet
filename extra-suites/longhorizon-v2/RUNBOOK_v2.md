# Long-horizon v2 — sweep runbook (for the sweep executor)

Suite dir (AREO): `slm-gauntlet/extra-suites/longhorizon-v2/`
Bench: `python3 lh-bench-v2r.py --endpoint http://127.0.0.1:8080/v1 --model <id>
  --doc longhorizon_doc_v2.txt --tasks longhorizon_tasks_v2r.json
  --out results_<id>-v2r.json`  (25 tasks, 9 families; per-family subscores in JSON)
Tunnel: AREO systemd user service `gauntlet-tunnel.service` (already active;
endpoint is http://127.0.0.1:8080/v1 from AREO, NEVER the PVE host's own :8080 —
PVE firewall DROPs 8080; only 22/8006/9100 are allowed).

## Serve (PVE, via AREO ssh with staging key ~/migration-backup/dotfiles/.ssh/id_ed25519)

```
/opt/llama-new/llama-dory-merge/build/bin/llama-server -m <gguf> \
  --host 0.0.0.0 --port 8080 -c 102400 -np 8 --kv-unified --jinja --temp 0.0 -ngl 99 \
  [--cache-type-k <kv> --cache-type-v <kv>]   # omit for FP16 (default f16)
```
- KV values: f16 (FP16), q8_0, q4_0. NEVER label q8_0 as FP8 or q4_0 as FP4.
- GGUF dirs on PVE (/mnt/data/models/): spark-x2.6-4b, spark-x2.6-4b-xhtoken,
  spark-x2.6-4b-bartowski, spark-x2.6-1.7b, spark-x2.6-1.7b-xhtoken,
  minicpmv47-1b, lfm3-1.7b, qwen35-9b, lfm25-1.2b, lfm25-8b-a1b.
  (Bolt dir: see run log; Bolt is model-excluded anyway — do not serve it.)
- One server at a time. After each bench: kill the server PID, verify GPU free
  (`nvidia-smi` memory.used = 2 MiB) before the next serve.
- At each serve, RE-VERIFY spare >= 1024 MiB (FIT_LIST.md values are from mixed
  builds). If spare < 1024, record does-not-fit for that variant and move on —
  never force, never OOM.

## Sweep order and scope

- Eligible: 184 variants (FIT_LIST.md). Task file: longhorizon_tasks_v2r.json (25 tasks). Start with the 3 LH-only additions if
  convenient (Qwen q4_0, LFM2.5-1.2B Q8 FP16, LFM2.5-8B UD-Q4 FP16), then the
  table in family order. Skip: all Bolt (65536 cap), Dory q8_0 (OOM),
  Spark-4B Q8 FP16 (OOM), all FP16-FLAGGED Spark-4B quants at FP16 only
  (their q8_0/q4_0 siblings ARE eligible).
- DORY GATE (q4_0 only): before scoring, read task-1 prompt_tokens from a
  single probe call. If prompt + 256 > 102400, record Dory as does-not-fit
  for v2 and move on. Do not assume fit or failure.
- NOT-PROVEN variants (FIT_LIST.md) are NOT in this sweep. Do not add them
  without a separate fit-test step.
- v2 scores go in their own leaderboard section. NEVER overwrite 32K scores.
- No wipe, no deletions, no Sparks work, no push.

## Health aborts (stop the run, record, do not retry blindly)

- GPU temp: HARD abort at 84C. > 80C is watch-and-record pending Tyler's
  decision (see criteria doc §8.1): sustained 100K prefills plateau at
  81-82C on this card, so a literal > 80C abort would kill every run.
  Record peak temp per run regardless.
- PVE RAM available < 500 MB, swap use > 4 GB, VRAM headroom < 1 GiB at serve.
- Server unhealthy, HTTP 400 on every task (context overflow), or slot stuck:
  record the mode, kill the server, verify GPU free, move to the next variant.

## Bench notes (learned in validation)

- Run the bench with nohup + a log file; do NOT run it in the foreground of
  an ssh session that you then wait on — the ssh session lingers while the
  bench holds the session (observed in validation). Poll with fresh short
  calls: bench PID, results file existence, `nvidia-smi`, server log tail.
- Bench prints only at the end (results JSON). Per-turn prompt_tokens,
  latency, max_tokens used, and tokenize estimates are in the JSON rows.
- Expected runtimes are long for reasoning models (Qwen v1 multihop alone
  took 681s). Do not declare a stall from a single slow task; check
  n_gen advancing in the server log first.
- A task that returns HTTP 400 for every task = prompt over cap (record
  does-not-fit for that tokenizer), not a model-quality score.
