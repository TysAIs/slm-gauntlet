#!/usr/bin/env python3
"""preflight_lane.py - ONE exit code answering: is the 1070 Ti test lane benchmarkable right now?

WHY THIS EXISTS
A sweep config costs 605 s to fail and a scored run on a sick card costs its whole duration.
Measured on this lane (2026-11-07/08): a config's serve attempt burned 604-698 s and left nothing;
and the shipped worker came back from a restart WEDGED - `/health` answered `{"status":"ok"}`,
`/v1/models` published an alias, and a 16-token completion never returned headers, so a bench
started then would have recorded timeouts as model quality. Both states are invisible to a
`systemctl is-active` check, so every benchmark run starts here instead.

WHAT IT REFUSES ON (each leg is a separate exit code, printed by name)
  unit       worker unit not active/running, or a dead MainPID
  endpoint   /health, /v1/models or a REAL completion fails (delegated to the sanctioned probe,
             which also catches the /health-ok-but-no-progress wedge)
  gpu        engine is not actually on the GPU (CPU fallback), or a hard throttle reason is active
  load       a foreign process owns the card, or the card is already busy with someone's benchmark
  thermal    the card is at/over the refuse temperature or thermally throttled
  pin        the sustained-load policy is not applied, so the number is not attributable

TRANSPORT IS NOT A VERDICT
A failed ssh/`pct exec`/nvidia-smi call exits 8 ("cannot ask"), never one of the fault codes. An
empty answer from a broken transport is indistinguishable from "the unit is gone", and this lane
has already recorded a healthy server as a fault that way.

THE THROTTLE-MASK RULE (why an idle clock is never a fault)
`clocks_throttle_reasons.active` is a BITMASK, not an error level. Bits, per NVIDIA's nvml.h:
  0x001 GPU_IDLE                 0x002 APPLICATIONS_CLOCKS_SETTING   0x004 SW_POWER_CAP
  0x008 HW_SLOWDOWN              0x010 SYNC_BOOST                    0x020 SW_THERMAL_SLOWDOWN
  0x040 HW_THERMAL_SLOWDOWN      0x080 HW_POWER_BRAKE_SLOWDOWN       0x100 DISPLAY_CLOCK_SETTING
Benchmarkable means: NONE of HW_SLOWDOWN, SW_THERMAL_SLOWDOWN, HW_THERMAL_SLOWDOWN or
HW_POWER_BRAKE_SLOWDOWN is set. Those are the bits that mean the card is already trading speed for
heat or power before the run starts, and a run begun there scores the throttle instead of the
config. Everything else is a state or a deliberate policy:
  * GPU_IDLE is NORMAL on an idle card. Measured 2026-11-07 on this box: 139 of 1911 MHz, 9.7 W,
    0 % util, mask 0x0000000000000001. Therefore this script NEVER compares clocks to the max
    clock to decide health - clocks are only reported, and only interpreted when the card is
    actually loaded. A "clock is below X % of max" gate is the naive check that calls a perfectly
    healthy idle card throttled.
  * SW_POWER_CAP is the 120 W pin doing its job (see the pin leg), not a fault.
  * APPLICATIONS_CLOCKS_SETTING / SYNC_BOOST / DISPLAY_CLOCK_SETTING are reported, never refused;
    none of them are in use on this lane.
  * the mask is read from THREE samples 4 s apart and ANY sample with a slowdown bit refuses:
    measured 2026-11-08 on this card under a 3-stream burn, 0x20 (SW_THERMAL) was set at 82 C and
    the very next sample read 0x0. A one-shot check calls that card healthy, and the run that
    follows then scores the slowdown as the config.

TEMPERATURE SOURCE (the one that actually answers)
Inside LXC 100 `nvidia-smi --query-gpu=temperature.gpu` returns `[Function Not Found]`, so the
thermal number is read on the PVE HOST (`nvidia-smi --query-gpu=temperature.gpu`) and the slowdown
enum from the host's `nvidia-smi -q -d PERFORMANCE`. The card's own target temperature is 83 C and
`sw_thermal_slowdown` was active on 8.8-17.4 % of loaded samples in a 13-minute 4-stream run
(receipt: the 1070 Ti thermal wall, `thermal_run.py`). A run started hot begins inside that band,
so the refuse threshold is 80 C - three degrees of margin under the target - and the measured value
is printed on every run whether it refuses or not.

USAGE
  preflight_lane.py --host <tailnet-address>                      # full gate, human output
  preflight_lane.py --host ... --legs load,thermal --json         # one machine-readable subset
  preflight_lane.py --fixture sample.json                         # replay a recorded sample
  preflight_lane.py --host ... --save-fixture out.json            # record today's sample

`--host` (or GRUNT_HOST) is required: the endpoint address is the operator's, not the repo's.
The address is deliberately absent from this file (the repo's hygiene gate bans address literals).

EXIT  0 benchmarkable / 2 unit / 3 endpoint / 4 gpu / 5 load / 6 thermal / 7 pin /
      8 cannot-ask (transport, probe missing, unparsable sample) / 10 usage error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_UNIT = "llama-worker@8891"
DEFAULT_PORT = 8891
DEFAULT_CT = "100"
DEFAULT_SSH = os.environ.get("GRUNT_SSH", "pve")

# Exit code per leg. Stable on purpose: a driver reports "REFUSED <code> <leg>" and a reader can
# tell a card problem from a transport problem without parsing prose.
LEG_EXIT = {
    "unit": 2,
    "endpoint": 3,
    "gpu": 4,
    "load": 5,
    "thermal": 6,
    "pin": 7,
}
LEG_ORDER = ("unit", "endpoint", "gpu", "load", "thermal", "pin")
E_CANNOT_ASK = 8
E_USAGE = 10

# --- thresholds, each with the measurement behind it -------------------------------------
# A card that answers nvidia-smi but holds almost nothing while a model is "loaded" is running on
# the CPU: llama.cpp falls back silently when nvidia_uvm is missing (measured 12.47 tok/s CPU vs
# 68.25 GPU on one config, 11 hours undetected).
#
# 256 MiB, not 100. Both CPU-fallback shapes were measured on this card (2026-11-08, t_837f2ef
# seeded faults): with no CUDA context at all the engine holds ~2 MiB, and `-ngl 0` on a card it
# CAN see still allocates a bare CUDA context of 169 MiB with zero layers offloaded - which a
# 100 MiB floor reads as healthy and then scores a CPU number. A real offload is an order of
# magnitude above this floor: the shipped 2B Q4 at -ngl 99 held 1796 MiB (same run). The floor is
# a "the engine is on the card" test, not a per-model one.
MIN_GPU_MEMORY_MIB = 256
# "Busy" is two consecutive samples at or above this, because one sample cannot separate a card
# that is finishing someone's benchmark from one that is idle. At preflight the card must be idle:
# a second stream during a run is memory-bandwidth contention (one retest went 3.15 -> 10.4 tok/s
# purely from running alone).
BUSY_UTIL_PCT = 10
BUSY_SAMPLE_GAP_S = 4
# Refuse-temperature: 80 C against the card's 83 C target (see the header). Thermal slowdown
# already fired at 8.8-17.4 % of loaded samples at the 180 W default limit.
THERMAL_TARGET_C = 83
THERMAL_REFUSE_C = 80
# The sustained-load policy for this lane: persistence mode on, power ceiling 120 W (measured
# 2026-11-07: 29.1 % throttled samples at the 180 W default -> 0 at 120 W, -1.8 % multi-stream).
POWER_LIMIT_CEILING_W = 120
# memory.current above memory.high only THROTTLES allocations; it collapses prefill to 1-5 tok/s
# when swap is also exhausted (measured: 4.6G against a 4G cap with swap full while /health said
# ok). Both signs are required to refuse, so a healthy server whose page cache sits above the cap
# with swap free (measured 8.7G against 8G, 6.1 GiB swap free) is not refused.
MIN_SWAP_FREE_MIB = 1024

# Mask bits (see the header table).
BIT_IDLE = 0x001
BIT_APPS_CLOCKS = 0x002
BIT_SW_POWER_CAP = 0x004
BIT_HW_SLOWDOWN = 0x008
BIT_SYNC_BOOST = 0x010
BIT_SW_THERMAL = 0x020
BIT_HW_THERMAL = 0x040
BIT_HW_POWER_BRAKE = 0x080
BIT_DISPLAY = 0x100
REFUSE_BITS = {
    BIT_HW_SLOWDOWN: "HW_SLOWDOWN",
    BIT_SW_THERMAL: "SW_THERMAL_SLOWDOWN",
    BIT_HW_THERMAL: "HW_THERMAL_SLOWDOWN",
    BIT_HW_POWER_BRAKE: "HW_POWER_BRAKE_SLOWDOWN",
}
ALLOWED_BITS = {
    BIT_IDLE: "GPU_IDLE(idle state, not a fault)",
    BIT_APPS_CLOCKS: "APPLICATIONS_CLOCKS_SETTING",
    BIT_SW_POWER_CAP: "SW_POWER_CAP(the 120 W pin working)",
    BIT_SYNC_BOOST: "SYNC_BOOST",
    BIT_DISPLAY: "DISPLAY_CLOCK_SETTING",
}

GPU_QUERY = (
    "persistence_mode,power.limit,power.draw,temperature.gpu,utilization.gpu,"
    "memory.used,memory.free,clocks.current.sm,clocks.max.sm,clocks_throttle_reasons.active"
)
UNIT_PROPS = ("ActiveState,SubState,MainPID,NRestarts,MemoryCurrent,MemoryHigh,MemoryMax,"
              "ExecMainStatus,ExecMainStartTimestamp")


class CannotAsk(RuntimeError):
    """The box did not answer. Never a verdict about the card."""


def sh(argv: list[str], timeout: int = 60, input_text: str | None = None):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          input=input_text)


class Lane:
    """The test lane's box, reached with one ssh alias and `pct exec`."""

    def __init__(self, ssh_alias: str, ct: str):
        self.ssh = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", ssh_alias]
        self.ct = ct

    def run(self, argv: list[str], timeout: int = 60):
        try:
            return sh(self.ssh + ["pct", "exec", self.ct, "--"] + argv, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CannotAsk(f"ssh+pct exec timed out after {timeout}s: {' '.join(argv)}") from exc
        except OSError as exc:
            raise CannotAsk(f"ssh failed to start: {exc}") from exc

    def host(self, argv: list[str], timeout: int = 60):
        """Run on the PVE HOST. nvidia-smi's temperature and its throttle enum only answer
        here: inside LXC 100 `temperature.gpu` returns `[Function Not Found]`, and the
        container's `--query-compute-apps` cannot see a process from another container."""
        try:
            return sh(self.ssh + argv, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CannotAsk(f"ssh host command timed out after {timeout}s: {' '.join(argv)}") from exc
        except OSError as exc:
            raise CannotAsk(f"ssh failed to start: {exc}") from exc


def parse_props(text: str) -> dict:
    out: dict = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def parse_csv_row(text: str) -> list[str]:
    row = (text or "").strip().splitlines()
    if not row:
        return []
    return [p.strip() for p in row[0].split(",")]


def to_int(value: str) -> int | None:
    m = re.match(r"-?\d+", (value or "").strip())
    return int(m.group(0)) if m else None


def to_float(value: str) -> float | None:
    m = re.match(r"-?\d+(?:\.\d+)?", (value or "").strip())
    return float(m.group(0)) if m else None


# --- sample collection: the only code that talks to the box -----------------------------

def collect_live(args) -> dict:
    lane = Lane(args.ssh, args.ct)
    sample: dict = {"source": "live", "sampled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    r = lane.run(["systemctl", "show", args.unit, "--no-pager", "-p", UNIT_PROPS], timeout=45)
    # An unreachable box gives rc!=0 AND no stdout. A unit that does not exist still gives rc=0
    # with LoadState=not-found, so treat only "no answer at all" as transport.
    if r.returncode != 0 and not (r.stdout or "").strip():
        raise CannotAsk(f"systemctl show {args.unit}: rc={r.returncode} {r.stderr.strip()[-200:]}")
    sample["unit_props"] = parse_props(r.stdout)

    r = lane.host(["cat", "/proc/meminfo"], timeout=30)
    if r.returncode != 0:
        raise CannotAsk(f"host /proc/meminfo: rc={r.returncode} {r.stderr.strip()[-200:]}")
    m = re.search(r"^SwapFree:\s+(\d+) kB", r.stdout or "", re.M)
    sample["swap_free_mib"] = round(int(m.group(1)) / 1024) if m else None

    r = lane.host(["nvidia-smi", f"--query-gpu={GPU_QUERY}", "--format=csv,noheader"], timeout=45)
    if r.returncode != 0:
        raise CannotAsk(f"host nvidia-smi: rc={r.returncode} {(r.stderr or r.stdout).strip()[-200:]}")
    sample["gpu_csv"] = (r.stdout or "").strip()

    r = lane.host(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                   "--format=csv,noheader"], timeout=45)
    if r.returncode != 0:
        raise CannotAsk(f"host nvidia-smi compute-apps: rc={r.returncode}")
    sample["compute_apps"] = (r.stdout or "").strip()

    r = lane.host(["nvidia-smi", "-q", "-d", "PERFORMANCE"], timeout=45)
    sample["perf_enum"] = (r.stdout or "") if r.returncode == 0 else ""

    # Three samples for the busy AND throttle decisions, 4 s apart. One snapshot cannot separate
    # "finishing a benchmark task" from "running one", and the slowdown bits themselves flicker:
    # measured 2026-11-08, a card at 82 C under a 3-stream burn read mask 0x20 in one sample and
    # 0x0 four seconds later. A single-sample gate therefore passed a card that was trading speed
    # for heat - the exact state that scores a slow run as a slow config.
    rows = [sample["gpu_csv"]]
    apps = [sample["compute_apps"]]
    for _ in range(2):
        time.sleep(BUSY_SAMPLE_GAP_S)
        r = lane.host(["nvidia-smi", f"--query-gpu={GPU_QUERY}", "--format=csv,noheader"],
                      timeout=45)
        if r.returncode != 0:
            raise CannotAsk(f"host nvidia-smi (extra sample): rc={r.returncode}")
        rows.append((r.stdout or "").strip())
        r = lane.host(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                       "--format=csv,noheader"], timeout=45)
        apps.append((r.stdout or "").strip() if r.returncode == 0 else apps[0])
    sample["gpu_csv_samples"] = rows
    sample["util_samples"] = [to_int(parse_csv_row(row)[4]) if len(parse_csv_row(row)) > 4 else None
                              for row in rows]
    sample["apps_samples"] = apps

    probe = resolve_health_probe(args.health_probe)
    base = args.base or f"http://{args.host}:{args.port}"
    env = dict(os.environ, GRUNT_BASE=base)
    try:
        p = subprocess.run([probe], capture_output=True, text=True, timeout=180, env=env)
    except subprocess.TimeoutExpired:
        sample["health"] = {"rc": 124, "out": "probe exceeded 180s"}
        return sample
    except OSError as exc:
        raise CannotAsk(f"health probe failed to run: {exc}") from exc
    sample["health"] = {"rc": p.returncode, "out": (p.stdout + p.stderr).strip()}
    return sample


def collect_fixture(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001 - a bad fixture is a usage error, not a card verdict
        raise CannotAsk(f"cannot read fixture {path}: {exc}") from exc
    sample = {
        "source": f"fixture:{path}",
        "sampled_at": raw.get("sampled_at") or "recorded",
        "unit_props": raw.get("unit_props") or {},
        "swap_free_mib": raw.get("swap_free_mib"),
        "gpu_csv": raw.get("gpu_csv") or "",
        "gpu_csv_samples": raw.get("gpu_csv_samples") or [],
        "compute_apps": raw.get("compute_apps") or "",
        "perf_enum": raw.get("perf_enum") or "",
        "util_samples": raw.get("util_samples") or [],
        "apps_samples": raw.get("apps_samples") or [],
        "health": raw.get("health") or {},
    }
    if not sample["util_samples"] and sample["gpu_csv"]:
        row = parse_csv_row(sample["gpu_csv"])
        sample["util_samples"] = [to_int(row[4])] if len(row) > 4 else []
    if not sample["apps_samples"]:
        sample["apps_samples"] = [sample["compute_apps"]]
    return sample


def resolve_health_probe(explicit: str | None) -> str:
    """The sanctioned probe is the only authority on "does the lane answer".

    It gates /health AND /v1/models AND a real completion, and it knows "busy is not down".
    Duplicating those gates here would create a second, drifting definition of liveness.
    """
    candidates = []
    if explicit:
        candidates.append(os.path.expanduser(explicit))
    if os.environ.get("GRUNT_HEALTH"):
        candidates.append(os.path.expanduser(os.environ["GRUNT_HEALTH"]))
    home = os.path.expanduser("~")
    for rel in (
        os.path.join(".hermes", "skills", "mlops", "local-llm-serving", "scripts",
                     "grunt_health.sh"),
        os.path.join(".hermes", "profiles", "invincible", "skills", "mlops",
                     "local-llm-serving", "scripts", "grunt_health.sh"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "grunt_health.sh"),
    ):
        candidates.append(os.path.join(home, rel) if not rel.startswith("/") else rel)
    for c in candidates:
        if c and Path(c).is_file():
            return c
    raise CannotAsk(
        "sanctioned lane probe not found - pass --health-probe PATH or set GRUNT_HEALTH "
        "(it is scripts/grunt_health.sh in the local-llm-serving skill)"
    )


# --- verdicts: pure functions over a sample ---------------------------------------------

def judge_unit(sample: dict) -> dict:
    p = sample.get("unit_props") or {}
    active, sub, pid = p.get("ActiveState", "?"), p.get("SubState", "?"), to_int(p.get("MainPID", "0"))
    detail = (f"{p.get('ActiveState', '?')}/{p.get('SubState', '?')} mainpid={p.get('MainPID', '?')} "
              f"restarts={p.get('NRestarts', '?')}")
    data = {"active_state": active, "sub_state": sub, "main_pid": pid,
            "restarts": p.get("NRestarts"), "memory_current": p.get("MemoryCurrent"),
            "memory_high": p.get("MemoryHigh"), "swap_free_mib": sample.get("swap_free_mib")}
    if active != "active" or sub != "running" or not pid:
        return {"leg": "unit", "ok": False,
                "detail": f"worker unit is not serving: {detail} "
                          f"(exec_status={p.get('ExecMainStatus', '?')})", "data": data}
    # The cap trap: memory.current above memory.high throttles allocations, and with swap gone it
    # collapses prefill to 1-5 tok/s while /health still answers ok.
    cur, high = to_int(p.get("MemoryCurrent", "")), to_int(p.get("MemoryHigh", ""))
    swap = sample.get("swap_free_mib")
    if cur and high and swap is not None and cur > high and swap < MIN_SWAP_FREE_MIB:
        return {"leg": "unit", "ok": False,
                "detail": (f"unit is memory-capped and out of swap: memory.current="
                           f"{cur // 1048576} MiB > memory.high={high // 1048576} MiB with only "
                           f"{swap} MiB swap free - prefill collapses here while /health stays ok"),
                "data": data}
    if cur and high and cur > high:
        detail += (f" | memory.current {cur // 1048576} MiB above memory.high {high // 1048576} MiB "
                   f"but {swap} MiB swap free (throttled allocations, not a collapse)")
    return {"leg": "unit", "ok": True, "detail": detail, "data": data}


def judge_endpoint(sample: dict) -> dict:
    h = sample.get("health") or {}
    rc, out = h.get("rc"), (h.get("out") or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    # The probe prints one FAIL line naming its own gate, then a RESULT line: keep the diagnosis.
    fail = next((ln for ln in lines if ln.startswith("FAIL")), None)
    tail = fail or (lines[-1] if lines else "no output")
    if rc == 0:
        return {"leg": "endpoint", "ok": True, "detail": tail, "data": {"probe_rc": rc}}
    return {"leg": "endpoint", "ok": False,
            "detail": f"lane endpoint failed its own gates (probe rc={rc}): {tail}",
            "data": {"probe_rc": rc}}


def judge_gpu(sample: dict) -> dict:
    raws = sample.get("gpu_csv_samples") or [sample.get("gpu_csv") or ""]
    parsed = [parse_csv_row(raw) for raw in raws]
    for row in parsed:
        if len(row) < 10:
            raise CannotAsk(f"unparsable nvidia-smi row: {row!r}")
    row = parsed[0]
    persistence, power_limit, power_draw, temp, util, mem_used, mem_free, sm, sm_max, mask_s = row
    masks: list[int] = []
    for prow in parsed:
        raw_mask = prow[9]
        if not re.fullmatch(r"0x[0-9a-fA-F]+", raw_mask or ""):
            raise CannotAsk(f"unparsable throttle mask {raw_mask!r}")
        masks.append(int(raw_mask, 16))
    mask = masks[0]
    # ANY sample with a refuse bit is a refusal: the bits flicker under load (measured 0x20 then
    # 0x0 four seconds later at 82 C), and the run that follows samples over minutes, not once.
    bits = sorted({f"{REFUSE_BITS[b]}(0x{b:03x})" for m in masks for b in REFUSE_BITS if m & b})
    allowed = sorted(f"{ALLOWED_BITS[b]}" for b in ALLOWED_BITS if mask & b)
    unknown = mask & ~(sum(REFUSE_BITS) | sum(ALLOWED_BITS))
    # Maximum resident, not the first sample: a transient dip must not accuse a healthy card.
    used = max((to_int(prow[5]) or 0) for prow in parsed)
    data = {
        "throttle_mask": f"0x{mask:016x}",
        "throttle_masks_sampled": [f"0x{m:016x}" for m in masks],
        "refuse_bits": bits, "allowed_bits": allowed,
        "gpu_memory_used_mib": used, "gpu_memory_free_mib": to_int(mem_free),
        "util_pct": to_int(util), "power_draw_w": to_float(power_draw),
        "power_limit_w": to_float(power_limit), "persistence_mode": persistence,
        "clocks_sm_mhz": to_int(sm), "clocks_sm_max_mhz": to_int(sm_max),
        "temperature_c": to_int(temp), "unknown_bits": f"0x{unknown:03x}" if unknown else None,
    }
    if used < MIN_GPU_MEMORY_MIB:
        return {"leg": "gpu", "ok": False,
                "detail": (f"engine is NOT on the GPU: memory.used={used} MiB while the unit is "
                           f"serving - the silent llama.cpp CPU fallback (a speed number here is a "
                           f"CPU number)"), "data": data}
    if bits:
        return {"leg": "gpu", "ok": False,
                "detail": (f"hard throttle reason active before the run: {', '.join(bits)} "
                           f"(masks {data['throttle_masks_sampled']}, {temp}, {sm} of {sm_max}, "
                           f"{power_draw}, util {util}) - a run begun here scores the throttle"),
                "data": data}
    note = f"mask {data['throttle_mask']} clean"
    if allowed:
        note += f" ({'; '.join(allowed)})"
    if to_int(util) is not None and (to_int(util) or 0) <= BUSY_UTIL_PCT:
        note += (f"; clock {to_int(sm)} of {to_int(sm_max)} MHz at {to_int(util)} % util is NOT a "
                 f"fault (idle is a state, not a throttle - the rule lives in the header)")
    return {"leg": "gpu", "ok": True,
            "detail": f"{note}; {used} MiB resident on the card", "data": data}


def judge_thermal(sample: dict) -> dict:
    raws = sample.get("gpu_csv_samples") or [sample.get("gpu_csv") or ""]
    parsed = [parse_csv_row(raw) for raw in raws if parse_csv_row(raw)]
    temps = [to_int(prow[3]) for prow in parsed if len(prow) > 3]
    temps = [t for t in temps if t is not None]
    # The hottest sample and ANY sample's slowdown bit: the bit is intermittent under load, so a
    # single clean snapshot is not evidence that the card is not trading speed for heat.
    temp = max(temps) if temps else None
    mask_any = 0
    for prow in parsed:
        if len(prow) > 9 and re.fullmatch(r"0x[0-9a-fA-F]+", prow[9] or ""):
            mask_any |= int(prow[9], 16)
    enum = sample.get("perf_enum") or ""
    sw_thermal = "SW Thermal Slowdown               : Active" in enum or bool(mask_any & BIT_SW_THERMAL)
    data = {"temperature_c": temp, "source": "host nvidia-smi temperature.gpu",
            "target_c": THERMAL_TARGET_C, "refuse_c": THERMAL_REFUSE_C,
            "throttle_masks_sampled": [prow[9] for prow in parsed if len(prow) > 9],
            "sw_thermal_slowdown": sw_thermal}
    if temp is None:
        raise CannotAsk(f"no temperature in host nvidia-smi row: {sample.get('gpu_csv')!r}")
    if sw_thermal:
        return {"leg": "thermal", "ok": False,
                "detail": (f"SW thermal slowdown is already active at {temp} C (card target "
                           f"{THERMAL_TARGET_C} C)"), "data": data}
    if temp >= THERMAL_REFUSE_C:
        return {"leg": "thermal", "ok": False,
                "detail": (f"card is {temp} C, at/over the {THERMAL_REFUSE_C} C refuse line "
                           f"({THERMAL_TARGET_C} C target): let it cool, or the first minutes of the "
                           f"run land in the 8.8-17.4 % throttled band"), "data": data}
    return {"leg": "thermal", "ok": True,
            "detail": f"{temp} C, {THERMAL_TARGET_C - temp} C below the target ceiling", "data": data}


def judge_load(sample: dict, allow_procs: list[str]) -> dict:
    apps_text = sample.get("apps_samples") or [sample.get("compute_apps") or ""]
    seen: dict[str, dict] = {}
    for text in apps_text:
        for line in (text or "").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2 or not parts[0]:
                continue
            name = parts[1]
            if any(a.lower() in name.lower() for a in allow_procs):
                continue
            seen.setdefault(name, {"pid": parts[0], "process": name,
                                   "used_memory": parts[2] if len(parts) > 2 else "?"})
    utils = [u for u in (sample.get("util_samples") or []) if u is not None]
    busy = bool(utils) and len(utils) >= 2 and all(u >= BUSY_UTIL_PCT for u in utils)
    data = {"compute_apps": apps_text[0], "foreign": list(seen.values()),
            "util_samples_pct": utils, "allowed_processes": allow_procs,
            "busy_util_pct": BUSY_UTIL_PCT}
    if seen:
        who = "; ".join(f"{v['process']} pid {v['pid']} holding {v['used_memory']}"
                        for v in seen.values())
        return {"leg": "load", "ok": False,
                "detail": (f"foreign load on the card (not in the allow-list "
                           f"{allow_procs}): {who} - its memory bandwidth is not yours"),
                "data": data}
    if busy:
        return {"leg": "load", "ok": False,
                "detail": (f"card is busy: util {utils} % across {BUSY_SAMPLE_GAP_S}s "
                           f"(>= {BUSY_UTIL_PCT} % on every sample) - another run owns it, and a "
                           f"second stream costs memory bandwidth"), "data": data}
    note = f"no foreign process ({apps_text[0].strip() or 'none resident'})"
    if utils:
        note += f"; util {utils} %"
    return {"leg": "load", "ok": True, "detail": note, "data": data}


def judge_pin(sample: dict, ceiling_w: float) -> dict:
    row = parse_csv_row(sample.get("gpu_csv") or "")
    if len(row) < 3:
        raise CannotAsk(f"unparsable nvidia-smi row: {sample.get('gpu_csv')!r}")
    persistence, power_limit = row[0], to_float(row[1])
    data = {"persistence_mode": persistence, "power_limit_w": power_limit,
            "ceiling_w": ceiling_w}
    if not persistence.lower().startswith("enabled"):
        return {"leg": "pin", "ok": False,
                "detail": (f"persistence mode is {persistence!r}: without it the driver's clocks "
                           f"are not held between configs, so two identical configs are not "
                           f"comparable"), "data": data}
    if power_limit is None:
        raise CannotAsk(f"unparsable power.limit {row[1]!r}")
    if power_limit > ceiling_w + 0.5:
        return {"leg": "pin", "ok": False,
                "detail": (f"power limit is {power_limit} W, above the {ceiling_w} W ceiling: at "
                           f"the card's default limit SW thermal slowdown fired on 29.1 % of loaded "
                           f"samples (0 % at the ceiling), so this run is not attributable"),
                "data": data}
    return {"leg": "pin", "ok": True,
            "detail": f"persistence={persistence}, power.limit={power_limit} W <= {ceiling_w} W",
            "data": data}


def run_legs(sample: dict, legs: list[str], args) -> list[dict]:
    results: list[dict] = []
    for leg in legs:
        try:
            if leg == "unit":
                r = judge_unit(sample)
            elif leg == "endpoint":
                r = judge_endpoint(sample)
            elif leg == "gpu":
                r = judge_gpu(sample)
            elif leg == "load":
                r = judge_load(sample, args.allow_proc)
            elif leg == "thermal":
                r = judge_thermal(sample)
            elif leg == "pin":
                r = judge_pin(sample, args.power_limit_ceiling_w)
            else:  # pragma: no cover - argparse already validates
                raise CannotAsk(f"unknown leg {leg!r}")
        except CannotAsk:
            raise
        except Exception as exc:  # noqa: BLE001 - a broken sample must not read as a fault
            raise CannotAsk(f"leg {leg!r} could not be evaluated: {exc}") from exc
        results.append(r)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="One exit code: is the 1070 Ti test lane benchmarkable right now?")
    ap.add_argument("--host", default=os.environ.get("GRUNT_HOST", ""),
                    help="lane address (or GRUNT_HOST); required unless --fixture")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--base", default="", help="full base URL override, e.g. for a wrong-port seed")
    ap.add_argument("--ssh", default=DEFAULT_SSH)
    ap.add_argument("--ct", default=DEFAULT_CT, help="container id holding the worker unit")
    ap.add_argument("--unit", default=DEFAULT_UNIT)
    ap.add_argument("--legs", default=",".join(LEG_ORDER),
                    help=f"comma list, subset of {','.join(LEG_ORDER)} (default: all)")
    ap.add_argument("--skip", default="", help="comma list of legs to skip")
    ap.add_argument("--allow-proc", action="append", default=None,
                    help="process-name substring allowed to hold the card (repeatable; "
                         "default: llama-server)")
    ap.add_argument("--health-probe", default=None,
                    help="path to the sanctioned lane probe (default: discovered, or $GRUNT_HEALTH)")
    ap.add_argument("--power-limit-ceiling-w", type=float, default=POWER_LIMIT_CEILING_W)
    ap.add_argument("--fixture", default=None, help="replay a recorded sample instead of the box")
    ap.add_argument("--save-fixture", default=None, help="write the sample this run used")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.allow_proc is None:
        args.allow_proc = ["llama-server"]

    legs = [name.strip() for name in args.legs.split(",") if name.strip()]
    skip = {name.strip() for name in args.skip.split(",") if name.strip()}
    bad = [name for name in legs if name not in LEG_EXIT]
    if bad:
        print(f"preflight: unknown leg(s) {bad}; known: {list(LEG_ORDER)}", file=sys.stderr)
        return E_USAGE
    legs = [name for name in legs if name not in skip]
    if not legs:
        print("preflight: no legs left to run", file=sys.stderr)
        return E_USAGE
    if not args.fixture and not (args.host or args.base):
        print("preflight: --host (or GRUNT_HOST) is required unless --fixture is used",
              file=sys.stderr)
        return E_USAGE

    started = time.time()
    try:
        sample = collect_fixture(Path(args.fixture).expanduser()) if args.fixture \
            else collect_live(args)
        results = run_legs(sample, legs, args)
    except CannotAsk as exc:
        payload = {"ok": False, "refused": "cannot_ask", "exit": E_CANNOT_ASK,
                   "detail": str(exc), "source": args.fixture or "live"}
        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(f"REFUSED cannot_ask (exit {E_CANNOT_ASK}): {exc}")
        return E_CANNOT_ASK

    if args.save_fixture:
        # Sanitize the recorded sample before it is committed: the probe's output carries the
        # lane's address, and the repo's hygiene gate bans address literals in tracked files.
        blob = re.sub(r"http://[^\s)\"',]+", "http://LANE", json.dumps(sample, indent=2,
                                                                      default=str))
        Path(args.save_fixture).expanduser().write_text(blob)

    failed = [r for r in results if not r["ok"]]
    exit_code = LEG_EXIT[failed[0]["leg"]] if failed else 0
    payload = {
        "ok": not failed,
        "refused": failed[0]["leg"] if failed else None,
        "exit": exit_code,
        "source": sample.get("source"),
        "sampled_at": sample.get("sampled_at"),
        "lane": {"unit": args.unit, "ct": args.ct, "base": args.base or
                 (f"http://{args.host}:{args.port}" if args.host else None)},
        "seconds": round(time.time() - started, 1),
        "legs": [{"leg": r["leg"], "ok": r["ok"], "detail": r["detail"], "data": r["data"]}
                 for r in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        for r in results:
            print(f"{'PASS' if r['ok'] else 'FAIL'} {r['leg']:<8} {r['detail']}")
        if failed:
            print(f"RESULT refused leg={failed[0]['leg']} exit={exit_code} "
                  f"({sample.get('source')})")
        else:
            print(f"RESULT benchmarkable exit=0 ({sample.get('source')}, "
                  f"{payload['seconds']}s)")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
