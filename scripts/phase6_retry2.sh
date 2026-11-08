#!/usr/bin/env bash
# The one manifest config no earlier pass measured: gemma4-12b-ud-q2_K_XL (a serve_failed in
# the pre-pin epoch that serves fine on an idle card). Same state file as the retry pass so
# cards_from_runs.py picks it up with the rest.
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
export GRUNT_HOST=${GRUNT_HOST:-prometheus-1}
echo "=== [retry2] gemma4-12b  $(date -Is)"
"$ROOT/.venv/bin/python" scripts/pve_sweep.py --restore-on-exit \
  --state "$ROOT/results/_sweep_state_retry.jsonl" --only "gemma4-12b-ud-q2_K_XL"
echo "=== [retry2] done rc=$?  $(date -Is)"
