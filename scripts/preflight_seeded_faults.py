#!/usr/bin/env python3
"""preflight_seeded_faults.py - prove EVERY refusal leg of the lane gate against the real box.

WHY THIS EXISTS
`tests/test_preflight_lane.py` proves the rule set by replaying recorded samples. That is not the
same claim as "the gate refuses a real sick box": a fixture cannot show that `systemctl stop`
produces exit 2 through this ssh/`pct exec` path, or that a genuinely GPU-less engine reads as
exit 4. This script seeds one real fault per leg, runs the shipped gate, and quotes the exit code
and the leg name the gate printed. It restores the lane in `finally` and then requires the
unseeded state to return 0.

Each seed is a REAL condition, not a patched sample:
  unit      `systemctl stop` the worker unit (the state a crash-loop ends in)
  endpoint  the unit is up and healthy, the gate is pointed at a port nothing listens on
            (a stale --port, which is exactly how a sweep reaches the wrong server)
  gpu       a real `llama-server -ngl 0` serving the lane's own model: the card holds <100 MiB,
            which is the silent CPU-fallback signature (a speed number from here is a CPU number)
  load      `llama-bench` on the lane's model while the gate runs: a foreign process holding the
            card, which is somebody else's benchmark and not comparable
  thermal   a sustained decode burn until the card reaches >=80 C or SW thermal slowdown fires
  pin       `nvidia-smi -pl` raised above the 120 W ceiling, then restored

SAFETY
The lane is restored in `finally` (burn killed, pin back to the ceiling, unit started) and the
script refuses to run while a sweep is live, because stopping the unit under a running config
would turn this proof into a benchmark failure. Exit 0 only if every leg refused with the code
its rule assigns AND the restored lane passed the full gate.

USAGE
  GRUNT_HOST=<lane-address> python3 scripts/preflight_seeded_faults.py [--receipt DIR]
  ... --legs unit,load            # prove a subset
  ... --thermal-budget-s 600      # how long the thermal seed may take to heat the card

EXIT 0 all seeds behaved / 1 a seed disagreed with its rule / 9 the lane did not come back
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "preflight_lane.py"

# A sweep holding the lane means this script must not stop the unit under it.
SWEEP_MARKERS = ("pve_sweep.py", "night_queue")

# Exit code each seed must provoke, keyed by the leg it proves. Cross-checked against the gate's
# own LEG_EXIT by tests/test_preflight_seeded_faults.py, so a leg added or renumbered in one file
# cannot silently disagree with the other.
EXPECTED_EXIT = {"unit": 2, "endpoint": 3, "gpu": 4, "load": 5, "thermal": 6, "pin": 7}


def sh(argv, timeout=120, quiet=True):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


class Lane:
    """The box, reached the way the gate reaches it: one ssh alias + `pct exec` into the CT."""

    def __init__(self, ssh_alias: str, ct: str, unit: str, port: int, host: str,
                 ssh_user: str = "root"):
        self.ssh = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", ssh_alias]
        self.ct = ct
        self.unit = unit
        self.port = port
        self.host = host
        self.user = ssh_user

    # -- transport ----------------------------------------------------------------------
    # ssh joins its argv into ONE string and the remote login shell parses it again, so an
    # argument containing `sh -c '<pipeline>'` loses its quoting and is silently split. Quote
    # every command for that second parse: an unquoted `sh -c cd && ... &` became `sh -c cd`
    # plus a background job in the wrong directory, which read as "nohup: failed to run command
    # './llama-bench': No such file or directory" on a binary that was right there.
    def _ssh(self, argv, timeout=120):
        return sh(self.ssh + [shlex.join(argv)], timeout=timeout)

    def run(self, argv, timeout=120):
        return self._ssh(["pct", "exec", self.ct, "--"] + argv, timeout=timeout)

    def host_run(self, argv, timeout=120):
        return self._ssh(argv, timeout=timeout)

    # -- lane operations ----------------------------------------------------------------
    def unit_active(self) -> bool:
        r = self.run(["systemctl", "is-active", self.unit])
        return r.stdout.strip() == "active"

    def stop_unit(self):
        self.run(["systemctl", "stop", self.unit], timeout=120)

    def start_unit(self):
        self.run(["systemctl", "start", self.unit], timeout=120)

    def wait_endpoint(self, want_up=True, timeout=180) -> bool:
        """Poll /v1/models through the CT (no raw curl from the repo: this is a liveness wait,
        not a benchmark caller)."""
        deadline = time.time() + timeout
        url = f"http://127.0.0.1:{self.port}/v1/models"
        while time.time() < deadline:
            r = self.run(["curl", "-fsS", "--max-time", "5", url], timeout=30)
            up = r.returncode == 0 and '"id"' in (r.stdout or "")
            if up == want_up:
                return True
            time.sleep(3)
        return False

    def model_path(self) -> str:
        """The model a burn loads: deliberately a SMALL one, not the served model.

        The card is 8 GB and the serving engine already holds ~5.7 GB of it, so a burn that
        loaded the served 12B would fall back to partial offload and heat the card less than a
        real run does. Prefer the shipped worker model (proven loadable by the tested build),
        else the smallest non-mmproj GGUF on the box.
        """
        r = self.run(["sh", "-c", "find /mnt/data/models -name '*.gguf' -printf '%s\\t%p\\n' "
                                   "| grep -v -i mmproj | sort -n"], timeout=60)
        files = [ln.split("\t", 1) for ln in (r.stdout or "").splitlines() if "\t" in ln]
        if not files:
            raise RuntimeError("no usable GGUF on the box for the burn; pass --burn-model")
        for _, path in files:
            if "MiniCPM5-2B-Q4_K_M.gguf" in path:
                return path
        return files[0][1]

    def wait_gpu_released(self, timeout: int = 90) -> bool:
        """Wait until the card actually holds nothing.

        A just-stopped unit leaves its VRAM resident for a moment; gating before the driver frees
        it made the CPU-fallback seed read 5699 MiB and pass the gpu leg (measured, t_837f2ef).
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if (self.gpu()["mem_mib"] or 0) < 100:
                    return True
            except Exception:  # noqa: BLE001 - transient nvidia-smi hiccup while freeing
                pass
            time.sleep(3)
        return False

    def gpu(self) -> dict:
        q = ("temperature.gpu,clocks_throttle_reasons.active,power.draw,utilization.gpu,"
             "memory.used,power.limit")
        r = self.host_run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader"])
        row = [p.strip() for p in (r.stdout or "").strip().splitlines()[0].split(",")] if r.stdout.strip() else []
        if len(row) < 6:
            raise RuntimeError(f"unparsable nvidia-smi row: {r.stdout!r} {r.stderr[-200:]!r}")
        num = lambda s: float(re.match(r"-?\d+(?:\.\d+)?", s).group(0)) if re.match(r"-?\d", s) else None  # noqa: E731
        return {"temp_c": num(row[0]), "mask": row[1], "power_w": num(row[2]),
                "util_pct": num(row[3]), "mem_mib": num(row[4]), "limit_w": num(row[5])}

    def set_power_limit(self, watts: float):
        return self.host_run(["nvidia-smi", "-pl", f"{watts:g}"], timeout=60)

    def burn(self, model: str, parallel: int, tag: str):
        """Start llama-bench inside the CT, detached, so the gate samples a genuinely loaded card.

        Absolute binary path on purpose: a `cd ... && nohup ./llama-bench` inside `sh -c` lost
        its working directory through ssh's second parse and died with "No such file or
        directory" on a binary that was present (t_837f2ef).
        """
        self.kill_burn(tag)
        log = f"/tmp/preflight-burn-{tag}.log"
        cmd = (f"LD_LIBRARY_PATH=/opt/llama.cpp/build/bin setsid nohup "
               f"/opt/llama.cpp/build/bin/llama-bench -m {shlex.quote(model)} "
               f"-p 512 -n 512 -r 1000 -t 2 -ngl 99 > {log} 2>&1 < /dev/null &")
        for _ in range(parallel):
            self.run(["sh", "-c", cmd], timeout=60)
        for _ in range(45):
            if self.burn_alive():
                return log
            time.sleep(1)
        tail = self.run(["sh", "-c", f"tail -3 {log} 2>/dev/null || true"], timeout=30).stdout
        raise RuntimeError(f"burn ({tag}) never started; {log}: {tail.strip()[-300:]}")

    def kill_burn(self, tag: str = ""):
        self.run(["sh", "-c", "pkill -f '[l]lama-bench' || true"], timeout=60)

    def burn_alive(self) -> int:
        r = self.run(["sh", "-c", "pgrep -fc '[l]lama-bench' || true"], timeout=60)
        try:
            return int((r.stdout or "").strip() or 0)
        except ValueError:
            return 0

    def cpu_fallback_server(self, model: str, port: int):
        """A real GPU-less engine serving the lane's own model on another port."""
        self.kill_cpu_server()
        cmd = (f"LD_LIBRARY_PATH=/opt/llama.cpp/build/bin:/usr/lib/x86_64-linux-gnu/nvidia/current "
               f"setsid nohup /opt/llama.cpp/build/bin/llama-server -m {shlex.quote(model)} "
               f"--alias llama-server-cpu -ngl 0 -t 4 -c 512 --host 127.0.0.1 --port {port} "
               f"> /tmp/preflight-cpu.log 2>&1 < /dev/null &")
        self.run(["sh", "-c", cmd], timeout=60)
        deadline = time.time() + 240
        url = f"http://127.0.0.1:{port}/v1/models"
        while time.time() < deadline:
            r = self.run(["curl", "-fsS", "--max-time", "5", url], timeout=30)
            if r.returncode == 0 and '"id"' in (r.stdout or ""):
                return True
            time.sleep(3)
        return False

    def kill_cpu_server(self):
        self.run(["sh", "-c", "pkill -f '[l]lama-server-cpu' || true"], timeout=60)


