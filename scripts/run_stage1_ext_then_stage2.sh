#!/bin/bash
# Driver chain v2 (subagent e476d065, Nov 9 12:10 MST): Phase M ext ->
# Stage 2 main -> Stage 2 gap. v1 chain was killed and replaced because its
# pgrep wait-pattern self-matched an immortal tailscaled wrapper cmdline
# containing the literal manifest string. v2 signals on the Phase M state
# file (39 done) instead — already true at replacement time.
cd ~/TysAIs/slm-gauntlet || exit 1
export GRUNT_HOST=${GRUNT_HOST:?set GRUNT_HOST to the test-lane host}
PY=.venv/bin/python
L=results/_sweep_state_phase_m_v060.jsonl
while true; do
  n=$(python3 -c "import json; print(sum(1 for l in open(\"$L\") if l.strip()))" 2>/dev/null || echo 0)
  [ "$n" -ge 39 ] && break
  sleep 60
done
echo "[chain2] $(date) Phase M main complete ($n lines); launching Phase M ext (19 rows)"
$PY scripts/pve_sweep.py --manifest scripts/sweep_manifest_phase_m_ext_v060.tsv --state results/_sweep_state_phase_m_ext_v060.jsonl --restore-on-exit >> results/_p4_logs/phase_m_ext.log 2>&1
echo "[chain2] $(date) Phase M ext exited rc=$?; launching Stage 2 main (195 rows)"
$PY scripts/pve_sweep.py --manifest scripts/sweep_manifest_phase_ext_v060.tsv --state results/_sweep_state_phase_ext_v060.jsonl --restore-on-exit >> results/_p4_logs/phase_ext.log 2>&1
echo "[chain2] $(date) Stage 2 main exited rc=$?; launching Stage 2 gap (14 rows)"
$PY scripts/pve_sweep.py --manifest scripts/sweep_manifest_phase_ext_gap_v060.tsv --state results/_sweep_state_phase_ext_gap_v060.jsonl --restore-on-exit >> results/_p4_logs/phase_ext_gap.log 2>&1
echo "[chain2] $(date) Stage 2 gap exited rc=$?; CHAIN COMPLETE"
