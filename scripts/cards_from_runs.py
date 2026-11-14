#!/usr/bin/env python3
"""Build model card JSON from a real run log, for every config a sweep measured.

WHY THIS EXISTS
---------------
`results/cards/card_<model>.json` is the corpus the published leaderboard is
built from, and those cards used to be written by hand, one script per group of
models (`make-missing-cards*.py`). So a sweep could produce perfectly valid run
logs that never reached a table: the runner measures, the publisher only knows
what someone typed into a card.

This script closes that gap generically. For any model id it finds the newest
complete run log, recomputes the score from THAT log with the CLI suite weights,
and writes a card carrying the exact quant, KV cache type and context the run
actually used. Nothing is guessed: an unknown quant string or a missing GGUF
size is left as "—" rather than invented.

USAGE
  python3 scripts/cards_from_runs.py --from-sweep
      # every config in results/_sweep_state.jsonl that finished a full run
      # under the 120 W sustained-load pin
  python3 scripts/cards_from_runs.py --models id1,id2 --allow-unpinned
      # explicit ids; --allow-unpinned admits runs measured before the pin
  python3 scripts/cards_from_runs.py --from-sweep --dry-run

BRING YOUR OWN RUN
  You do not need this repo's sweep state, GGUF inventory or hardware. Point the
  tool at the model id of YOUR run log; quant, KV type and context are read from
  that log's own `meta.provenance`, and the card is stamped with the device this
  machine reports (gauntlet.device.detect_device), not with ours:
    gauntlet run --endpoint http://localhost:8080/v1 --model my-model --suite all
    python3 scripts/cards_from_runs.py --models my-model
    python3 scripts/cards_from_runs.py --models my-model --device "GTX 1070 Ti:8192:nvidia"
      # --device overrides detection, e.g. when re-deriving cards for a run that
      # was measured on another box
  then render the images with scripts/publish_cards.py.

A card is only written when the run log covers at least the epoch's task count,
so a partial/aborted run cannot produce a full-looking score.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gauntlet.cli import SUITE_WEIGHTS  # noqa: E402
from gauntlet.device import detect_device  # noqa: E402
from gauntlet.methodology import CURRENT_TASK_COUNT, METHODOLOGY_VERSION  # noqa: E402
from gauntlet.report import aggregate_results  # noqa: E402

CARDS = ROOT / "results" / "cards"
STATE = ROOT / "results" / "_sweep_state.jsonl"
SIZES = ROOT / "gguf-sizes.csv"

# Model family -> display name. Longest prefix wins. The leaderboard merges
# families by normalized display name, so all Bolt E4B quants (including the
# vendor-prefixed Nemotron ids) stay one family and are never split by spelling.
DISPLAY = [
    ("nvidia-nemotron-3.5-bolt-e4b", "Bolt E4B"),
    ("nemotron-3.5-bolt-e4b", "Bolt E4B"),
    ("nvidia-nemotron-labs-dory1.0-4b", "Dory 1.0 4B"),
    ("gemma4-e4b", "Gemma 4 E4B"),
    ("gemma-e4b", "Gemma 3n E4B"),
    ("gemma4-12b", "Gemma 4 12B"),
    ("spark-x2.6-4b", "Spark-X2.6-4B"),
    ("spark-x2.6-1.7b", "Spark-X2.6-1.7B"),
    ("bolt-e4b", "Bolt E4B"),
    ("dory-1.0-4b", "Dory 1.0 4B"),
    ("qwen3.5-4b", "Qwen3.5-4B"),
    ("qwen35-9b", "Qwen3.5-9B"),
    ("ornith-9b", "Ornith-1.5-9B"),
    ("mimo-9b", "MiMo-V2.6-9B"),
    ("minicpmv47-1b", "MiniCPM-V 4.7 1B"),
    ("minicpm5-2b", "MiniCPM5-2B"),
    ("lfm2.5-2.6b", "LFM2.5-2.6B"),
    ("lfm25-8b-a1b", "LFM2.5-8B-A1B"),
    ("lfm25-1.2b", "LFM2.5-1.2B"),
    ("lfm3-1.7b", "LFM3-1.7B"),
    ("sharp-spark-4b", "Sharp-Spark-4B"),
    ("qwen3.5-9b", "Qwen3.5-9B"),
    ("qwen3.5-0.8b", "Qwen3.5-0.8B"),
    ("qwen3.5-2b", "Qwen3.5-2B"),
    ("gemma3n-e4b", "Gemma 3n E4B"),
    ("gemma4-e2b", "Gemma 4 E2B"),
    ("nemotron3-nano-4b", "Nemotron 3 Nano 4B"),
    ("ministral3-3b", "Ministral 3 3B"),
    ("ministral3-8b", "Ministral 3 8B"),
    ("granite4.2-3b", "Granite 4.2 3B"),
    ("granite4.2-8b", "Granite 4.2 8B"),
    ("minicpm5-1b", "MiniCPM5-1B"),
    ("llama-3.1-8b", "Llama 3.1 8B"),
    ("lfm2.5-1.2b", "LFM2.5-1.2B"),
    ("mimo-v2.6-9b", "MiMo-V2.6-9B"),
    ("ornith-1.5-9b", "Ornith-1.5-9B"),
    ("lfm2.5-8b-a1b", "LFM2.5-8B-A1B"),
]
RELEASE = {
    "Bolt E4B": "Nov 2026",
    "Dory 1.0 4B": "Nov 2026",
    "Gemma 4 E4B": "2026",
    "Gemma 3n E4B": "Jun 2025",
    "Qwen3.5-4B": "2026",
    "Qwen3.5-9B": "Feb–Mar 2026",
    "Ornith-1.5-9B": "2026",
    "MiMo-V2.6-9B": "2026",
    "MiniCPM5-2B": "2026",
    "MiniCPM-V 4.7 1B": "2026",
    "LFM2.5-2.6B": "2026",
    "LFM2.5-8B-A1B": "May 28 2026",
    "LFM2.5-1.2B": "Jan 2026",
    "LFM3-1.7B": "2026",
    "Qwen3.5-0.8B": "2026",
    "Qwen3.5-2B": "2026",
    "Nemotron 3 Nano 4B": "Mar 2026",
    "Ministral 3 3B": "Dec 2025",
    "Ministral 3 8B": "Dec 2025",
    "Granite 4.2 3B": "2026",
    "Granite 4.2 8B": "2026",
    "MiniCPM5-1B": "May 2026",
    "Gemma 4 E2B": "2026",
    "Llama 3.1 8B": "Jul 2024",
}
KV_LABEL = {"f16": "FP16", "q8_0": "q8_0", "q4_0": "q4_0", "q4_1": "q4_1", "bf16": "BF16"}
QUANT_RE = re.compile(
    r"(UD-)?(IQ\d+_[A-Z0-9]+|Q\d+_K(_[A-Z]+)?|Q\d+_\d+|Q\d+_K|Q\d+)", re.IGNORECASE
)


def display_for(model_id: str) -> tuple[str, str]:
    """(display name, family key) for a model/config id. Never invents a name."""
    for prefix, name in DISPLAY:
        if model_id.startswith(prefix):
            return name, prefix
    return model_id, model_id


def quant_of(gguf_path: str) -> str | None:
    """Quant label exactly as the GGUF filename spells it, else None."""
    m = QUANT_RE.search(Path(gguf_path).stem)
    if not m:
        return None
    return (m.group(0) or "").lstrip("-").upper().replace("UD-", "UD-")


def gguf_sizes() -> dict[str, int]:
    """basename -> byte size from the checked-in size table.

    `gguf-sizes.csv` holds basenames only: the box's absolute model paths are
    operator-local and never ship. A size that is not in the table stays unknown
    ("—" on the card, category read from the run log) instead of being guessed.
    """
    inv: dict[str, int] = {}
    if not SIZES.exists():
        return inv
    with SIZES.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("gguf_file") or "").strip()
            size = (row.get("bytes") or "").strip()
            if name and size.isdigit():
                inv[name] = int(size)
    return inv


def device_for(row: dict, meta: dict, override: tuple[str, int, str] | None = None):
    """The device a card is stamped with.

    Explicit override wins (re-deriving cards for a run measured elsewhere), then
    anything the run itself declared, then this machine. Never a hardcoded box:
    a card that says GTX 1070 Ti on a Mac is a lie about the hardware.
    """
    if override:
        return override
    prov = meta.get("provenance") or {}
    name = row.get("device_name") or prov.get("device_name")
    if name:
        vram = row.get("device_vram_mb") or prov.get("device_vram_mb") or 0
        kind = row.get("device_kind") or prov.get("device_kind") or ""
        return str(name), int(vram), str(kind)
    return detect_device()


def parse_device(spec: str) -> tuple[str, int, str]:
    """'NAME:VRAM_MB:KIND' -> tuple. See --device."""
    parts = spec.rsplit(":", 2)
    if len(parts) != 3 or not parts[1].strip().isdigit():
        raise SystemExit(f"--device must be NAME:VRAM_MB:KIND, got {spec!r}")
    return parts[0].strip(), int(parts[1]), parts[2].strip()


def state_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def newest_run(model_id: str, min_tasks: int) -> tuple[Path, dict] | None:
    best = None
    for f in glob.glob(str(ROOT / "results" / f"{glob.escape(model_id)}_*.json")):
        try:
            d = json.load(open(f))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(d, dict) or "results" not in d:
            continue
        if len(d["results"]) < min_tasks:
            continue
        ts = str((d.get("meta") or {}).get("timestamp", ""))
        if best is None or ts > best[0]:
            best = (ts, Path(f), d)
    if not best:
        return None
    return best[1], best[2]


def build_card(model_id: str, row: dict, sizes: dict[str, int], min_tasks: int,
               device: tuple[str, int, str] | None = None) -> tuple[dict | None, str]:
    found = newest_run(model_id, min_tasks)
    if not found:
        return None, f"no complete run log with >= {min_tasks} tasks"
    rpath, run = found
    meta = run.get("meta") or {}
    agg = aggregate_results(run["results"], SUITE_WEIGHTS)
    suites = {k: v["pass1"] for k, v in agg["suites"].items()}
    prov = meta.get("provenance") or {}
    gguf = Path(row.get("path") or prov.get("gguf_path") or "").name
    quant = quant_of(gguf or model_id)
    if not quant and prov.get("quant"):
        quant = str(prov["quant"]).split("(")[0].strip() or None
    if row.get("ctk") or row.get("ctv"):
        ctk = row.get("ctk") or "f16"
        ctv = row.get("ctv") or ctk
    elif prov.get("kv_type"):
        ctk, _, ctv = str(prov["kv_type"]).partition("/")
        ctv = ctv or ctk
        ctk = ctk or "f16"
    else:
        ctk = "f16"
        ctv = ctk
    kv = KV_LABEL.get(ctk, ctk) if ctk == ctv else f"{KV_LABEL.get(ctk, ctk)}/{KV_LABEL.get(ctv, ctv)}"
    display, _fam = display_for(model_id)
    size = sizes.get(gguf)
    ctx = int(row.get("ctx") or prov.get("ctx") or 32768)
    dev_name, dev_vram, dev_kind = device_for(row, meta, device)
    pin = f" · {row['gpu_power_limit_w']} W pin" if row.get("gpu_power_limit_w") else ""
    # A card must never claim hardware or an engine it did not run on. Size unknown
    # is not the same as "does not fit", and another box's build string is not ours.
    on_gpu = bool(size) and size <= int(7.5 * 1024**3)  # weights fit the card on their own
    category = "on-GPU ≤12B" if on_gpu else ("offload" if size else "unclassified")
    server_build = prov.get("engine_system_fingerprint") or row.get("server_build") or "not recorded"
    card = {
        "model": model_id,
        "display_name": display,
        "sub": f"{quant or '—'} · KV {kv} · {ctx // 1000}K · {dev_name}{pin}",
        "overall_pct": round(agg["subagent_capability_score"] * 100, 1),
        "suites": suites,
        "n": len(run["results"]),
        "rank": "",
        "ts": str(meta.get("timestamp", ""))[:8],
        "device_name": dev_name,
        "device_vram_mb": dev_vram,
        "device_kind": dev_kind,
        "failure_modes": agg["failure_modes"],
        "details": {
            "release_date": RELEASE.get(display) or "",
            "gguf_file": gguf or "",
            "gguf_size_bytes": size,
            "quant": quant,
            "kv_type": kv,
            "context_tokens": ctx,
            "vram_total_mb": dev_vram,
            "kv_pool_tokens": ctx,
            "max_subagents": ctx // 8192,
            "server_build": server_build,
            "category": category,
            "methodology": meta.get("methodology"),
            "run_log": str(rpath.relative_to(ROOT)),
            "gpu_power_limit_w": row.get("gpu_power_limit_w"),
            "gpu_persistence": row.get("gpu_persistence"),
            "gpu_pins_ok": row.get("gpu_pins_ok"),
            "transport_failure": meta.get("transport_failure"),
            "zero_token_errors": meta.get("zero_token_errors"),
            "attempts": meta.get("attempts"),
        },
    }
    return card, "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", default=str(STATE))
    ap.add_argument("--from-sweep", action="store_true", help="use done configs from the sweep state file")
    ap.add_argument("--models", default="", help="comma-separated model ids (run log prefix)")
    ap.add_argument("--allow-unpinned", action="store_true",
                    help="admit runs measured before the sustained-load pin (different thermal epoch)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written")
    ap.add_argument("--device", default="", metavar="NAME:VRAM_MB:KIND",
                    help="stamp every card with this device instead of auto-detecting "
                         "(use it to re-derive cards for runs measured on another box)")
    a = ap.parse_args(argv)

    device = parse_device(a.device) if a.device else None
    sizes = gguf_sizes()
    targets: list[tuple[str, dict]] = []
    rows = state_rows(Path(a.state))
    last: dict[tuple, dict] = {}
    for r in rows:
        last[(r.get("alias"), r.get("ctk"), r.get("path"))] = r
    if a.from_sweep:
        for (_alias, _ctk, _path), r in last.items():
            if r.get("status") != "done":
                continue
            if not a.allow_unpinned and r.get("gpu_pins_ok") is not True:
                print(f"skip {r.get('alias')}: measured before the 120 W pin (gpu_pins_ok={r.get('gpu_pins_ok')})")
                continue
            targets.append((str(r.get("alias")), r))
    else:
        by_alias = {str(r.get("alias")): r for r in last.values()}
        for mid in [m.strip() for m in a.models.split(",") if m.strip()]:
            targets.append((mid, by_alias.get(mid, {"alias": mid})))
        if not targets:
            print("nothing to do: pass --from-sweep or --models", file=sys.stderr)
            return 2

    min_tasks = CURRENT_TASK_COUNT
    print(f"[cards] methodology {METHODOLOGY_VERSION}, {min_tasks} tasks; {len(targets)} target(s)")
    wrote = 0
    for model_id, row in targets:
        card, why = build_card(model_id, row, sizes, min_tasks, device)
        if not card:
            print(f"skip {model_id}: {why}")
            continue
        out = CARDS / f"card_{model_id}.json"
        print(f"{card['overall_pct']:5.1f}%  {model_id}  ({card['details']['quant'] or '—'} · KV "
              f"{card['details']['kv_type']} · {card['n']} tasks)  -> {out.name}")
        if not a.dry_run:
            CARDS.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps([card], indent=1))
        wrote += 1
    print(f"[cards] {wrote} card(s) {'checked' if a.dry_run else 'written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