class Prover:
    def __init__(self, args):
        self.args = args
        self.lane = Lane(args.ssh, args.ct, args.unit, args.port, args.host, ssh_user=args.ssh_user)
        self.rows: list[dict] = []
        self.failures: list[str] = []
        self.notes: list[str] = []

    # -- the gate, invoked exactly as the sweep invokes it -------------------------------
    def gate(self, legs: str, port: int | None = None, extra=()) -> tuple[int, dict | None, str]:
        cmd = [sys.executable, str(GATE), "--host", self.args.host, "--ssh", self.args.ssh,
               "--ct", self.args.ct, "--unit", self.args.unit,
               "--port", str(port or self.lane.port), "--legs", legs, "--json"]
        cmd += list(extra)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        try:
            obj = json.loads(r.stdout)
        except Exception:  # noqa: BLE001
            obj = None
        shown = " ".join(["preflight_lane.py"] + [c for c in cmd[2:]])
        detail = ""
        if obj:
            bad = [x for x in obj.get("legs", []) if not x.get("ok")]
            detail = (bad[0]["detail"] if bad else
                      "; ".join(f"{x['leg']}: {x['detail']}" for x in obj.get("legs", [])))
        return r.returncode, obj, f"{shown}\n  -> exit {r.returncode} | {detail}"

    def record(self, seed: str, legs: str, expect: int, got: int, detail: str, note: str):
        # The expectation for a real leg comes from EXPECTED_EXIT, which tests/test_preflight_
        # seeded_faults.py cross-checks against the gate's own LEG_EXIT: a renumbered leg in
        # either file fails loudly instead of proving the wrong refusal.
        if legs in EXPECTED_EXIT and expect != EXPECTED_EXIT[legs]:
            raise SystemExit(f"seed {seed}: expectation {expect} disagrees with EXPECTED_EXIT"
                             f"[{legs}]={EXPECTED_EXIT[legs]}")
        ok = got == expect
        self.rows.append({"seed": seed, "legs_proven": legs, "expected_exit": expect,
                          "actual_exit": got, "ok": ok, "note": note, "receipt": detail})
        print(f"[{'OK  ' if ok else 'BAD '}] seed {seed:<10} expected exit {expect} got {got} "
              f"({legs})", flush=True)
        print("        " + detail.replace("\n", "\n        "), flush=True)
        if not ok:
            self.failures.append(f"{seed}: expected exit {expect}, got {got}")

    # -- seeds -------------------------------------------------------------------------
    def seed_unit(self):
        self.lane.stop_unit()
        code, _, detail = self.gate("unit", port=self.args.dead_port)
        self.lane.start_unit()
        self.record("unit", "unit", 2, code, detail,
                    "`systemctl stop` of the worker unit - the state a crash-loop ends in")

    def seed_gpu_cpu_fallback(self):
        model = self.lane.model_path()
        self.lane.stop_unit()
        try:
            if not self.lane.wait_gpu_released():
                raise RuntimeError("the card never went back to <100 MiB after stopping the unit")
            up = self.lane.cpu_fallback_server(model, self.args.dead_port)
            gpu = self.lane.gpu()
            code, _, detail = self.gate("gpu", port=self.args.dead_port)
            self.record("gpu", "gpu", 4, code,
                        detail + (f"\n  card while the -ngl 0 engine served: {gpu['mem_mib']} MiB, "
                                  f"{gpu['util_pct']} % util"),
                        f"real `llama-server -ngl 0` on the lane's model (endpoint up={up}): "
                        f"the card is not doing the work")
        finally:
            self.lane.kill_cpu_server()
            self.lane.start_unit()
            self.lane.wait_endpoint(True)

    def seed_endpoint(self):
        code, _, detail = self.gate("unit,endpoint", port=self.args.dead_port)
        self.record("endpoint", "endpoint", 3, code, detail,
                    f"healthy unit, gate pointed at the dead port {self.args.dead_port} "
                    f"(a stale --port reaches the wrong server)")

    def seed_pin(self):
        self.lane.set_power_limit(self.args.seed_power_w)
        try:
            code, _, detail = self.gate("pin")
        finally:
            self.lane.set_power_limit(self.args.ceiling_w)
        self.record("pin", "pin", 7, code, detail,
                    f"`nvidia-smi -pl {self.args.seed_power_w:g}` above the "
                    f"{self.args.ceiling_w:g} W ceiling, restored after the gate")

    def seed_load(self):
        model = self.lane.model_path()
        self.lane.burn(model, parallel=1, tag="load")
        try:
            # A llama-bench that is still loading its model is not yet a load on the card; wait
            # for the foreign process to actually reach the GPU before judging the gate's answer.
            seen = False
            for _ in range(60):
                r = self.lane.host_run(["nvidia-smi", "--query-compute-apps=process_name",
                                        "--format=csv,noheader"], timeout=45)
                names = (r.stdout or "")
                if "llama-bench" in names:
                    g = self.lane.gpu()
                    if (g["util_pct"] or 0) > 0:
                        seen = True
                        break
                time.sleep(2)
            if not seen:
                raise RuntimeError("llama-bench never showed up on the card; cannot prove the "
                                   "load leg")
            code, _, detail = self.gate("load")
        finally:
            self.lane.kill_burn("load")
        self.record("load", "load", 5, code, detail,
                    "`llama-bench` on the lane's model holding the card while the gate ran "
                    "(somebody else's benchmark is not comparable)")

    def seed_thermal(self):
        model = self.lane.model_path()
        budget = self.args.thermal_budget_s
        # The serving engine holds ~5.7 GiB of this 8 GiB card, so N burn streams cannot fit
        # beside it (one llama-bench of the shipped 2B already takes 1.8 GiB). Stop the unit for
        # the burn: the thermal leg reads only the card, and a half-offloaded burn would heat it
        # less than a real run does. The unit is started again in `finally`.
        self.lane.stop_unit()
        self.lane.set_power_limit(self.args.seed_power_w)  # heat faster; the pin leg is not gated here
        self.lane.burn(model, parallel=self.args.burn_streams, tag="thermal")
        reached, gpu, trail = False, {}, []
        deadline = time.time() + budget
        try:
            while time.time() < deadline:
                time.sleep(15)
                gpu = self.lane.gpu()
                trail.append(f"{int(gpu['temp_c'] or 0)}C/{gpu['mask']}/{gpu['power_w']}W")
                print(f"        burn {len(trail) * 15:>4}s  {trail[-1]}", flush=True)
                if self.lane.burn_alive() < 1:
                    tail = self.lane.run(
                        ["sh", "-c", "tail -3 /tmp/preflight-burn-thermal.log"],
                        timeout=30).stdout
                    raise RuntimeError(f"the burn died mid-seed: {tail.strip()[-300:]}")
                if (gpu["temp_c"] or 0) >= 80 or int(gpu["mask"], 16) & 0x020:
                    reached = True
                    break
            if not reached:
                # The gate also refuses when SW thermal slowdown is already active; if the card
                # plateaued under 80 C we cannot claim the thermal seed, so say so.
                self.failures.append(
                    f"thermal: card plateaued at {gpu.get('temp_c')} C in {budget}s "
                    f"(need >=80 C or SW_THERMAL_SLOWDOWN); trail {' '.join(trail[-6:])}")
            code, _, detail = self.gate("thermal")
            self.record("thermal", "thermal", 6, code,
                        detail + f"\n  burn trail: {' '.join(trail[-6:])}",
                        f"{self.args.burn_streams} decode streams until the card reached the "
                        f"refuse line (this is the state a run begun straight after a loaded "
                        f"config lands in)")
            if reached:
                # The gate refuses the SLOWDOWN bits (0x8/0x20/0x40/0x80). At the 80 C refuse line
                # the mask is usually still clean (measured: 0x4 SW_POWER_CAP, an allowed bit at
                # 73-77 C, then 0x0 at 80 C), so keep the burn running until the card sets one -
                # that bit is precisely the state that silently scores a slow run - and prove the
                # gpu leg refuses it. Bounded: if the card plateaus clean, the bit path stays
                # proven by the recorded real 82 C / 0x20 row in tests/fixtures.
                deadline2 = time.time() + self.args.bit_budget_s
                hits = 0
                while time.time() < deadline2:
                    time.sleep(10)
                    gpu = self.lane.gpu()
                    print(f"        bit-wait {int(gpu['temp_c'] or 0)}C/{gpu['mask']}/"
                          f"{gpu['power_w']}W", flush=True)
                    # The bit flickers (0x20 then 0x0 four seconds later at 82 C), so wait for it
                    # to be set on two consecutive samples or for the card to be hot enough that
                    # it stays set; otherwise the gate's own samples can land in a clean gap.
                    hit = bool(int(gpu["mask"], 16) & 0x028)
                    hits = hits + 1 if hit else 0
                    if hits >= 2 or (hit and (gpu["temp_c"] or 0) >= 84):
                        break
                if int(gpu["mask"], 16) & 0x028:
                    bit_code, _, bit_detail = self.gate("gpu")
                    self.record("gpu_throttle_bits", "gpu", EXPECTED_EXIT["gpu"], bit_code,
                                bit_detail + f"\n  card during the gate: {gpu['temp_c']} C, "
                                             f"mask {gpu['mask']}, {gpu['power_w']} W",
                                "hard throttle bit set by real heat: the gpu leg refuses the "
                                "run that would otherwise score the throttle as the config")
                else:
                    self.notes.append(
                        f"gpu_throttle_bits not re-seeded live: the card stayed at "
                        f"{gpu['temp_c']} C / mask {gpu['mask']} for {self.args.bit_budget_s}s "
                        f"(no slowdown bit). The bit path is proven by the recorded 82 C / 0x20 "
                        f"row in tests/fixtures/lane_throttled_sw_thermal.json.")
        finally:
            self.lane.kill_burn("thermal")
            self.lane.set_power_limit(self.args.ceiling_w)
            self.lane.start_unit()
            self.lane.wait_endpoint(True)

    def prove_lane_restored(self):
        ok = self.lane.wait_endpoint(True)
        code, _, detail = self.gate(",".join(("unit", "endpoint", "gpu", "load", "thermal", "pin")))
        self.record("real_state", "all", 0, code,
                    detail + f"\n  worker answered /v1/models again: {ok}",
                    "unseeded lane after restore: everything the gate asks for is true")
        return code == 0 and ok

    def run(self):
        want = {s.strip() for s in self.args.legs.split(",") if s.strip()}
        base = self.lane.gpu()
        print(f"[seeded] baseline: {base['temp_c']} C, {base['limit_w']} W limit, "
              f"{base['mem_mib']} MiB resident, mask {base['mask']}", flush=True)
        if base["limit_w"] and base["limit_w"] > self.args.ceiling_w + 0.5:
            print(f"[seeded] WARNING: pin is {base['limit_w']} W before any seed; the real-state "
                  f"check will refuse until it is back at {self.args.ceiling_w:g} W", flush=True)

        def attempt(seed, fn):
            """A seed that cannot be staged is a FAILED proof, never a silent skip."""
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 - a broken proof must be reported as one
                self.failures.append(f"{seed}: could not stage the seed: {exc}")
                print(f"[BAD ] seed {seed:<10} could not be staged: {exc}", flush=True)

        try:
            if "unit" in want:
                attempt("unit", self.seed_unit)
                self.lane.wait_endpoint(True)
            if "gpu" in want:
                attempt("gpu", self.seed_gpu_cpu_fallback)
            if "endpoint" in want:
                attempt("endpoint", self.seed_endpoint)
            if "pin" in want:
                attempt("pin", self.seed_pin)
            if "load" in want:
                attempt("load", self.seed_load)
            if "thermal" in want:
                attempt("thermal", self.seed_thermal)
        finally:
            self.lane.kill_burn()
            self.lane.kill_cpu_server()
            self.lane.set_power_limit(self.args.ceiling_w)
            self.lane.start_unit()
        restored = self.prove_lane_restored()
        return self.report() and restored

    def report(self):
        stamp = time.strftime("%Y%m%dT%H%M%S")
        out_dir = pathlib.Path(os.path.expanduser(self.args.receipt))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"preflight_seeded_faults_{stamp}.md"
        lines = [
            f"# Seeded-fault proof of the lane gate ({stamp})",
            "",
            "Every row is a REAL fault seeded on the lane; the command is the shipped gate and",
            "the exit code is what it returned. Reproduce with",
            "`GRUNT_HOST=<lane> python3 scripts/preflight_seeded_faults.py`.",
            "",
            f"Lane thresholds in force: refuse temperature 80 C (card target 83 C), power ceiling "
            f"{self.args.ceiling_w:g} W, throttle-mask rule as documented in "
            f"`scripts/preflight_lane.py`.",
            "",
            "| seed | legs | expected | actual | verdict |",
            "|---|---|---|---|---|",
        ]
        for row in self.rows:
            lines.append(f"| {row['seed']} | {row['legs_proven']} | {row['expected_exit']} | "
                         f"{row['actual_exit']} | {'PASS' if row['ok'] else 'FAIL'} |")
        lines.append("")
        for row in self.rows:
            lines += [f"## {row['seed']} - {row['note']}", "", "```", row["receipt"], "```", ""]
        if self.failures:
            lines += ["## Failures", ""] + [f"- {f}" for f in self.failures] + [""]
        if self.notes:
            lines += ["## Not re-seeded live (and what proves it instead)", ""] + \
                     [f"- {n}" for n in self.notes] + [""]
        path.write_text("\n".join(lines))
        # Sanitize before it can be committed: the repo's hygiene gate bans address literals, and
        # both the gate's command line and the probe's output carry the lane address.
        blob = path.read_text()
        if self.args.host:
            blob = blob.replace(self.args.host, "LANE")
        blob = re.sub(r"(https?://)[^/\s\")']+", r"\1LANE", blob)
        path.write_text(blob)
        print(f"[seeded] receipt: {path}", flush=True)
        return not self.failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default=os.environ.get("GRUNT_HOST", ""),
                    help="lane address (or GRUNT_HOST) - required, the repo bans address literals")
    ap.add_argument("--port", type=int, default=8891)
    ap.add_argument("--dead-port", type=int, default=8899,
                    help="a port nothing listens on, for the endpoint and CPU-fallback seeds")
    ap.add_argument("--ssh", default=os.environ.get("GRUNT_SSH", "pve"))
    ap.add_argument("--ssh-user", default="root")
    ap.add_argument("--ct", default="100")
    ap.add_argument("--unit", default="llama-worker@8891")
    ap.add_argument("--legs", default="unit,gpu,endpoint,pin,load,thermal")
    ap.add_argument("--ceiling-w", type=float, default=120.0)
    ap.add_argument("--seed-power-w", type=float, default=180.0)
    ap.add_argument("--burn-streams", type=int, default=3,
                    help="parallel llama-bench decode streams for the thermal seed (3 x a 2B Q4 "
                         "fits the 8 GiB card once the serving engine is stopped)")
    ap.add_argument("--thermal-budget-s", type=int, default=900)
    ap.add_argument("--bit-budget-s", type=int, default=300,
                    help="how long the burn may keep running after the temp refuse line to make "
                         "the card set its own slowdown bit (the throttle-state proof)")
    ap.add_argument("--receipt", default="results/_preflight")
    ap.add_argument("--force", action="store_true",
                    help="run even if a sweep looks live (it will stop the worker unit)")
    args = ap.parse_args(argv)

    if not args.host:
        print("seeded: --host (or GRUNT_HOST) is required", file=sys.stderr)
        return 10
    if not GATE.is_file():
        print(f"seeded: gate not found at {GATE}", file=sys.stderr)
        return 10

    if not args.force:
        sweep = sh(["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", args.ssh,
                    "pgrep", "-af", "pve_sweep|night_queue"]).stdout
        live = [ln for ln in sweep.splitlines() if ln.strip()]
        if live:
            print("[seeded] a sweep is live on the lane; it owns the card - pass --force to seed "
                  "anyway (the worker unit will be stopped under it)", file=sys.stderr)
            for ln in live:
                print(f"  {ln}", file=sys.stderr)
            return 3

    prover = Prover(args)
    ok = prover.run()
    print(f"[seeded] {'ALL SEEDS BEHAVED - lane restored and benchmarkable' if ok else 'FAILURES'}"
          .replace("FAILURES", "FAILURES: " + "; ".join(prover.failures)), flush=True)
    return 0 if ok else 1 if prover.failures else 9


if __name__ == "__main__":
    sys.exit(main())
