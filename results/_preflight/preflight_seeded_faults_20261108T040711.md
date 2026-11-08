# Seeded-fault proof of the lane gate (20261108T040711)

Every row is a REAL fault seeded on the lane; the command is the shipped gate and
the exit code is what it returned. Reproduce with
`GRUNT_HOST=<lane> python3 scripts/preflight_seeded_faults.py`.

Lane thresholds in force: refuse temperature 80 C (card target 83 C), power ceiling 120 W, throttle-mask rule as documented in `scripts/preflight_lane.py`.

| seed | legs | expected | actual | verdict |
|---|---|---|---|---|
| unit | unit | 2 | 2 | PASS |
| gpu | gpu | 4 | 4 | PASS |
| endpoint | endpoint | 3 | 3 | PASS |
| pin | pin | 7 | 7 | PASS |
| load | load | 5 | 5 | PASS |
| thermal | thermal | 6 | 6 | PASS |
| gpu_throttle_bits | gpu | 4 | 4 | PASS |
| real_state | all | 0 | 0 | PASS |

## unit - `systemctl stop` of the worker unit - the state a crash-loop ends in

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8899 --legs unit --json
  -> exit 2 | worker unit is not serving: inactive/dead mainpid=0 restarts=0 (exec_status=0)
```

## gpu - real `llama-server -ngl 0` on the lane's model (endpoint up=True): the card is not doing the work

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8899 --legs gpu --json
  -> exit 4 | engine is NOT on the GPU: memory.used=169 MiB while the unit is serving - the silent llama.cpp CPU fallback (a speed number here is a CPU number)
  card while the -ngl 0 engine served: 169.0 MiB, 0.0 % util
```

## endpoint - healthy unit, gate pointed at the dead port 8899 (a stale --port reaches the wrong server)

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8899 --legs unit,endpoint --json
  -> exit 3 | lane endpoint failed its own gates (probe rc=1): FAIL reach    no TCP answer on http://LANE (wrong port / container down / not on tailnet)
```

## pin - `nvidia-smi -pl 180` above the 120 W ceiling, restored after the gate

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8891 --legs pin --json
  -> exit 7 | power limit is 180.0 W, above the 120 W ceiling: at the card's default limit SW thermal slowdown fired on 29.1 % of loaded samples (0 % at the ceiling), so this run is not attributable
```

## load - `llama-bench` on the lane's model holding the card while the gate ran (somebody else's benchmark is not comparable)

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8891 --legs load --json
  -> exit 5 | foreign load on the card (not in the allow-list ['llama-server']): /opt/llama.cpp/build/bin/llama-bench pid 1453988 holding 1796 MiB - its memory bandwidth is not yours
```

## thermal - 3 decode streams until the card reached the refuse line (this is the state a run begun straight after a loaded config lands in)

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8891 --legs thermal --json
  -> exit 6 | card is 81 C, at/over the 80 C refuse line (83 C target): let it cool, or the first minutes of the run land in the 8.8-17.4 % throttled band
  burn trail: 76C/0x0000000000000004/176.03W 80C/0x0000000000000004/179.73W
```

## gpu_throttle_bits - hard throttle bit set by real heat: the gpu leg refuses the run that would otherwise score the throttle as the config

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8891 --legs gpu --json
  -> exit 4 | hard throttle reason active before the run: SW_THERMAL_SLOWDOWN(0x020) (masks ['0x0000000000000020', '0x0000000000000020', '0x0000000000000020'], 82, 1733 MHz of 1911 MHz, 163.59 W, util 100 %) - a run begun here scores the throttle
  card during the gate: 82.0 C, mask 0x0000000000000020, 163.71 W
```

## real_state - unseeded lane after restore: everything the gate asks for is true

```
preflight_lane.py --host LANE --ssh pve --ct 100 --unit llama-worker@8891 --port 8891 --legs unit,endpoint,gpu,load,thermal,pin --json
  -> exit 0 | unit: active/running mainpid=936437 restarts=0; endpoint: RESULT green (http://LANE) model=gemma4-12b-ud-q2_K_XL; gpu: mask 0x0000000000000000 clean; clock 1607 of 1911 MHz at 0 % util is NOT a fault (idle is a state, not a throttle - the rule lives in the header); 5697 MiB resident on the card; load: no foreign process (1456764, /opt/llama.cpp/build/bin/llama-server, 5692 MiB); util [0, 0, 0] %; thermal: 65 C, 18 C below the target ceiling; pin: persistence=Enabled, power.limit=120.0 W <= 120 W
  worker answered /v1/models again: True
```
