#!/usr/bin/env python3
"""Swap-and-measure sweep driver for the PVE GTX 1070 Ti test box (provider grunt-pve).

WHY THIS EXISTS
The gauntlet corpus was produced by per-model hand runs and a Mac-era night queue that
spoke `ssh pve-lab` + port 18081. Neither matches the current test lane (CT100,
`llama-worker@8891.service`, the box's tailnet address on port 8891), so a whole-suite
re-run had no driver. This is that driver, and it is resume-safe because a full re-run
spans hours.

WHAT IT DOES, PER MANIFEST ENTRY
  1. write a systemd drop-in for llama-worker@8891 that replaces ExecStart with the
     config's model, alias, context, slots and KV types (the shipped template hardcodes
     MiniCPM; a drop-in keeps the unit's Restart/MemoryHigh policy intact)
  2. daemon-reload + restart, then wait for BOTH /props model_path and /v1/models alias to
     match the intended config - a stale server answers every liveness check
  3. run `python -m gauntlet.cli run --suite all --thermal-limit 89` against it
  4. append a state line (alias, path, ctx, kv, result file, rc, score) to the state file

STATE + RESUME
  `--state` (default results/_sweep_state.jsonl, gitignored with results/*) is appended
  line-buffered, one JSON object per attempt. A re-run skips entries already marked
  `done` whose result file still exists, so a crash, a reboot or a crashed agent session
  costs one config, not the sweep.

MANIFEST FORMAT (TSV, one config per line, '#' comments ignored)
  alias<TAB>gguf_path<TAB>ctx<TAB>np<TAB>ctk<TAB>ctv[<TAB>extra_flags]
  - gguf_path is absolute on the CT (/mnt/data/...)
  - ctk/ctv are llama.cpp KV types: f16, q8_0, q4_0
  - extra_flags may carry e.g. "--reasoning-budget 0 -fa on"

RESTORE
  `--restore` removes the drop-in, daemon-reloads, restarts the shipped unit and proves a
  real completion answers before returning 0. `--restore-on-exit` does that automatically
  at the end of a sweep (default when the sweep is not interrupted).

FAILURE EVIDENCE (why this file now writes logs for failures too)
  Measured 2026-11-07 on the lane: seven configs were recorded `serve_failed` after a
  604-698 s wait and left *nothing* behind - no log, no engine error, no exit code - so the
  0.5.0 table lost those rows and nobody could say why. The engine had in fact printed the
  reason in under a second (`unknown model architecture: 'dory'`, `cudaMalloc failed: out of
  memory`). Two defects, both fixed here:
    * the attempt now streams the unit's own stdout/stderr into
      results/_sweep_logs/<alias>-kv<ctk>.serve.log from before the restart, and a failed
      config records a named cause (`serve_cause`) plus a tail in the state line;
    * a unit that has already crashed is failed fast (a couple of restart attempts) instead
      of being polled for the full HEALTH_TIMEOUT_S.
  The pre-flight completion probe also sends `enable_thinking: false` and accepts a
  reasoning-only answer, because a live thinking model answers into `reasoning_content` with
  `content: ''` at max_tokens=8 and was being called dead (ornith-9b, qwen35-9b).

EXCLUSIONS
  A manifest line beginning with `!` is an exclusion, not a config:
      !<alias><TAB><reason>
  The matching config row is skipped with `skip (excluded)` and its reason, instead of being
  retried forever. Use it for a GGUF the deployed engine cannot load at any context.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT = "llama-worker@8891"


def dropin_paths(unit: str) -> tuple[str, str]:
    """Drop-in directory and file for a unit instance. Keyed by unit, not hardcoded, so an
    isolated probe can run on `llama-worker@8893` without touching the sweep's unit."""
    d = f"/etc/systemd/system/{unit}.service.d"
    return d, f"{d}/50-sweep.conf"


DEFAULT_PORT = 8891
HEALTH_TIMEOUT_S = 600

# A crash-looping unit never serves, so waiting the full HEALTH_TIMEOUT_S for it is pure
# loss. Measured 2026-11-07: `dory` and `lfm3` exit 166-259 ms after start with an
# "unknown model architecture" error and each cost the sweep 604-605 s anyway. A unit that
# has failed FASTFAIL_RESTARTS invocations without ever answering HTTP is concluded dead.
FASTFAIL_RESTARTS = 2
FASTFAIL_MIN_S = 20
UNIT_PROBE_INTERVAL_S = 6
UNIT_STATE_PROPS = "ActiveState,SubState,NRestarts,ExecMainCode,ExecMainStatus,Result"

