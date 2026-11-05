#!/usr/bin/env bash
# LH v2r sweep driver — serves each manifest variant on PVE (GTX 1070 Ti),
# benches it from AREO via the tunnel, enforces runbook health rules.
# Thermal rule (Tyler, 2026-11-04): HARD abort at 89C (the 1070 Ti is rated to 94C);
# peaks are logged every 5s to /tmp/lh2_therm.log. 84C was the pre-ruling value.
set -u
SUITE="${SUITE:-$HOME/TysAIs/slm-gauntlet/extra-suites/longhorizon-v2}"
KEY="${KEY:-$HOME/migration-backup/dotfiles/.ssh/id_ed25519}"
PVE_HOST="${PVE_HOST:-pve-node}"
PVE="ssh -o ConnectTimeout=10 -o BatchMode=yes -i $KEY root@$PVE_HOST"
BIN=/opt/llama-new/llama-dory-merge/build/bin/llama-server
MANIFEST=$SUITE/sweep-manifest.tsv
DLOG=$SUITE/sweep-driver.log
STATUS=$SUITE/sweep-status.tsv
PEAKS=$SUITE/sweep-peaks.tsv
ONLY="${1:-}"
log(){ echo "[$(date -Is)] $*" | tee -a "$DLOG"; }
pve(){ $PVE "$@" 2>/dev/null; }

# --- start-of-run guards ---
if pve "pgrep -f 'llama-server.*--por[t] 8080' >/dev/null"; then
  log "FATAL: a port-8080 llama-server is already running on PVE; refusing to disturb it"; exit 1
fi
pve "rm -f /tmp/lh2_ABORT; : > /tmp/lh2_therm.log"
# thermal watchdog on PVE: sample every 5s; at >=89C kill ONLY the port-8080 server + flag abort
pve "setsid nohup bash -c 'while true; do t=\$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader); echo \"\$(date +%s) \$t\" >> /tmp/lh2_therm.log; if [ \"\$t\" -ge 89 ]; then touch /tmp/lh2_ABORT; pkill -f \"llama-server.*--por[t] 8080\"; fi; sleep 5; done' >/dev/null 2>&1 & echo \$!" > /tmp/lh2_watchdog.pid
WD=$(cat /tmp/lh2_watchdog.pid)
log "watchdog started on PVE (pid $WD), abort threshold 89C"
cleanup(){ pve "kill $WD 2>/dev/null; pkill -f 'llama-server.*--por[t] 8080' 2>/dev/null; true"; }
trap cleanup EXIT

done_count=0; total=0
while IFS=$'\t' read -r mid path kv vram label; do
  total=$((total+1))
  [ -n "$ONLY" ] && [ "$ONLY" != "$mid" ] && continue
  out=$SUITE/results_${mid}-v2r.json
  if [ -f "$out" ]; then done_count=$((done_count+1)); continue; fi
  if pve "test -f /tmp/lh2_ABORT"; then log "THERMAL ABORT flagged — stopping sweep at $mid"; echo -e "$mid\tTHERMAL_ABORT" >> "$STATUS"; exit 2; fi
  # host health gates (runbook): RAM avail >= 500MB, swap used <= 4GB
  read -r ramav swapused <<< "$(pve "free -m | awk '/^Mem:/{a=\$7} /^Swap:/{s=\$3} END{print a, s}'")"
  if [ "${ramav:-0}" -lt 500 ] || [ "${swapused:-99999}" -gt 4096 ]; then
    log "HOST HEALTH ABORT at $mid (ram_avail=${ramav}MB swap_used=${swapused}MB)"; echo -e "$mid\tHOST_ABORT" >> "$STATUS"; exit 3
  fi
  free=$(pve "nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits")
  if [ $(( vram + 1024 )) -gt "${free:-0}" ]; then
    log "DEFER $mid (needs $((vram+1024)) MiB incl. spare rule, free=${free} MiB — GPU shared)"
    echo -e "$mid\tDEFERRED_GPU_SHARED\tfree=${free}" >> "$STATUS"; continue
  fi
  kvargs=""
  [ "$kv" = "q8_0" ] && kvargs="--cache-type-k q8_0 --cache-type-v q8_0"
  [ "$kv" = "q4_0" ] && kvargs="--cache-type-k q4_0 --cache-type-v q4_0"
  log "SERVE $mid ($label, kv=$kv, fit_vram=${vram})"
  t_start=$(date +%s)
  pve "setsid nohup $BIN -m $path --alias $mid --host 0.0.0.0 --port 8080 -c 102400 -np 8 --kv-unified --jinja --temp 0.0 -ngl 99 $kvargs </dev/null > /tmp/lh2_srv_${mid}.log 2>&1 &"
  healthy=0
  for i in $(seq 1 48); do
    sleep 5
    if pve "test -f /tmp/lh2_ABORT"; then log "THERMAL ABORT during serve of $mid"; echo -e "$mid\tTHERMAL_ABORT" >> "$STATUS"; exit 2; fi
    if curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8080/health 2>/dev/null | grep -q 200; then healthy=1; break; fi
    if ! pve "pgrep -f 'llama-server.*--por[t] 8080' >/dev/null"; then break; fi
  done
  if [ "$healthy" != "1" ]; then
    log "SERVE_FAIL $mid (server log tail on PVE: /tmp/lh2_srv_${mid}.log)"
    echo -e "$mid\tSERVE_FAIL" >> "$STATUS"
    pve "pkill -f 'llama-server.*--por[t] 8080'; true"; sleep 5; continue
  fi
  used=$(pve "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits")
  log "BENCH $mid (gpu_used=${used} MiB)"
  timeout 10800 python3 "$SUITE/lh-bench-v2r.py" --endpoint http://127.0.0.1:8080/v1 \
    --model "$mid" --doc "$SUITE/longhorizon_doc_v2.txt" \
    --tasks "$SUITE/longhorizon_tasks_v2r.json" --out "$out" >> "$SUITE/sweep-bench.log" 2>&1
  t_end=$(date +%s)
  peak=$(pve "awk -v a=$t_start -v b=$t_end '\$1>=a && \$1<=b {if(\$2>m) m=\$2} END{print m}' /tmp/lh2_therm.log")
  echo -e "$mid\t${peak:-NA}\t$t_start\t$t_end" >> "$PEAKS"
  pve "pkill -f 'llama-server.*--por[t] 8080'; true"; sleep 5
  if pve "test -f /tmp/lh2_ABORT"; then log "THERMAL ABORT after $mid (peak ${peak}C)"; echo -e "$mid\tTHERMAL_ABORT" >> "$STATUS"; exit 2; fi
  if [ -f "$out" ]; then
    score=$(python3 -c "import json;d=json.load(open('$out'));print(d.get('overall', d.get('score','?')))" 2>/dev/null || echo "?")
    log "DONE $mid score=$score peak=${peak}C dur=$((t_end-t_start))s"
    echo -e "$mid\tDONE\tscore=$score peak=${peak}" >> "$STATUS"; done_count=$((done_count+1))
  else
    log "BENCH_FAIL $mid (no results file; see sweep-bench.log)"
    echo -e "$mid\tBENCH_FAIL" >> "$STATUS"
  fi
done < "$MANIFEST"
log "SWEEP PASS COMPLETE: $done_count result files present of $total manifest rows"
