"""Offline proofs for scripts/preflight_seeded_faults.py (the live seeded-fault prover).

The prover itself needs the box; these tests pin the two things that would make it lie while
still printing "PASS":

  * an expectation that disagrees with the shipped gate's own exit contract, so it "proves" the
    wrong refusal - cross-checked here against preflight_lane.LEG_EXIT;
  * the ssh double-parse bug: ssh joins its argv into one string and the remote login shell
    parses it again, so an unquoted `sh -c 'cd ... && nohup ./bin ...'` silently became
    `sh -c cd` plus a background job in the wrong directory. The burn then died with
    "No such file or directory" on a binary that existed, and the load leg passed for the wrong
    reason (measured 2026-11-08, t_837f2ef).
"""

from __future__ import annotations

import importlib.util
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


prover = load("preflight_seeded_faults", "preflight_seeded_faults.py")
gate = load("preflight_lane_for_prover_tests", "preflight_lane.py")


def test_every_seeded_leg_expects_the_code_the_gate_actually_returns():
    assert set(prover.EXPECTED_EXIT) == set(gate.LEG_EXIT), (
        "the prover and the gate disagree about which legs exist")
    for leg, code in prover.EXPECTED_EXIT.items():
        assert gate.LEG_EXIT[leg] == code, f"{leg}: prover expects {code}, gate returns {gate.LEG_EXIT[leg]}"


def test_remote_commands_are_quoted_for_the_second_shell(monkeypatch):
    captured = {}

    class Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_sh(argv, timeout=120, input_text=None):
        captured["argv"] = argv
        return Done()

    monkeypatch.setattr(prover, "sh", fake_sh)
    lane = prover.Lane("pve", "100", "llama-worker@8891", 8891, "lane.example")
    lane.run(["sh", "-c", "cd /opt && nohup ./llama-bench -m x > /tmp/y 2>&1 < /dev/null &"])
    remote = captured["argv"][-1]
    # One argument, fully quoted: the remote shell must hand `sh -c` the whole pipeline.
    assert remote == shlex.join([
        "pct", "exec", "100", "--", "sh", "-c",
        "cd /opt && nohup ./llama-bench -m x > /tmp/y 2>&1 < /dev/null &"])
    # the pipeline is ONE quoted word, so the remote shell cannot split it at its spaces/&&/>,
    assert remote.endswith(
        "'cd /opt && nohup ./llama-bench -m x > /tmp/y 2>&1 < /dev/null &'")


def test_burn_prefers_a_model_that_fits_beside_the_serving_engine(monkeypatch):
    """The burn must not load the served 12B: 5.7 GiB is already resident on an 8 GiB card."""
    rows = [
        "407207584\t/mnt/data/models/small-600m-Q8_0.gguf",
        "449397600\t/mnt/data/models/laya/Laya-Q8_0.gguf",
        "1615826144\t/mnt/data/models/minicpm5-2b/MiniCPM5-2B-Q4_K_M.gguf",
        "5039006688\t/mnt/data/models/minicpm5-2b/MiniCPM5-2B-F16.gguf",
    ]

    class Done:
        returncode = 0
        stdout = "\n".join(rows)
        stderr = ""

    lane = prover.Lane("pve", "100", "llama-worker@8891", 8891, "lane.example")
    monkeypatch.setattr(lane, "run", lambda *a, **k: Done())
    assert lane.model_path().endswith("MiniCPM5-2B-Q4_K_M.gguf")


def test_burn_falls_back_to_the_smallest_gguf(monkeypatch):
    rows = [
        "407207584\t/mnt/data/models/small-600m-Q8_0.gguf",
        "449397600\t/mnt/data/models/laya/Laya-Q8_0.gguf",
    ]

    class Done:
        returncode = 0
        stdout = "\n".join(rows)
        stderr = ""

    lane = prover.Lane("pve", "100", "llama-worker@8891", 8891, "lane.example")
    monkeypatch.setattr(lane, "run", lambda *a, **k: Done())
    assert lane.model_path().endswith("small-600m-Q8_0.gguf")


def test_a_seed_expectation_cannot_contradict_the_table():
    """record() refuses to log a verdict whose expectation contradicts EXPECTED_EXIT."""
    class Args:
        ssh = "pve"
        ct = "100"
        unit = "llama-worker@8891"
        port = 8891
        host = "lane.example"
        ssh_user = "root"

    p = prover.Prover(Args())
    p.record("unit", "unit", prover.EXPECTED_EXIT["unit"], prover.EXPECTED_EXIT["unit"], "", "")
    assert p.rows[0]["ok"] is True
    try:
        p.record("unit", "unit", 99, 99, "", "")
    except SystemExit as exc:
        assert "disagrees" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("record() accepted an expectation that contradicts EXPECTED_EXIT")
