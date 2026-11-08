#!/usr/bin/env bash
# Phase-6 retry pass (2026-11-07 23:5x): the 4 `no_answer` configs + the 3 configs that
# were measured before the 120 W pin existed. Fresh state file so nothing is skipped.
# Every pass restores the shipped unit on exit. Resume-safe: re-running skips done rows.
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
export GRUNT_HOST=${GRUNT_HOST:-prometheus-1}
PY="$ROOT/.venv/bin/python"
STATE="$ROOT/results/_sweep_state_retry.jsonl"
run() {
  echo "=== [retry] pass --only $1  $(date -Is)"
  "$PY" scripts/pve_sweep.py --restore-on-exit --state "$STATE" --only "$1"
  echo "=== [retry] pass rc=$? --only $1  $(date -Is)"
}
run "nemotron-3.5-bolt-e4b-q4-k-m"
run "ud-q8-k-xl-kvq4"
run "spark-x2.6-4b-iq3m"
run "bolt-e4b-udiq3xxs"
run "spark-x2.6-1.7b-q8_0"
echo "=== [retry] ALL PASSES DONE $(date -Is)"