# Free-VRAM gate before starting a config: 8 GiB card, configs need 2.5-5.6 GiB, and a config has
# been seen to fail its first cudaMalloc 0.15 s after start while the previous config's server was
# still releasing its memory. Wait (bounded) for the card to look empty, then proceed and log what
# it looked like either way.
VRAM_GATE_MIN_MIB = 4800
VRAM_GATE_TIMEOUT_S = 45

# Sustained-load pins for the box's GTX 1070 Ti. Measured 2026-11-07 on this card with
# the identical 13-minute 4-stream thermal test (receipt:
# invincible/missions/work/2026-11-07-1070ti-sustained-policy.md): at the default 180 W
# limit the card regulates to its own 83 C target temperature and SW thermal slowdown was
# active on 29.1% of loaded samples, with SM clock wandering 1632-1835 MHz - so whichever
# config landed in a throttled minute scored lower than the same config scored cool.
# Locked GPU clocks (-lgc) and application clocks (-ac) are NOT supported on this GeForce
# card (nvidia-smi: "Setting locked GPU clocks is not supported", exit 0 and silently
# ignored), so persistence mode plus a power ceiling the cooling holds with margin is the
# whole lever set. 120 W: 0 slowdown samples, plateau 74.8 C against an 83 C target, and
# no measurable cost at the sweep's own load (one client stream never reaches the ceiling).
GPU_POWER_LIMIT_W = 120
GPU_PIN_QUERY = (
    "persistence_mode,power.limit,power.draw,clocks.current.sm,temperature.gpu,"
    "clocks_event_reasons.active"
)


def sh(cmd: list[str], timeout: int = 120, input_text: str | None = None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input_text)


class Lane:
    """The test lane's box, reached with one ssh alias and pct exec."""

    def __init__(self, ssh_alias: str, ct: str):
        self.ssh = ["ssh", "-o", "ConnectTimeout=20", "-o", "BatchMode=yes", ssh_alias]
        self.ct = ct
        self.base = ["pct", "exec", ct, "--"]

    def run(self, argv: list[str], timeout: int = 120, stdin: str | None = None):
        return sh(self.ssh + self.ct_cmd(argv), timeout=timeout, input_text=stdin)

    def host_run(self, argv: list[str], timeout: int = 60):
        """Run on the PVE HOST, not inside the CT: nvidia-smi settings live there
        (inside the CT, temperature.gpu answers "Function Not Found")."""
        return sh(self.ssh + argv, timeout=timeout)

    def ct_cmd(self, argv: list[str]) -> list[str]:
        return self.base + argv

    def write_remote(self, path: str, content: str) -> None:
        r = self.run(["tee", path], stdin=content)
        if r.returncode != 0:
            raise RuntimeError(f"tee {path} failed: {r.stderr[-300:]}")

    def http_json(self, url: str, timeout: int = 10):
        with urllib.request.urlopen(url, timeout=timeout) as fh:
            return json.loads(fh.read().decode())


def serve_argv(entry: dict) -> list[str]:
    """The exact ExecStart for a config. One function so the drop-in, the captured log
    header and any isolated re-run all agree on the command."""
    argv = [
        "/opt/llama.cpp/build/bin/llama-server",
        "-m", entry["path"],
        "--alias", entry["alias"],
        "--host", "0.0.0.0",
        "--port", str(entry.get("port", DEFAULT_PORT)),
        "--jinja",
        "-ngl", "99",
        "-t", str(entry.get("threads", 6)),
        "-tb", str(entry.get("threads", 6)),
        "-c", str(entry["ctx"]),
        "-np", str(entry.get("np", 1)),
        "--kv-unified",
        "-ctk", entry.get("ctk", "f16"),
        "-ctv", entry.get("ctv", "f16"),
        "--repeat-penalty", "1.15",
        "--temp", "0.7",
        "--top-p", "0.95",
        "--min-p", "0.0",
    ]
    extra = entry.get("extra") or ""
    if extra:
        argv += shlex.split(extra)
    return argv


def dropin_text(entry: dict) -> str:
    """A drop-in that replaces ExecStart outright (empty value first, then the real one)."""
    wrapped = " \\\n  ".join(shlex.quote(a) for a in serve_argv(entry))
    return (
        "[Service]\n"
        "ExecStart=\n"
        f"ExecStart={wrapped}\n"
        # 4G is a performance trap, not a safety net: measured 2026-11-07 on
        # provider grunt-pve, MemoryCurrent sat at 4.6G against a 4G cap with swap
        # full, prompt eval collapsed to 1-5 tok/s and clients timed out with zero
        # tokens (24/102 attempts in one 94-task run). Same process, cap raised:
        # 1776-token prompt prefilled at 935.9 tok/s and decoded at 43.8 tok/s.
        "MemoryHigh=8192M\n"
    )


