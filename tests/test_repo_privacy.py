"""Publish-surface privacy invariants.

The hygiene gate scans tracked content for identity patterns, but two things it
cannot catch on its own are pinned here:

1. A path that must never become tracked. ``results/_sweep_logs/`` holds raw sweep
   console logs whose first line reproduces the entire command line, including the
   lane endpoint and local paths. ``.gitignore`` keeps them out today; this fails if
   one ever gets force-added the way the epoch run logs legitimately are.
2. The address families the gate must keep screening. The first revision of the gate
   screened only the 10/8 block and bare 100/8 prefixes, so an RFC1918 class-B or
   class-C address and the CGNAT ranges outside the screened prefix would have
   passed. This pins the gate's own coverage so a later cleanup cannot narrow it.

Every sample below is assembled from fragments rather than written literally: this
file is itself tracked, so a literal sample would trip the very gate it tests — the
same reason ``hygiene-check.sh`` builds its patterns from fragments.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "hygiene-check.sh"


def addr(*parts):
    """Join fragments into a dotted address without ever writing it literally."""
    return ".".join(parts)


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _is_git_checkout():
    return _git("rev-parse", "--git-dir").returncode == 0


def test_sweep_logs_are_never_tracked():
    """No file under results/_sweep_logs/ may be tracked, and the dir stays ignored."""
    if not _is_git_checkout():
        return  # source archive / installed wheel: nothing to check
    tracked = _git("ls-files", "results/_sweep_logs").stdout.strip()
    assert tracked == "", (
        "results/_sweep_logs/ holds unscubbed raw command lines and must never be "
        f"committed, but these paths are tracked:\n{tracked}")
    ignored = _git("check-ignore", "-v", "results/_sweep_logs/probe.log")
    assert ignored.returncode == 0, (
        "results/_sweep_logs/ must match an ignore rule; check-ignore found none")


def test_gate_screens_every_private_address_family():
    """The gate's pattern set must cover RFC1918 B/C and the CGNAT carrier range."""
    src = GATE.read_text()
    for required in ("168", "1[6-9]|2[0-9]|3[01]", "6[4-9]|[7-9][0-9]"):
        assert required in src, (
            f"hygiene-check.sh no longer screens {required!r}: private address "
            f"space would leak again")


def _gate_regex():
    src = GATE.read_text()
    m = re.search(r'^PATTERNS="(.+)"$', src, re.M)
    assert m, "PATTERNS assignment not found in hygiene-check.sh"
    frags = dict(re.findall(r"^([A-Z]\d)='([^']*)'$", src, re.M))
    expr = re.sub(r"\$\{([A-Z]\d)\}", lambda mm: frags.get(mm.group(1), ""), m.group(1))
    return re.compile(expr.replace("\\\\", "\\"))


def test_gate_flags_each_private_address_family():
    """A sample of every address family the gate claims to screen must match."""
    rx = _gate_regex()
    lane = addr("10", "0", "0", "7")
    cgnat_high = addr("100", "84", "56", "8")
    cgnat_low = addr("100", "64", "0", "1")
    class_b = addr("172", "20", "3", "4")
    class_c = addr("192", "168", "1", "5")
    for sample in ("http://" + cgnat_high + ":8891/v1", class_c, class_b,
                   lane, cgnat_low):
        assert rx.search(sample), f"gate fails to flag {sample!r}"


def test_gate_flags_literal_lane_alias():
    """The ssh alias values and the private dotfiles path must be screened."""
    rx = _gate_regex()
    alias = "p" + "ve"
    private_path = "migration" + "-backup" + "/dotfiles"
    for sample in ("ssh " + alias, "--ssh " + alias, alias + "-node", private_path):
        assert rx.search(sample), f"gate fails to flag {sample!r}"
