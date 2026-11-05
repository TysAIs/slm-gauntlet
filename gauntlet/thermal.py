"""Thermal guard for the test box.

The gauntlet runs on a single GTX 1070 Ti. Tyler's ruling (2026-11-04) is a HARD
abort at 89 C — the card is rated to 94 C. Before this module nothing in
`gauntlet/` ever read the GPU temperature, so `gauntlet run` would happily cook
the card; the only watchdog in the repo was a 84 C (pre-ruling) one-liner inside
the long-horizon sweep driver.

Scope of the guard, stated honestly: this is a PREFLIGHT check. It refuses to
start a run on an already-hot card. It does not sample mid-run — that needs a
thread or an external watchdog, and for long sweeps the sweep driver's monitor
(kill the server at the ceiling) remains the right tool.
"""

from __future__ import annotations

import shutil
import subprocess

# Tyler's ruling, 2026-11-04: abort at 89 C (1070 Ti is rated to 94 C).
THERMAL_LIMIT_C = 89.0


class ThermalAbort(SystemExit):
    """Raised (as SystemExit) when the GPU is at or above the ceiling."""


def read_gpu_temp_c(timeout: float = 5.0) -> float | None:
    """Current GPU temperature in C, or None when there is no readable sensor.

    None is deliberately not an error: a CPU-only host (or a container without
    nvidia-smi) must still be able to run the suite.
    """
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        return float(lines[0].split()[0])
    except (ValueError, IndexError):
        return None


def assert_thermal_ok(limit_c: float = THERMAL_LIMIT_C) -> float | None:
    """Refuse to start a run at or above `limit_c`. Returns the reading.

    limit_c <= 0 disables the check (for a host with no sensor, or a deliberate
    cold-room overclock).
    """
    if limit_c is None or limit_c <= 0:
        return None
    temp = read_gpu_temp_c()
    if temp is None:
        return None
    if temp >= limit_c:
        raise ThermalAbort(
            f"[gauntlet] thermal abort: GPU is {temp:.0f}C, ceiling is {limit_c:.0f}C "
            f"(Tyler's 89C rule). Let it cool, then re-run; --thermal-limit 0 disables."
        )
    return temp
