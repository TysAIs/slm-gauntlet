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
DROPIN_DIR = f"/etc/systemd/system/{UNIT}.service.d"
DROPIN = f"{DROPIN_DIR}/50-sweep.conf"
DEFAULT_PORT = 8891
HEALTH_TIMEOUT_S = 600


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

    def ct_cmd(self, argv: list[str]) -> list[str]:
        return self.base + argv

    def write_remote(self, path: str, content: str) -> None:
        r = self.run(["tee", path], stdin=content)
        if r.returncode != 0:
            raise RuntimeError(f"tee {path} failed: {r.stderr[-300:]}")

    def http_json(self, url: str, timeout: int = 10):
        with urllib.request.urlopen(url, timeout=timeout) as fh:
            return json.loads(fh.read().decode())


def dropin_text(entry: dict) -> str:
    """A drop-in that replaces ExecStart outright (empty value first, then the real one)."""
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
    wrapped = " \\\n  ".join(shlex.quote(a) for a in argv)
    return (
        "[Service]\n"
        "ExecStart=\n"
        f"ExecStart={wrapped}\n"
        "MemoryHigh=4096M\n"
    )


def serve(entry: dict, lane: Lane, log=print) -> bool:
    lane.run(["mkdir", "-p", DROPIN_DIR])
    lane.write_remote(DROPIN, dropin_text(entry))
    r = lane.run(["systemctl", "daemon-reload"], timeout=60)
    if r.returncode:
        log(f"    daemon-reload failed: {r.stderr[-200:]}")
    lane.run(["systemctl", "reset-failed", UNIT], timeout=60)
    r = lane.run(["systemctl", "restart", UNIT], timeout=120)
    if r.returncode:
        log(f"    restart failed: {r.stderr[-200:]}")
        return False
    port = entry.get("port", DEFAULT_PORT)
    host = entry.get("host") or ""
    if not host:
        log("    no host for this entry (pass --host or set GRUNT_HOST)")
        return False
    deadline = time.time() + HEALTH_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(3)
        try:
            props = lane.http_json(f"http://{host}:{port}/props", timeout=5)
            models = lane.http_json(f"http://{host}:{port}/v1/models", timeout=5)
        except Exception:
            continue
        got_path = str((props or {}).get("model_path") or "")
        got_alias = ""
        try:
            got_alias = (models.get("data") or [{}])[0].get("id", "")
        except Exception:
            pass
        if got_path == entry["path"] and got_alias == entry["alias"]:
            # A served alias is not an engine. Require one real, non-empty completion:
            # llama.cpp answers /props and /v1/models long before (and sometimes when)
            # it cannot finish a request.
            try:
                body = json.dumps({
                    "model": entry["alias"],
                    "messages": [{"role": "user", "content": "Reply with the single word: READY"}],
                    "max_tokens": 8, "temperature": 0,
                }).encode()
                req = urllib.request.Request(
                    f"http://{host}:{port}/v1/chat/completions", data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as fh:
                    out = json.loads(fh.read().decode())
                txt = (out["choices"][0]["message"].get("content") or "").strip()
                if txt:
                    return True
            except Exception:
                pass
    log(f"    server never came up as {entry['alias']} ({entry['path']})")
    return False


def restore(lane: Lane, host: str, port: int = DEFAULT_PORT, log=print) -> bool:
    lane.run(["rm", "-f", DROPIN], timeout=60)
    lane.run(["systemctl", "daemon-reload"], timeout=60)
    lane.run(["systemctl", "reset-failed", UNIT], timeout=60)
    lane.run(["systemctl", "restart", UNIT], timeout=120)
    deadline = time.time() + HEALTH_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(3)
        try:
            lane.http_json(f"http://{host}:{port}/health", timeout=5)
            body = json.dumps({
                "model": "",
                "messages": [{"role": "user", "content": "Reply with the single word: READY"}],
                "max_tokens": 8,
                "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False},
            }).encode()
            req = urllib.request.Request(
                f"http://{host}:{port}/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as fh:
                out = json.loads(fh.read().decode())
            text = (out["choices"][0]["message"].get("content") or "").strip()
            if text:
                log(f"  restored shipped unit, completion answered: {text[:40]!r}")
                return True
        except Exception:
            continue
    log("  restored shipped unit but no real completion answered")
    return False


def read_manifest(path: Path) -> list[dict]:
    entries = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) < 6:
            raise SystemExit(f"bad manifest line (need 6+ tab fields): {raw!r}")
        entries.append({
            "alias": f[0], "path": f[1], "ctx": int(f[2]), "np": int(f[3]),
            "ctk": f[4], "ctv": f[5], "extra": f[6] if len(f) > 6 else "",
        })
    return entries


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
    ap.add_argument("--concurrency", type=int, default=1,
                    help="match the server slots: a queued second stream only adds latency")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--thermal-limit", type=int, default=89)
    ap.add_argument("--limit", type=int, default=0, help="stop after N configs (smoke)")
    ap.add_argument("--only", default="", help="substring filter on alias")
    ap.add_argument("--restore", action="store_true", help="only restore the shipped unit and exit")
    ap.add_argument("--restore-on-exit", action="store_true")
    args = ap.parse_args()

    lane = Lane(args.ssh, args.ct)
    if args.restore:
        return 0 if restore(lane, args.host, args.port) else 1

    entries = read_manifest(Path(args.manifest))
    if args.only:
        entries = [e for e in entries if args.only in e["alias"]]
    state_path = Path(args.state)
    done = load_state(state_path)
    started = time.time()
    ran = 0
    failures: list[str] = []

    print(f"[sweep] {len(entries)} configs, state {state_path}", flush=True)
    for i, e in enumerate(entries, 1):
        key = f"{e['alias']}|{e['ctk']}|{e['path']}"
        prev = done.get(key)
        if prev and prev.get("status") == "done" and prev.get("result") and Path(prev["result"]).exists():
            print(f"[sweep] {i}/{len(entries)} skip (done) {e['alias']} {e['ctk']}", flush=True)
            continue
        if args.limit and ran >= args.limit:
            break
        print(f"[sweep] {i}/{len(entries)} serve {e['alias']} ctx={e['ctx']} kv={e['ctk']}/{e['ctv']}", flush=True)
        t0 = time.time()
        rec = dict(e, started=time.strftime("%Y-%m-%dT%H:%M:%S"), status="serving")
        if not serve(dict(e, host=args.host), lane):
            rec.update(status="serve_failed", seconds=round(time.time() - t0, 1))
            failures.append(e["alias"])
            with state_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
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
    if args.restore_on_exit:
        restore(lane, args.host, args.port)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
