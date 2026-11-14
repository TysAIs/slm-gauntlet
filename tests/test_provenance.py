"""Provenance spine: every new result JSON records what produced it.

Covers the fingerprint query path (via client.version_info), the GGUF hash
cache (computed once per file version), write_results stamping run end, and
backward compatibility: a meta dict without provenance must write unchanged
in shape (old files and old callers keep working).
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gauntlet import provenance  # noqa: E402
from gauntlet.runner import write_results  # noqa: E402


def test_gguf_sha256_hashes_once_and_caches(tmp_path):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"GGUF-fake-bytes" * 100)
    expected = hashlib.sha256(b"GGUF-fake-bytes" * 100).hexdigest()
    assert provenance.gguf_sha256(f) == expected
    # second call is served from the cache even if the file becomes unreadable
    f.chmod(0)
    try:
        assert provenance.gguf_sha256(f) == expected
    finally:
        f.chmod(0o644)


def test_gguf_sha256_missing_file_is_none():
    assert provenance.gguf_sha256("/nonexistent/model.gguf") is None


async def test_collect_provenance_without_client():
    prov = await provenance.collect_provenance(
        None, quant="Q4_K_M", kv_type="q4_0", ctx=32768, np_=4,
        serve_flags="-c 32768 -np 4",
    )
    assert prov["engine_system_fingerprint"] is None
    assert prov["gguf_path"] is None and prov["gguf_sha256"] is None
    assert prov["quant"] == "Q4_K_M" and prov["kv_type"] == "q4_0"
    assert prov["ctx"] == 32768 and prov["np"] == 4
    assert prov["serve_flags"] == "-c 32768 -np 4"
    assert prov["run_started_at"] and prov["run_ended_at"] is None


async def test_collect_provenance_with_client_fingerprint():
    class FakeClient:
        async def version_info(self):
            return {"system_fingerprint": "fp-xyz"}

    prov = await provenance.collect_provenance(FakeClient())
    assert prov["engine_system_fingerprint"] == "fp-xyz"


def test_write_results_stamps_provenance_end(tmp_path):
    meta = {
        "model": "m", "methodology": "0.6.0",
        "provenance": {"run_started_at": "2026-11-08T00:00:00+00:00", "run_ended_at": None},
    }
    path = write_results([], meta, tmp_path)
    payload = json.loads(path.read_text())
    prov = payload["meta"]["provenance"]
    assert prov["run_started_at"] == "2026-11-08T00:00:00+00:00"
    assert prov["run_ended_at"] is not None
    # pre-existing meta keys untouched
    assert payload["meta"]["model"] == "m"
    assert payload["meta"]["gauntlet_version"] == "0.6.0"


def test_write_results_without_provenance_still_writes(tmp_path):
    path = write_results([], {"model": "m"}, tmp_path)
    payload = json.loads(path.read_text())
    assert "provenance" not in payload["meta"]
    assert payload["meta"]["model"] == "m"


def test_gguf_sha256_manifest_fallback(tmp_path, monkeypatch):
    # The GGUF lives on the test-lane host; this machine cannot read it, so
    # the digest comes from the worker-generated manifest keyed by path.
    mpath = tmp_path / "gguf_hashes.json"
    mpath.write_text(json.dumps({"entries": {
        "/mnt/data/models/x/model.gguf": {"sha256": "ab" * 32, "size": 123},
    }}))
    monkeypatch.setattr(provenance, "_MANIFEST_PATH", mpath)
    monkeypatch.setattr(provenance, "_MANIFEST_CACHE", None)
    assert provenance.gguf_sha256("/mnt/data/models/x/model.gguf") == "ab" * 32
    # a path absent from the manifest stays unknown, never guessed
    assert provenance.gguf_sha256("/mnt/data/models/x/other.gguf") is None


def test_gguf_sha256_local_read_wins_over_manifest(tmp_path, monkeypatch):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"GGUF-fake-bytes")
    expected = hashlib.sha256(b"GGUF-fake-bytes").hexdigest()
    mpath = tmp_path / "gguf_hashes.json"
    mpath.write_text(json.dumps({"entries": {
        str(f): {"sha256": "cd" * 32, "size": 15},
    }}))
    monkeypatch.setattr(provenance, "_MANIFEST_PATH", mpath)
    monkeypatch.setattr(provenance, "_MANIFEST_CACHE", None)
    assert provenance.gguf_sha256(f) == expected
