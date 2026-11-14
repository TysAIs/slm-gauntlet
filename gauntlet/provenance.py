"""Run provenance: what exactly produced a result file.

Every new result JSON's meta carries a `provenance` mapping: the engine's
system_fingerprint (from /version at run start), the GGUF path and its sha256
(hashed once per run and cached — a multi-GB file is never re-hashed per
task), the quant label, KV type, context size, slot count (np) and the full
serve flags when the caller knows them, plus run start/end timestamps.

The GGUFs live on the test-lane host, not on the machine running this CLI,
so local hashing usually cannot read them. For that case a worker-generated
manifest (`gguf_hashes.json` beside this module, sha256sum run on the host
over the model tree) is consulted by exact path; see `gguf_sha256`.

Everything here is best-effort and additive: fields the run cannot determine
are null, never guessed, and old result files (which have no provenance) keep
loading exactly as before.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

# (path, size, mtime_ns) -> hex digest. A run hashes each GGUF once.
_HASH_CACHE: dict[tuple[str, int, int], str] = {}

# Worker-side hash manifest: {path: {"sha256": hex, "size": int}} under an
# "entries" key (a flat path->entry mapping is also accepted). Generated on
# the test-lane host, where the files actually live; shipped with the repo so
# provenance survives the CLI running anywhere else. Regenerate by running
# sha256sum over the host's model tree and rebuilding the JSON.
_MANIFEST_PATH = Path(__file__).with_name("gguf_hashes.json")
_MANIFEST_CACHE: dict | None = None


def _manifest() -> dict:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        try:
            doc = json.loads(_MANIFEST_PATH.read_text())
        except (OSError, ValueError):
            doc = {}
        if isinstance(doc, dict) and isinstance(doc.get("entries"), dict):
            doc = doc["entries"]
        _MANIFEST_CACHE = doc if isinstance(doc, dict) else {}
    return _MANIFEST_CACHE


def _manifest_sha256(path_str: str) -> str | None:
    entry = _manifest().get(path_str)
    if isinstance(entry, dict):
        digest = entry.get("sha256")
        return digest if isinstance(digest, str) and digest else None
    if isinstance(entry, str) and entry:
        return entry
    return None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _gguf_sha256_local(p: Path) -> str | None:
    """sha256 of a locally readable GGUF, computed once per (path, size,
    mtime) and cached. None when the file cannot be read here."""
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), st.st_size, st.st_mtime_ns)
    if key in _HASH_CACHE:
        return _HASH_CACHE[key]
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    digest = h.hexdigest()
    _HASH_CACHE[key] = digest
    return digest


def gguf_sha256(path: str | Path) -> str | None:
    """sha256 of the GGUF file. Local read first (cached per file version);
    when the file is not readable from this machine — the normal case, since
    the GGUFs live on the test-lane host — fall back to the worker-generated
    manifest by exact path. Returns None when neither source knows the file:
    provenance records the path and leaves the digest unknown rather than
    failing the run or guessing."""
    p = Path(path)
    digest = _gguf_sha256_local(p)
    if digest is None:
        digest = _manifest_sha256(str(p))
    return digest


def engine_fingerprint_via_props(endpoint: str | None) -> str | None:
    """Fallback fingerprint source for llama.cpp builds whose /version
    route 404s but which stamp system_fingerprint on every completion
    (verified live 2026-11-08: build 1c3cdd2 answers completions with
    b1-1c3cdd2 while GET /version returns 404). One tiny completion;
    best-effort, returns None on any failure."""
    if not endpoint:
        return None
    try:
        import json as _json
        import urllib.request as _u
        base = endpoint.rstrip("/")
        model = None
        try:
            with _u.urlopen(base + "/models", timeout=10) as fh:
                data = _json.loads(fh.read().decode())
            model = ((data.get("data") or [{}])[0] or {}).get("id")
        except Exception:  # noqa: BLE001 - best-effort provenance
            model = None
        body = _json.dumps({
            "model": model, "max_tokens": 1, "temperature": 0,
            "messages": [{"role": "user", "content": "hi"}],
        }).encode()
        req = _u.Request(base + "/chat/completions", data=body,
                         headers={"Content-Type": "application/json"})
        with _u.urlopen(req, timeout=60) as fh:
            outj = _json.loads(fh.read().decode())
        fp = outj.get("system_fingerprint") if isinstance(outj, dict) else None
        return fp if isinstance(fp, str) and fp else None
    except Exception:  # noqa: BLE001 - provenance is best-effort
        return None


async def collect_provenance(
    client=None,
    *,
    gguf_path: str | None = None,
    quant: str | None = None,
    kv_type: str | None = None,
    ctx: int | None = None,
    np_: int | None = None,
    serve_flags: list[str] | str | None = None,
) -> dict:
    """Assemble the provenance mapping for a run about to start.

    `client` is queried for /version when provided; the engine fingerprint is
    the only field that needs the endpoint, everything else is caller-supplied
    serve configuration."""
    endpoint = getattr(client, "base_url", None) if client is not None else None
    fingerprint = None
    if client is not None:
        info = await client.version_info()
        fingerprint = info.get("system_fingerprint") if isinstance(info, dict) else None
    if not fingerprint:
        # Builds without a /version route still stamp every completion;
        # recover the same fingerprint from one tiny live completion.
        fingerprint = engine_fingerprint_via_props(endpoint)
    return {
        "engine_system_fingerprint": fingerprint,
        "gguf_path": gguf_path,
        "gguf_sha256": gguf_sha256(gguf_path) if gguf_path else None,
        "quant": quant,
        "kv_type": kv_type,
        "ctx": ctx,
        "np": np_,
        "serve_flags": serve_flags,
        "run_started_at": _utc_now(),
        "run_ended_at": None,
    }


def finish_provenance(meta: dict) -> dict:
    """Stamp run_ended_at on meta's provenance (if any) at write time."""
    prov = meta.get("provenance")
    if isinstance(prov, dict):
        prov = {**prov, "run_ended_at": _utc_now()}
        meta = {**meta, "provenance": prov}
    return meta
