"""A failed sweep config must be a *labelled* failure, not a bare `serve_failed`.

Measured defect this pins (2026-11-07, PVE GTX 1070 Ti lane): seven configs were recorded
`serve_failed` after a 604-698 s wait and left nothing behind - the engine had printed the
reason in under a second. These fixtures are verbatim lines captured from the lane
(llama.cpp `a2878d3`) so a future edit cannot quietly drop the cause, the log, or the
thinking-model probe lever again.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pve_sweep", ROOT / "scripts" / "pve_sweep.py")
pve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pve)


# Verbatim from results/_sweep_logs/dory-1.0-4b-q5km-kvq8-kvq8_0.serve.log (2026-11-07).
DORY_ATTEMPT = """0.00.009.137 I srv    load_model: loading model '/mnt/data/models/dory-4b/NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf'
0.00.122.960 E llama_model_load: error loading model: unknown model architecture: 'dory'
0.00.122.966 E llama_model_load_from_file_impl: failed to load model
0.00.219.923 E srv    load_model: failed to load model, '/mnt/data/models/dory-4b/NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf'
0.00.220.340 E srv  llama_server: exiting due to model loading error
llama-worker@8893.service: Main process exited, code=exited, status=1/FAILURE
"""

# Verbatim from results/_sweep_logs/minicpm5-2b-q8_0-kvf16.serve.log (2026-11-07).
MINICPM5_ATTEMPT = """0.15.610.756 E ggml_backend_cuda_buffer_type_alloc_buffer: allocating 2279.73 MiB on device 0: cudaMalloc failed: out of memory
0.15.610.765 E alloc_tensor_range: failed to allocate CUDA0 buffer of size 2390466560
0.16.075.139 E llama_model_load: error loading model: unable to allocate CUDA0 buffer
0.16.075.505 E srv  llama_server: exiting due to model loading error
"""


def test_unsupported_architecture_is_named_with_the_gguf_arch():
    cause, detail = pve.classify_serve_failure(DORY_ATTEMPT, {"ActiveState": "failed"})
    assert cause == "unsupported_arch"
    assert "'dory'" in detail
    assert "not retryable" in detail


def test_cuda_allocation_failure_is_named_as_vram_oom_with_the_request_size():
    cause, detail = pve.classify_serve_failure(MINICPM5_ATTEMPT, {"ActiveState": "activating"})
    assert cause == "vram_oom"
    assert "2279.73 MiB" in detail


def test_a_dead_unit_without_engine_error_is_still_labelled():
    assert pve.classify_serve_failure("", {"ActiveState": "failed", "ExecMainStatus": "1"})[0] == "unit_failed"
    assert pve.classify_serve_failure("", {"ActiveState": "running", "SubState": "running"})[0] == "no_answer"


def test_stale_lines_from_the_previous_config_do_not_name_the_cause():
    """The journal window carries the previous config's crash loop: a stale dory line inside
    a minicpm5 attempt mislabelled a VRAM problem as an unsupported architecture."""
    log = (
        "# sweep serve attempt minicpm5-2b-q8_0 ctx=32768 kv=f16/f16\n"
        "llama-worker@8893.service: Scheduled restart job, restart counter is at 38.\n"
        "0.00.120.924 E llama_model_load: error loading model: unknown model architecture: 'dory'\n"
        "\n# --- restarted 13:44:37 - this attempt's output follows ---\n"
        + MINICPM5_ATTEMPT
    )
    cause, _ = pve.classify_serve_failure(pve.attempt_section(log), {"ActiveState": "activating"})
    assert cause == "vram_oom"


def test_exclusions_are_parsed_and_leave_the_config_row_visible(tmp_path):
    manifest = tmp_path / "m.tsv"
    manifest.write_text(
        "# alias\tpath\tctx\tnp\tctk\tctv\n"
        "!bad-arch\tGGUF arch 'bad' unknown to the deployed build\n"
        "bad-arch\t/mnt/data/x.gguf\t32768\t1\tf16\tf16\t-fa on\n"
        "good\t/mnt/data/y.gguf\t32768\t1\tq8_0\tq8_0\n"
    )
    entries, exclusions = pve.read_manifest(manifest)
    assert [e["alias"] for e in entries] == ["bad-arch", "good"]
    assert exclusions == {"bad-arch": "GGUF arch 'bad' unknown to the deployed build"}


def test_manifest_rows_reject_a_short_line(tmp_path):
    manifest = tmp_path / "m.tsv"
    manifest.write_text("only\tthree\tfields\n")
    with pytest.raises(SystemExit):
        pve.read_manifest(manifest)


def test_serve_argv_carries_the_config_port_and_extra_flags():
    entry = {"alias": "a", "path": "/mnt/data/a.gguf", "ctx": 32768, "np": 1,
             "ctk": "q8_0", "ctv": "q8_0", "extra": "-fa on --reasoning-budget 0",
             "port": 8893}
    argv = pve.serve_argv(entry)
    assert argv[argv.index("--port") + 1] == "8893"
    assert argv[-6:] == ["--min-p", "0.0", "-fa", "on", "--reasoning-budget", "0"]
    assert argv[argv.index("-ctk") + 1] == "q8_0"


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_probe_sends_the_thinking_lever_and_accepts_a_live_answer(monkeypatch):
    seen: list[dict] = []

    def fake_urlopen(req, timeout=None):
        body = json.loads(req.data.decode())
        seen.append(body)
        if body.get("chat_template_kwargs", {}).get("enable_thinking") is False:
            return _Resp({"choices": [{"message": {"content": "READY"}, "finish_reason": "stop"}]})
        return _Resp({"choices": [{"message": {"content": "",
                                              "reasoning_content": "The user asked me to reply with the"},
                                  "finish_reason": "length"}]})

    monkeypatch.setattr(pve.urllib.request, "urlopen", fake_urlopen)
    ok, meta = pve.probe_completion("127.0.0.1", 1, "ornith-9b-q4_K_M")
    assert ok is True
    assert meta["payload"] == "think_off"
    assert meta["answered_in"] == "content"
    # The lever is what made the healthy thinking model answer; without it the same server
    # returns an empty `content` at max_tokens=8 (the 2026-11-07 false serve_failed).
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_probe_counts_a_reasoning_only_answer_as_a_live_engine(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return _Resp({"choices": [{"message": {"content": "",
                                              "reasoning_content": "I will answer READY"},
                                  "finish_reason": "length"}]})

    monkeypatch.setattr(pve.urllib.request, "urlopen", fake_urlopen)
    ok, meta = pve.probe_completion("127.0.0.1", 1, "qwen35-9b-q4km")
    assert ok is True
    assert meta["answered_in"] == "reasoning_content"


def test_probe_rejects_a_response_with_no_content_and_no_reasoning(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return _Resp({"choices": [{"message": {"content": "", "reasoning_content": ""},
                                  "finish_reason": "length"}]})

    monkeypatch.setattr(pve.urllib.request, "urlopen", fake_urlopen)
    ok, meta = pve.probe_completion("127.0.0.1", 1, "dead")
    assert ok is False and meta == {}


def test_vram_gate_waits_until_the_card_is_free(monkeypatch):
    reads: list[int] = []

    def fake_gpu(lane):
        reads.append(1)
        if len(reads) == 1:
            return {"gpu_used_mib": 7713, "gpu_free_mib": 395}
        return {"gpu_used_mib": 400, "gpu_free_mib": 7700}

    monkeypatch.setattr(pve, "gpu_memory", fake_gpu)
    monkeypatch.setattr(pve.time, "sleep", lambda s: None)
    mem = pve.wait_card_idle(None, log=lambda *_: None, timeout_s=10)
    assert mem["gpu_free_mib"] == 7700 and len(reads) == 2


def test_vram_gate_is_bounded_and_reports_what_it_saw(monkeypatch):
    monkeypatch.setattr(pve, "gpu_memory", lambda lane: {"gpu_used_mib": 7713, "gpu_free_mib": 395})
    monkeypatch.setattr(pve.time, "sleep", lambda s: None)
    mem = pve.wait_card_idle(None, log=lambda *_: None, timeout_s=0)
    assert mem["gpu_free_mib"] == 395
