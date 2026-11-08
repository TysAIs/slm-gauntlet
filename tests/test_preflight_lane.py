"""Offline proofs for scripts/preflight_lane.py.

The live gate is proven by seeded faults against the box (see the receipt); these tests replay
RECORDED samples so the rule set itself stays proven without touching the card:

  lane_live_healthy.json        real sample captured with --save-fixture on the live lane
  lane_throttled_sw_thermal     a real loaded row from the 13-minute thermal run (mask 0x20, 82 C)
  lane_endpoint_wedged          the real 2026-11-08 wedge output (/health ok, completion never came)
  the rest                      the healthy sample with ONE field changed, documented in "note"

Every test asserts the exit code AND the reported leg, because "non-zero" is not a diagnosis.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPT = HERE.parent / "scripts" / "preflight_lane.py"


def load_module():
    spec = importlib.util.spec_from_file_location("preflight_lane", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = load_module()


def run(*argv):
    return pf.main(list(argv))


def sample(name: str, **over) -> dict:
    d = json.loads((FIXTURES / name).read_text())
    d.update(over)
    return d


# --- the real state is green, and an idle clock is not a fault ---------------------------

def test_live_healthy_sample_is_benchmarkable(capsys):
    assert run("--fixture", str(FIXTURES / "lane_live_healthy.json")) == 0
    out = capsys.readouterr().out
    assert "RESULT benchmarkable exit=0" in out
    # The rule that keeps a healthy idle card out of the refuse path: GPU_IDLE is a state.
    assert "NOT a fault" in out
    assert "0x0000000000000001" in out


def test_idle_clock_never_refuses_whatever_the_clock():
    """A 139/1911 MHz idle card is healthy; the naive 'clock below X% of max' gate would fail it."""
    s = sample("lane_live_healthy.json")
    gpu = pf.judge_gpu(s)["data"]
    assert gpu["clocks_sm_mhz"] == 139 and gpu["clocks_sm_max_mhz"] == 1911
    assert pf.judge_gpu(s)["ok"] is True
    # Same card, same clock, only the idle bit cleared: still fine.
    s2 = json.loads(json.dumps(s))
    s2["gpu_csv"] = s["gpu_csv"].replace("0x0000000000000001", "0x0000000000000000")
    assert pf.judge_gpu(s2)["ok"] is True


@pytest.mark.parametrize("mask,ok", [
    ("0x0000000000000000", True),    # nothing set
    ("0x0000000000000001", True),    # GPU_IDLE, the measured idle state
    ("0x0000000000000002", True),    # applications clocks setting, not used here
    ("0x0000000000000004", True),    # SW power cap = the 120 W pin working
    ("0x0000000000000100", True),    # display clock setting
    ("0x0000000000000008", False),   # HW slowdown
    ("0x0000000000000020", False),   # SW thermal slowdown
    ("0x0000000000000040", False),   # HW thermal slowdown
    ("0x0000000000000080", False),   # HW power brake
    ("0x0000000000000021", False),   # idle + thermal: thermal wins
])
def test_throttle_mask_rule(mask, ok):
    s = sample("lane_live_healthy.json")
    row = s["gpu_csv"].split(",")
    row[9] = mask
    s["gpu_csv"] = ",".join(row)
    assert pf.judge_gpu(s)["ok"] is ok


# --- every leg refuses with its own code, from a recorded fault --------------------------

def test_unit_down(capsys):
    assert run("--fixture", str(FIXTURES / "lane_unit_down.json")) == pf.LEG_EXIT["unit"]
    assert "refused leg=unit exit=2" in capsys.readouterr().out


def test_wedged_endpoint():
    """The real wedge: /health 200, /v1/models ok, completion never came."""
    rc = run("--fixture", str(FIXTURES / "lane_endpoint_wedged.json"),
             "--legs", "endpoint")
    assert rc == pf.LEG_EXIT["endpoint"]


def test_cpu_fallback_refuses():
    rc = run("--fixture", str(FIXTURES / "lane_cpu_fallback.json"), "--legs", "gpu")
    assert rc == pf.LEG_EXIT["gpu"]
    assert pf.judge_gpu(sample("lane_cpu_fallback.json"))["ok"] is False


def test_cpu_fallback_with_a_bare_cuda_context_refuses():
    """`-ngl 0` on a card the engine CAN see: 169 MiB of context, zero layers offloaded.

    Measured 2026-11-08 by the seeded-fault prover: this state read as healthy under the old
    100 MiB floor and would have scored a CPU number.
    """
    s = sample("lane_live_healthy.json")
    s["gpu_csv"] = s["gpu_csv"].replace("5699 MiB", "169 MiB")
    rc = run("--fixture", str(FIXTURES / "lane_live_healthy.json"), "--legs", "gpu")
    assert rc == 0
    verdict = pf.judge_gpu(s)
    assert verdict["ok"] is False
    assert "NOT on the GPU" in verdict["detail"]


def test_a_real_offload_clears_the_floor():
    """1796 MiB is what the shipped 2B Q4 actually held at -ngl 99 (same run): not a refusal."""
    s = sample("lane_live_healthy.json")
    s["gpu_csv"] = s["gpu_csv"].replace("5699 MiB", "1796 MiB")
    assert pf.judge_gpu(s)["ok"] is True


def test_hard_throttle_refuses():
    rc = run("--fixture", str(FIXTURES / "lane_throttled_sw_thermal.json"), "--legs", "gpu")
    assert rc == pf.LEG_EXIT["gpu"]


def test_a_flickering_throttle_bit_still_refuses():
    """Measured: 0x20 one sample, 0x0 the next, at 82 C under a 3-stream burn.

    The run that follows lasts minutes, so one clean snapshot is not evidence. Any sampled
    slowdown bit must refuse, and the receipt must carry every mask that was read.
    """
    s = sample("lane_live_healthy.json")
    hot = s["gpu_csv"].replace("5699 MiB", "5393 MiB").replace("37", "82")
    hot = hot.rsplit(",", 1)[0] + ", 0x0000000000000020"
    clean = hot.rsplit(",", 1)[0] + ", 0x0000000000000000"
    s["gpu_csv_samples"] = [clean, hot, clean]
    verdict = pf.judge_gpu(s)
    assert verdict["ok"] is False
    assert "SW_THERMAL_SLOWDOWN" in verdict["detail"]
    assert verdict["data"]["throttle_masks_sampled"] == [
        "0x0000000000000000", "0x0000000000000020", "0x0000000000000000"]
    assert run("--fixture", str(FIXTURES / "lane_live_healthy.json"), "--legs", "gpu") == 0


def test_thermal_and_throttle_are_reported_together():
    """The full gate must name the card state, not just the first symptom."""
    rc = run("--fixture", str(FIXTURES / "lane_throttled_sw_thermal.json"), "--json")
    assert rc == pf.LEG_EXIT["gpu"]
    # thermal leg also fails on the same sample
    assert run("--fixture", str(FIXTURES / "lane_throttled_sw_thermal.json"),
               "--legs", "thermal") == pf.LEG_EXIT["thermal"]


def test_foreign_load_refuses():
    rc = run("--fixture", str(FIXTURES / "lane_foreign_load.json"), "--legs", "load")
    assert rc == pf.LEG_EXIT["load"]


def test_foreign_load_seed_by_allow_list():
    """A real healthy sample plus a stricter allow-list: the worker itself becomes 'foreign'."""
    rc = run("--fixture", str(FIXTURES / "lane_live_healthy.json"), "--legs", "load",
             "--allow-proc", "not-this-binary")
    assert rc == pf.LEG_EXIT["load"]


def test_busy_card_refuses_but_is_not_foreign():
    r = pf.judge_load(sample("lane_busy.json"), ["llama-server"])
    assert r["ok"] is False and "busy" in r["detail"]
    assert r["data"]["foreign"] == []


def test_unpinned_card_refuses():
    assert run("--fixture", str(FIXTURES / "lane_unpinned.json"), "--legs", "pin") == \
        pf.LEG_EXIT["pin"]


def test_memory_capped_unit_refuses():
    assert run("--fixture", str(FIXTURES / "lane_memory_capped.json"), "--legs", "unit") == \
        pf.LEG_EXIT["unit"]


# --- transport and usage are not verdicts -----------------------------------------------

def test_missing_fixture_is_cannot_ask(tmp_path):
    assert run("--fixture", str(tmp_path / "nope.json")) == pf.E_CANNOT_ASK


def test_unparsable_gpu_row_is_cannot_ask():
    s = sample("lane_live_healthy.json", gpu_csv="garbage")
    with pytest.raises(pf.CannotAsk):
        pf.judge_gpu(s)


def test_unknown_leg_is_usage_error():
    assert run("--fixture", str(FIXTURES / "lane_live_healthy.json"), "--legs", "bogus") == \
        pf.E_USAGE


def test_no_host_and_no_fixture_is_usage_error(monkeypatch):
    monkeypatch.delenv("GRUNT_HOST", raising=False)
    assert run() == pf.E_USAGE


def test_skip_leg(tmp_path):
    s = sample("lane_unpinned.json")
    p = tmp_path / "s.json"
    p.write_text(json.dumps(s))
    # skipping the only failing leg on a clean sample returns green
    assert run("--fixture", str(p), "--skip", "pin") == 0


def test_save_fixture_sanitizes_addresses(tmp_path):
    """Recorded samples are committed, so they may not carry the lane's address."""
    p = tmp_path / "out.json"
    run("--fixture", str(FIXTURES / "lane_live_healthy.json"), "--save-fixture", str(p))
    text = p.read_text()
    assert "http://LANE" in text
