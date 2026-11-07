#!/usr/bin/env python3
"""Build the v0.5.0 sweep manifest: re-measure the ranked corpus, then the Nemotron matrix.

Two blocks, in this order, because the first is what a published table needs:

A. RANKED RE-RUN — for every rankable row in the current published leaderboard, the exact
   configuration that row names (gguf file, quant, KV type, context), resolved to a real
   on-box path. These are the rows a v0.5.0 table would restate.

B. NEMOTRON MATRIX — the intake the card asks for: every Bolt-E4B and Dory-1.0 quant that
   is actually on the test box, crossed with the three KV-cache types the corpus uses
   (f16 / q8_0 / q4_0). Labels carry the quant file and the KV type, so a row can never be
   read as another quant or KV setting. Quants NOT on the box are not invented: the
   manifest only lists files the inventory returned.

Inputs
  --inventory  lines of "<bytes>\\t<abs path>" for every .gguf on the box:
               ssh pve 'pct exec 100 -- find /mnt/data/models -name "*.gguf" -printf "%s\\t%p\\n"'
  --cards      results/cards (default; falls back to cards/manifest.json for headline rows)
  --published  results/_published/leaderboard.json (default; rankable rows only)

Output: TSV consumed by scripts/pve_sweep.py, plus a printed mapping. A row whose gguf
cannot be resolved to exactly ONE file on the box is refused and listed, not guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KV_TYPES = {"q4_0", "q8_0", "f16"}
# Reasoning budget 0 = thinking off, flash attention on: the corpus-wide serving settings.
EXTRA = "-fa on --reasoning-budget 0"
QUANT_RE = re.compile(r"(UD-)?(IQ|Q)\d[_A-Za-z0-9]*")

# EXCLUSIONS: a weights file the DEPLOYED engine cannot serve at any context. Measured on the
# lane 2026-11-07 with llama.cpp a2878d3 (2026-09-11): both files load-fail in ~0.2 s with
# "error loading model: unknown model architecture: 'dory' | 'lfm3'". They are not a ctx or
# VRAM verdict, so they are excluded by name with a reason the driver prints, instead of
# costing 600 s per row on every sweep. Keyed by gguf basename so every KV row of that file is
# covered, and re-enable by deleting the entry once the CT100 engine build is advanced.
ENGINE_UNSUPPORTED_REASON = (
    "GGUF architecture unknown to the deployed llama.cpp a2878d3 (2026-09-11): engine exits 1 "
    "in ~0.2 s with 'unknown model architecture' at any ctx, so this is an engine-upgrade "
    "exclusion, not a model/VRAM verdict. Evidence: results/_sweep_logs/<alias>-kv<ctk>.serve.log"
)
EXCLUDE_GGUF = {
    "NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf": ENGINE_UNSUPPORTED_REASON,
    "LFM3-1.7B-IQ4_NL.gguf": ENGINE_UNSUPPORTED_REASON,
}

# Explicit model-id -> gguf filename facts. Not a guess and not a fuzzy match: these are
# the rows whose two candidate files differ only by a size or generation token that the
# scoring rule cannot separate (2.6B vs 1.2B, 4B vs 9B, Gemma 3n vs Gemma 4). Each was
# read off the box inventory by a human and belongs here rather than in a heuristic.
ALIASES = {
    "gemma-e4b-q4_K_M": "gemma-3n-E4B-it-Q4_K_M.gguf",
    "lfm2.5-2.6b-q8_0": "LFM2.5-2.6B-Q8_0.gguf",
    "qwen3.5-4b-q4_K_M": "Qwen3.5-4B-Q4_K_M.gguf",
}


def norm_kv(sub: str, details: dict) -> str:
    raw = (details.get("kv_type") or "").strip().lower().replace("fp16", "f16")
    if raw in KV_TYPES:
        return raw
    low = (sub or "").lower()
    m = re.search(r"kv\s*(q\d_\w)", low)
    if m:
        return m.group(1)
    return "f16"


def load_inventory(path: Path) -> dict[str, str]:
    """Map gguf basename -> absolute path from the box's inventory.

    Two shapes are accepted, because both exist in this repo's history: one
    `<bytes>TAB<path>` pair per line (the runbook's `find -printf`), and the box's own
    single-line `bytes,path,bytes,path,...` dump (pve-gguf-inventory.txt). The second shape
    used to be skipped silently by a tab-only parser, so regenerating the manifest from the
    checked-in inventory refused every row.
    """
    inv: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        fields = line.split(",") if ("," in line and "\t" not in line) else [line]
        for i, tok in enumerate(fields):
            if i + 1 >= len(fields):
                break
            if "\t" in tok:
                size, p = tok.split("\t", 1)
            else:
                size, p = tok, fields[i + 1]
                if not size.strip().isdigit():
                    continue
            p = p.strip()
            if p.lower().endswith(".gguf"):
                inv[Path(p).name] = p
    return inv


def card_for(model_id: str, cards_dir: Path) -> dict | None:
    """Per-config card, else the headline-card manifest (14 published rows live only there)."""
    p = cards_dir / f"card_{model_id}.json"
    if p.exists():
        data = json.loads(p.read_text())
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and "overall_pct" in obj:
                return obj
    man = cards_dir / "manifest.json"
    if man.exists():
        data = json.loads(man.read_text())
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and obj.get("model") == model_id and "overall_pct" in obj:
                return obj
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", (s or "").lower())


def resolve_gguf(model_id: str, sub: str, details: dict, inv: dict[str, str]) -> tuple[str | None, str]:
    """Find the on-box file for a row. Refuses on ambiguity instead of guessing.

    Matching scores quant + family words, never a bare substring: a hint like "k" or "m"
    (from Q4_K_M) matches nearly every filename, which is how a resolver silently returns
    the wrong weights.
    """
    named = details.get("gguf_file") or ""
    if named and inv.get(named):
        return inv[named], "details.gguf_file"
    pinned = ALIASES.get(model_id)
    if pinned and inv.get(pinned):
        return inv[pinned], f"explicit alias -> {pinned}"
    m = QUANT_RE.search(sub or "")
    quant = m.group(0) if m else ""
    qn = _norm(quant)
    hints = [h for h in re.split(r"[-_.]", model_id.lower())
             if len(h) >= 3 and not re.match(r"^(ud|iq|q\d|kv|bartowski|prithiv)", h)]
    best: list[str] = []
    best_score = 0
    for name in inv:
        if "mmproj" in name.lower():
            continue
        nn = _norm(name)
        if qn and qn not in nn:
            continue
        score = sum(1 for h in hints if _norm(h) in nn)
        if hints and score == 0:
            continue
        if score > best_score:
            best, best_score = [name], score
        elif score == best_score:
            best.append(name)
    if len(best) == 1:
        return inv[best[0]], f"quant={quant!r} hints={hints} -> {best[0]}"
    if not best:
        return None, f"no file matches quant={quant!r} hints={hints}"
    return None, "ambiguous at score %d: %s" % (best_score, ", ".join(sorted(best)[:5]))


def ranked_rows(published: Path) -> list[dict]:
    d = json.loads(published.read_text())
    return [{"model": m.get("model"), "config": m.get("config"), "score": m.get("score")}
            for m in d.get("models") or []]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--cards", default=str(ROOT / "results" / "cards"))
    ap.add_argument("--published", default=str(ROOT / "results" / "_published" / "leaderboard.json"))
    ap.add_argument("--out", default=str(ROOT / "scripts" / "sweep_manifest_v050.tsv"))
    ap.add_argument("--nemotron-only", action="store_true")
    args = ap.parse_args()

    inv = load_inventory(Path(args.inventory))
    cards_dir = Path(args.cards)
    lines: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    def add(alias: str, path: str, ctx: int, np_: int, kv: str, extra: str = EXTRA) -> None:
        key = f"{alias}\t{path}\t{ctx}\t{kv}"
        if key in seen:
            return
        seen.add(key)
        lines.append("\t".join([alias, path, str(ctx), str(np_), kv, kv, extra]))

    block_a = 0
    if not args.nemotron_only:
        for row in ranked_rows(Path(args.published)):
            card = card_for(row["model"], cards_dir)
            if not card:
                missing.append(f"{row['model']}: no card (per-config or manifest)")
                continue
            det = card.get("details") or {}
            path, why = resolve_gguf(row["model"], card.get("sub", ""), det, inv)
            if not path:
                missing.append(f"{row['model']}: {why}")
                continue
            if why != "details.gguf_file":
                print(f"  resolved {row['model']} {why}")
            kv = norm_kv(card.get("sub", ""), det)
            ctx = int(det.get("context_tokens") or 32768)
            # np=1 for a large window: a measured np=2/32K/f16 slot pair did not finish a
            # 22k-token prompt inside 420 s, while np=1 served the same prompt in 30 s at
            # 675 tok/s prefill. Two slots halve the effective KV on an 8 GB card.
            add(row["model"], path, ctx, 1 if ctx >= 16384 else 2, kv)
            block_a += 1

    block_b = 0
    fam = [n for n in inv if re.search(r"nemotron-3\.5-bolt-e4b|nemotron-labs-dory1\.0-4b", n, re.I)]
    for name in sorted(fam):
        stem = re.sub(r"[^a-z0-9.]+", "-", name.rsplit(".gguf", 1)[0].lower()).strip("-")
        for kv in ("f16", "q8_0", "q4_0"):
            add(f"{stem}-kv{kv}", inv[name], 32768, 1, kv)
            block_b += 1

    exclusions: list[str] = []
    seen_excl: set[str] = set()
    for line in lines:
        f = line.split("\t")
        reason = EXCLUDE_GGUF.get(Path(f[1]).name)
        if reason and f[0] not in seen_excl:
            seen_excl.add(f[0])
            exclusions.append(f"!{f[0]}\t{reason}")

    Path(args.out).write_text("\n".join([
        "# v0.5.0 sweep manifest - consumed by scripts/pve_sweep.py",
        "# config row: alias<TAB>gguf_path<TAB>ctx<TAB>np<TAB>ctk<TAB>ctv[<TAB>extra_flags]",
        "# exclusion row: !<alias><TAB><reason> - the config row is skipped with that reason and",
        "#   never retried (the deployed engine cannot load that GGUF at any ctx)",
        "",
        *lines,
        "",
        "# EXCLUSIONS - measured on the lane, not assumed. See docs/SWEEP-v050.md.",
        *exclusions,
        "",
    ]) + "\n")
    print(f"wrote {len(lines)} configs (+{len(exclusions)} exclusions) -> {args.out}")
    print(f"  ranked re-run entries: {block_a}")
    print(f"  nemotron matrix entries: {block_b}")
    if missing:
        print("NOT re-runnable from the box (refused, not guessed):")
        for m in missing:
            print("  " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