def unit_props(lane: Lane, unit: str) -> dict:
    """systemd's own view of the unit - the only channel that survives a process that dies
    before it can answer HTTP."""
    try:
        r = lane.run(["systemctl", "show", unit, "--no-pager", "-p", UNIT_STATE_PROPS], timeout=40)
    except Exception:
        return {}
    out: dict = {}
    for line in (r.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def classify_serve_failure(text: str, unit_state: dict | None = None) -> tuple[str, str]:
    """Turn the engine's own output into a named cause.

    A lost config has to be a *labelled* lost config: `unsupported_arch` is a permanent
    exclusion, `vram_oom` is a config that does not fit, and `no_answer` is a driver defect
    that must never be blamed on the model.
    """
    t = text or ""
    m = re.search(r"unknown model architecture: '([^']+)'", t)
    if m:
        return "unsupported_arch", (
            f"deployed llama.cpp does not know GGUF architecture '{m.group(1)}'; not "
            "retryable at any context (needs a newer engine build, or a manifest exclusion)"
        )
    if "cudaMalloc failed" in t or "failed to allocate CUDA" in t or "out of memory" in t:
        m = re.search(r"allocating ([\d.]+) MiB", t)
        req = f" ({m.group(1)} MiB single request)" if m else ""
        return "vram_oom", f"CUDA allocation failed{req}; weights+KV do not fit in the free card"
    if "address already in use" in t:
        return "port_busy", "port already bound - another server owns it"
    if "error while handling argument" in t or "invalid argument" in t or "unknown argument" in t:
        return "bad_flags", "engine rejected a command-line flag in this config"
    if "failed to load model" in t:
        return "load_error", "engine failed to load the GGUF (first error line is in the log)"
    st = (unit_state or {}).get("ActiveState", "")
    if st == "failed":
        return "unit_failed", (
            f"unit is failed (exit {unit_state.get('ExecMainStatus', '?')}) and never answered "
            "HTTP; the log holds its own error"
        )
    return "no_answer", (
        f"unit is {st or 'unknown'}/{(unit_state or {}).get('SubState', '?')} but never answered "
        "HTTP - driver/probe defect, not a model verdict"
    )


def probe_completion(host: str, port: int, alias: str, timeout: int = 120) -> tuple[bool, dict]:
    """One real completion as proof the engine answers.

    Sends llama.cpp's per-request thinking lever (as `restore()` always did) and also accepts
    a non-empty `reasoning_content`: at max_tokens=8 a thinking model spends the budget in the
    reasoning channel, returns `content: ''` with finish_reason 'length', and *is* a live
    engine. Rejecting exactly that is what made ornith-9b and qwen35-9b look dead on
    2026-11-07 while their servers were healthy and named correctly.
    """
    msg = [{"role": "user", "content": "Reply with the single word: READY"}]
    payloads = [
        {"model": alias, "messages": msg, "max_tokens": 8, "temperature": 0,
         "chat_template_kwargs": {"enable_thinking": False}},
        {"model": alias, "messages": msg, "max_tokens": 8, "temperature": 0},
    ]
    for i, payload in enumerate(payloads):
        try:
            req = urllib.request.Request(
                f"http://{host}:{port}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                out = json.loads(fh.read().decode())
            choice = (out.get("choices") or [{}])[0]
            m = choice.get("message") or {}
            content = (m.get("content") or "").strip()
            reasoning = (m.get("reasoning_content") or m.get("reasoning") or "").strip()
            if content or reasoning:
                return True, {
                    "payload": "think_off" if i == 0 else "plain",
                    "answered_in": "content" if content else "reasoning_content",
                    "content": content[:40], "reasoning": reasoning[:40],
                    "finish_reason": choice.get("finish_reason"),
                }
        except Exception:
            continue
    return False, {}


def journal_scrape(lane: Lane, unit: str, since: int, limit: int | None = None) -> str:
    argv = ["journalctl", "-u", unit, "--no-pager", "-o", "cat", "--since", f"@{since}"]
    try:
        r = lane.run(argv, timeout=90)
    except Exception:
        return ""
    lines = (r.stdout or "").splitlines()
    if limit:
        lines = lines[-limit:]
    return "\n".join(lines)


def attempt_section(text: str) -> str:
    """Only the current attempt's lines: everything after the last restart boundary marker.
    A journal window can carry the previous config's crash-loop output (measured: a stale
    "unknown model architecture: 'dory'" line inside a minicpm5 log mislabelled a VRAM
    problem as an unsupported architecture)."""
    return (text or "").rsplit("# --- restarted", 1)[-1]


def error_tail(text: str, n: int = 12) -> str:
    """The lines a human needs from a 400-line engine log: errors first."""
    hits = [ln for ln in (text or "").splitlines() if re.search(r"\bE\b|error|failed|abort", ln, re.I)]
    return "\n".join((hits or (text or "").splitlines())[-n:])


def serve(entry: dict, lane: Lane, log=print, logs_dir: Path | None = None,
          unit: str = UNIT, vram_gate: bool = True) -> dict:
    """Bring the config's unit up and prove it answers. Always returns a diagnostics dict.

    Every attempt - success or failure - leaves results/_sweep_logs/<alias>-kv<ctk>.serve.log
    holding the engine's own stdout/stderr, captured by following the unit's journal from
    *before* the restart (its first error line lands ~150 ms after start, so scraping after a
    600 s wait can miss it entirely). A failure also comes back with a named cause.
    """
    logs_dir = logs_dir or (ROOT / "results" / "_sweep_logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{entry['alias']}-kv{entry.get('ctk', 'f16')}")
    log_path = logs_dir / f"{slug}.serve.log"
    diag: dict = {
        "ok": False, "alias": entry["alias"], "unit": unit,
        "log": str(log_path.relative_to(ROOT)) if log_path.is_relative_to(ROOT) else str(log_path),
    }
    port = entry.get("port", DEFAULT_PORT)
    host = entry.get("host") or ""
    dropin_dir, dropin = dropin_paths(unit)

    lane.run(["mkdir", "-p", dropin_dir])
    lane.write_remote(dropin, dropin_text(entry))
    r = lane.run(["systemctl", "daemon-reload"], timeout=60)
    if r.returncode:
        log(f"    daemon-reload failed: {r.stderr[-200:]}")
    lane.run(["systemctl", "reset-failed", unit], timeout=60)

    since = int(time.time()) - 2
    started = time.time()
    fh = log_path.open("w")
    fh.write(
        f"# sweep serve attempt {entry['alias']} ctx={entry.get('ctx')} "
        f"kv={entry.get('ctk')}/{entry.get('ctv')} unit={unit} port={port}\n"
        f"# ExecStart: {' '.join(shlex.quote(a) for a in serve_argv(entry))}\n"
        f"# following `journalctl -u {unit}` (the engine's stdout/stderr) since @{since}\n\n"
    )
    fh.flush()
    follower = None
    try:
        follower = subprocess.Popen(
            lane.ssh + lane.ct_cmd(["journalctl", "-u", unit, "-f", "-o", "cat",
                                    "--since", f"@{since}"]),
            stdout=fh, stderr=subprocess.STDOUT,
        )
    except Exception as exc:  # noqa: BLE001 - capture failure must never kill the sweep
        fh.write(f"# JOURNAL FOLLOW FAILED TO START: {exc}\n")
        fh.flush()

    try:
        # Stop, wait for the card, then start. A start that races the previous config's VRAM
        # release is indistinguishable from a config that does not fit, and that ambiguity is what
        # made `cudaMalloc failed` look like a model verdict twice on 2026-11-07.
        lane.run(["systemctl", "stop", unit], timeout=120)
        if vram_gate:
            diag["gpu_before_start"] = wait_card_idle(lane, log)
        r = lane.run(["systemctl", "start", unit], timeout=120)
        if r.returncode:
            diag.update(cause="restart_failed",
                        detail=(r.stderr or r.stdout or "").strip()[-300:])
            log(f"    restart failed: {diag['detail']}")
            return diag
        if not host:
            diag.update(cause="no_host", detail="no --host/GRUNT_HOST for this entry")
            log("    no host for this entry (pass --host or set GRUNT_HOST)")
            return diag

        # Everything the engine prints from here on belongs to THIS attempt. Without a
        # boundary, a line from the previous config's crash loop inside the same journal
        # window mislabels the cause (measured: a stale "unknown model architecture: 'dory'"
        # line landed in a minicpm5 log and reported unsupported_arch for a VRAM problem).
        fh.write(f"\n# --- restarted {time.strftime('%H:%M:%S')} - this attempt's output follows ---\n")
        fh.flush()
        base = unit_props(lane, unit)
        try:
            base_restarts = int(base.get("NRestarts") or 0)
        except ValueError:
            base_restarts = 0
        state: dict = base
        answered: dict = {}
        fastfail = ""
        deadline = started + HEALTH_TIMEOUT_S
        last_state_check = 0.0
        while time.time() < deadline:
            time.sleep(3)
            try:
                props = lane.http_json(f"http://{host}:{port}/props", timeout=5)
                models = lane.http_json(f"http://{host}:{port}/v1/models", timeout=5)
            except Exception:
                props, models = {}, {}
            got_path = str((props or {}).get("model_path") or "")
            got_alias = ""
            try:
                got_alias = str(((models or {}).get("data") or [{}])[0].get("id", ""))
            except Exception:
                pass
            if got_path == entry["path"] and got_alias == entry["alias"]:
                # A served alias is not an engine. Require one real completion.
                ok, meta = probe_completion(host, port, entry["alias"])
                if ok:
                    answered = meta
                    break
            if time.time() - last_state_check >= UNIT_PROBE_INTERVAL_S:
                last_state_check = time.time()
                state = unit_props(lane, unit)
                try:
                    n_restarts = int(state.get("NRestarts") or 0)
                except ValueError:
                    n_restarts = base_restarts
                if state.get("ActiveState") == "failed":
                    fastfail = "unit entered failed state"
                    break
                if (n_restarts - base_restarts >= FASTFAIL_RESTARTS
                        and state.get("ExecMainStatus") not in ("0", "", None)
                        and time.time() - started >= FASTFAIL_MIN_S):
                    fastfail = (
                        f"{n_restarts - base_restarts} failed restarts, last exit "
                        f"{state.get('ExecMainStatus')}")
                    break
    finally:
        if follower is not None:
            follower.terminate()
            try:
                follower.wait(timeout=15)
            except subprocess.TimeoutExpired:
                follower.kill()
        fh.flush()
        body = fh.tell()
        fh.close()

    diag["seconds"] = round(time.time() - started, 1)
    diag["unit_state"] = state
    text = log_path.read_text(errors="replace")
    if body < 400:  # follower caught nothing usable - scrape the journal definitively
        extra = journal_scrape(lane, unit, since)
        if extra.strip():
            with log_path.open("a") as afh:
                afh.write("\n# journal re-scrape (live follower produced no output)\n")
                afh.write(extra + "\n")
            text = log_path.read_text(errors="replace")
    diag["log_lines"] = len(text.splitlines())
    if answered:
        diag.update(ok=True, probe=answered)
        log(f"    served {entry['alias']}: probe answered via {answered.get('answered_in')} "
            f"({answered.get('payload')}), {diag['seconds']}s")
        return diag
    # A crash-looping config retries every 5 s for up to 60 attempts, and each attempt re-runs
    # the loader (a VRAM-OOM config grabs and drops a CUDA context every time). Stop it: the
    # verdict is already made, and a stopped unit also releases VRAM before the next config.
    lane.run(["systemctl", "stop", unit], timeout=60)
    # Only this attempt's lines may name the cause.
    attempt_text = attempt_section(text)
    cause, detail = classify_serve_failure(attempt_text, state)
    diag.update(cause=cause, detail=detail, tail=error_tail(attempt_text),
                exec_status=state.get("ExecMainStatus"), active_state=state.get("ActiveState"),
                restarts=state.get("NRestarts"), fastfail=fastfail)
    log(f"    server never came up as {entry['alias']} ({entry['path']})")
    log(f"    cause={cause}: {detail}")
    if fastfail:
        log(f"    fast-fail: {fastfail} after {diag['seconds']}s (was a fixed {HEALTH_TIMEOUT_S}s)")
    log(f"    engine log: {diag['log']}")
    return diag


def restore(lane: Lane, host: str, port: int = DEFAULT_PORT, log=print, unit: str = UNIT) -> bool:
    _, dropin = dropin_paths(unit)
    lane.run(["rm", "-f", dropin], timeout=60)
    lane.run(["systemctl", "daemon-reload"], timeout=60)
    lane.run(["systemctl", "reset-failed", unit], timeout=60)
    lane.run(["systemctl", "restart", unit], timeout=120)
    deadline = time.time() + HEALTH_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(3)
        try:
            lane.http_json(f"http://{host}:{port}/health", timeout=5)
        except Exception:
            continue
        ok, meta = probe_completion(host, port, "", timeout=60)
        if ok:
            said = (meta.get("content") or meta.get("reasoning") or "")[:40]
            log(f"  restored shipped unit, completion answered: {said!r}")
            return True
    log("  restored shipped unit but no real completion answered")
    return False


def gpu_pins(lane: Lane, log=print) -> dict:
    """Apply and verify the sustained-load pins on the PVE host, then report what the
    card actually says. Every sweep result is attributable only if this ran: without it
    the same config scores differently depending on how warm the minute was."""
    host = lane.host_run
    out: dict = {"requested_power_limit_w": GPU_POWER_LIMIT_W, "ok": False}
    r = host(["sudo", "-n", "nvidia-smi", "-pm", "1"])
    out["set_persistence_rc"] = r.returncode
    r = host(["sudo", "-n", "nvidia-smi", "-pl", str(GPU_POWER_LIMIT_W)])
    out["set_power_limit_rc"] = r.returncode
    out["set_power_limit_out"] = (r.stdout + r.stderr).strip()[-200:]
    r = host(["nvidia-smi", f"--query-gpu={GPU_PIN_QUERY}", "--format=csv,noheader"])
    out["readback"] = r.stdout.strip()
    if r.returncode != 0:
        out["error"] = (r.stderr or r.stdout).strip()[-200:]
        log(f"[sweep] GPU pins FAILED to read back: {out['error']}")
        return out
    fields = [p.strip() for p in r.stdout.strip().split(",")]
    try:
        out["persistence_mode"] = fields[0]
        out["power_limit_w"] = float(fields[1].split()[0])
        out["clocks_sm_mhz"] = int(fields[3].split()[0])
    except (IndexError, ValueError):
        out["error"] = f"unparsable readback {r.stdout.strip()!r}"
        log(f"[sweep] GPU pins {out['error']}")
        return out
    out["ok"] = (
        out["persistence_mode"].lower().startswith("enabled")
        and abs(out["power_limit_w"] - GPU_POWER_LIMIT_W) < 0.5
    )
    log(
        f"[sweep] GPU pins: persistence={out['persistence_mode']} "
        f"power_limit={out['power_limit_w']}W (requested {GPU_POWER_LIMIT_W}W) "
        f"sm={out['clocks_sm_mhz']}MHz -> {'OK' if out['ok'] else 'NOT APPLIED'}"
    )
    return out


def gpu_memory(lane: Lane) -> dict:
    """Host-side GPU memory right before an attempt.

    Inside CT100 `nvidia-smi --query-compute-apps` only sees that container's processes, which
    is how a config was once declared a VRAM wall while another server held 6 GiB of the card.
    The PVE host is the only authority on this number, and it is what makes an OOM verdict
    attributable to the config instead of to whatever else was resident.
    """
    try:
        r = lane.host_run(["nvidia-smi", "--query-gpu=memory.used,memory.free",
                           "--format=csv,noheader"])
    except Exception:
        return {}
    if r.returncode != 0:
        return {}
    out: dict = {}
    try:
        used, free = [p.strip() for p in r.stdout.strip().split(",", 1)]
        out["gpu_used_mib"] = int(used.split()[0])
        out["gpu_free_mib"] = int(free.split()[0])
    except (IndexError, ValueError):
        return {}
    return out


def wait_card_idle(lane: Lane, log=print, timeout_s: int = VRAM_GATE_TIMEOUT_S) -> dict:
    """Wait (bounded) for the card to actually be free after the previous config's server stops.

    Measured need 2026-11-07: two configs whose engine-accounted requirement fits an idle 8106 MiB
    card (`minicpm5-2b-q8_0` 3703 MiB, `gemma4-12b-ud-q2_K_XL` 5576 MiB) failed their first CUDA
    allocation 0.15-0.9 s after start with `cudaMalloc failed: out of memory`, while the same
    commands load fine minutes later. The variable left is the previous process's VRAM not being
    released yet, so the driver measures the card instead of assuming the stop freed it instantly.
    """
    deadline = time.time() + max(0, timeout_s)
    mem = gpu_memory(lane)
    while mem and time.time() < deadline and mem.get("gpu_free_mib", 0) < VRAM_GATE_MIN_MIB:
        time.sleep(2)
        mem = gpu_memory(lane)
    if mem:
        log(f"    card before start: {mem.get('gpu_used_mib')} MiB used, "
            f"{mem.get('gpu_free_mib')} MiB free")
    return mem


def read_manifest(path: Path) -> tuple[list[dict], dict[str, str]]:
    """Configs and explicit exclusions.

    A line starting with `!` is an exclusion, not a config: `!<alias><TAB><reason>`. The
    config row stays visible in the manifest, is skipped with its printed reason, and is
    never retried - the honest home for a GGUF the deployed engine cannot load at any ctx.
    """
    entries = []
    exclusions: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            f = line[1:].split("\t")
            alias = f[0].strip()
            if not alias:
                raise SystemExit(f"bad exclusion line (no alias): {raw!r}")
            exclusions[alias] = "\t".join(f[1:]).strip() or "no reason given"
            continue
        f = line.split("\t")
        if len(f) < 6:
            raise SystemExit(f"bad manifest line (need 6+ tab fields): {raw!r}")
        entries.append({
            "alias": f[0], "path": f[1], "ctx": int(f[2]), "np": int(f[3]),
            "ctk": f[4], "ctv": f[5], "extra": f[6] if len(f) > 6 else "",
        })
    return entries, exclusions


def load_state(path: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        done[f"{o.get('alias')}|{o.get('ctk')}|{o.get('path')}"] = o
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "scripts" / "sweep_manifest_v050.tsv"))
    ap.add_argument("--state", default=str(ROOT / "results" / "_sweep_state.jsonl"))
    ap.add_argument("--ssh", default=os.environ.get("GRUNT_SSH", "pve"))
    ap.add_argument("--ct", default="100")
    # No address literal in a public repo: the test box's tailnet/LAN address is the
    # operator's, so it arrives as --host or $GRUNT_HOST or the run refuses.
    ap.add_argument("--host", default=os.environ.get("GRUNT_HOST", ""))
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--unit", default=UNIT,
                    help="systemd unit instance to swap (default llama-worker@8891); a second "
                         "instance such as llama-worker@8893 lets a probe run beside the sweep")
    ap.add_argument("--concurrency", type=int, default=1,
                    help="match the server slots: a queued second stream only adds latency")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--thermal-limit", type=int, default=89)
    ap.add_argument("--limit", type=int, default=0, help="stop after N configs (smoke)")
    ap.add_argument("--only", default="", help="substring filter on alias")
    ap.add_argument("--restore", action="store_true", help="only restore the shipped unit and exit")
    ap.add_argument("--restore-on-exit", action="store_true")
    ap.add_argument("--no-gpu-pins", action="store_true",
                    help="skip the sustained-load pins (unattributable results; debugging only)")
    ap.add_argument("--no-vram-gate", action="store_true",
                    help="do not wait for the card to look idle before starting a config "
                         "(use when something else legitimately owns the GPU, e.g. an isolated probe)")
    args = ap.parse_args()

    lane = Lane(args.ssh, args.ct)
    if args.restore:
        return 0 if restore(lane, args.host, args.port, unit=args.unit) else 1

    # Pins first, before any config is served: a run on an unpinned card is not comparable
    # with a run on a pinned one, so refuse rather than mix them in one state file.
    pins: dict = {"ok": None, "skipped": True}
    if not args.no_gpu_pins:
        pins = gpu_pins(lane)
        if not pins.get("ok"):
            print(f"[sweep] GPU pins not applied ({pins.get('error') or pins}); "
                  f"refusing to score configs on a throttling card", flush=True)
            return 3

    entries, exclusions = read_manifest(Path(args.manifest))
    if args.only:
        entries = [e for e in entries if args.only in e["alias"]]
    state_path = Path(args.state)
    done = load_state(state_path)
    started = time.time()
    ran = 0
    failures: list[str] = []
    causes: dict[str, int] = {}

    print(f"[sweep] {len(entries)} configs, {len(exclusions)} manifest exclusion(s), "
          f"state {state_path}", flush=True)
    for i, e in enumerate(entries, 1):
        if e["alias"] in exclusions:
            print(f"[sweep] {i}/{len(entries)} skip (excluded) {e['alias']}: "
                  f"{exclusions[e['alias']]}", flush=True)
            continue
        key = f"{e['alias']}|{e['ctk']}|{e['path']}"
        prev = done.get(key)
        if prev and prev.get("status") == "done" and prev.get("result") and Path(prev["result"]).exists():
            print(f"[sweep] {i}/{len(entries)} skip (done) {e['alias']} {e['ctk']}", flush=True)
            continue
        if args.limit and ran >= args.limit:
            break
        print(f"[sweep] {i}/{len(entries)} serve {e['alias']} ctx={e['ctx']} kv={e['ctk']}/{e['ctv']}", flush=True)
        t0 = time.time()
        mem = gpu_memory(lane)
        if mem:
            print(f"    host GPU before attempt: {mem['gpu_used_mib']} MiB used, "
                  f"{mem['gpu_free_mib']} MiB free", flush=True)
        rec = dict(e, started=time.strftime("%Y-%m-%dT%H:%M:%S"), status="serving",
                   gpu_power_limit_w=pins.get("power_limit_w"),
                   gpu_persistence=pins.get("persistence_mode"),
                   gpu_pins_ok=pins.get("ok"), **mem)
        # A failed config is only useful if it is a labelled failure: the attempt streams the
        # engine's own output to results/_sweep_logs/<alias>-kv<ctk>.serve.log and comes back
        # with a named cause, so the 0.5.0 table can say *why* a row is missing.
        diag = serve(dict(e, host=args.host, port=args.port), lane,
                     logs_dir=ROOT / "results" / "_sweep_logs", unit=args.unit,
                     vram_gate=not args.no_vram_gate)
        if diag.get("gpu_before_start"):
            rec.update(gpu_start_used_mib=diag["gpu_before_start"].get("gpu_used_mib"),
                       gpu_start_free_mib=diag["gpu_before_start"].get("gpu_free_mib"))
        if not diag.get("ok"):
            cause = diag.get("cause") or "unknown"
            detail = diag.get("detail") or ""
            if cause == "vram_oom" and mem.get("gpu_free_mib") is not None:
                detail = f"{detail}; host free VRAM at attempt: {mem['gpu_free_mib']} MiB"
            causes[cause] = causes.get(cause, 0) + 1
            rec.update(status="serve_failed", seconds=diag.get("seconds") or round(time.time() - t0, 1),
                       serve_cause=cause, serve_detail=detail,
                       serve_log=diag.get("log"), serve_tail=diag.get("tail"),
                       serve_exec_status=diag.get("exec_status"),
                       serve_active_state=diag.get("active_state"),
                       serve_restarts=diag.get("restarts"),
                       serve_fastfail=diag.get("fastfail"))
            failures.append(e["alias"])
            with state_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"    -> serve_failed cause={cause} ({rec['seconds']}s) log={rec['serve_log']}",
                  flush=True)
            continue
        ran += 1
        cmd = [
            str(ROOT / ".venv" / "bin" / "python"), "-m", "gauntlet.cli", "run",
            "--endpoint", f"http://{args.host}:{args.port}/v1",
            "--model", e["alias"], "--suite", "all",
            "--concurrency", str(args.concurrency), "--timeout", str(args.timeout),
            "--seed", str(args.seed), "--thermal-limit", str(args.thermal_limit),
        ]
        print("    " + " ".join(cmd[1:]), flush=True)
        # Stream to a per-config log instead of buffering: a 20-minute run with no visible
        # output is indistinguishable from a hung one, and the log outlives this process.
        logs_dir = ROOT / "results" / "_sweep_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_name = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{e['alias']}-kv{e['ctk']}") + ".log"
        log_path = logs_dir / log_name
        with log_path.open("w") as fh:
            fh.write(" ".join(cmd) + "\n\n")
            fh.flush()
            p = subprocess.run(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
        out = log_path.read_text(errors="replace")
        result = None
        for line in out.splitlines():
            if "results ->" in line:
                result = line.split("results ->", 1)[1].strip()
        score = None
        for line in reversed(out.splitlines()):
            if '"overall_pct"' in line or '"capability_score"' in line:
                try:
                    score = float(line.split(":")[1].strip().rstrip(","))
                except Exception:
                    pass
                break
        rec.update(
            status="done" if p.returncode == 0 and result else "run_failed",
            returncode=p.returncode,
            result=result,
            score=score,
            seconds=round(time.time() - t0, 1),
            log=str(log_path.relative_to(ROOT)),
            tail="\n".join(out.splitlines()[-6:]) if p.returncode else "",
        )
        if rec["status"] != "done":
            failures.append(e["alias"])
        with state_path.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"    -> {rec['status']} score={score} result={result} ({rec['seconds']}s)", flush=True)

    print(f"[sweep] finished {ran} run(s) in {round((time.time()-started)/60,1)} min; failures={failures}", flush=True)
    if causes:
        print(f"[sweep] serve failure causes: {causes}", flush=True)
    if args.restore_on_exit:
        restore(lane, args.host, args.port, unit=args.unit)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
