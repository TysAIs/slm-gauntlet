#!/usr/bin/env python3
"""Render gauntlet model cards (HTML from scripts/make_cards.py) to PNG.

Why this exists: make_cards.py writes self-contained HTML, but the published
PNGs in results/_published/cards/ were produced by hand and went stale (still
the 61-task scores after v0.3.1 moved to 71 tasks). A card pipeline that needs a
human with a browser is not a pipeline.

Requires playwright + a chromium build (/usr/bin/python3 has playwright on areo;
browsers live in ~/.cache/ms-playwright). No network: cards are self-contained.

Usage
  /usr/bin/python3 scripts/render_card_png.py results/cards/card_a.html ...
  /usr/bin/python3 scripts/render_card_png.py --manifest results/_published/cards/manifest.json
  /usr/bin/python3 scripts/render_card_png.py --all          # every results/cards/*.html
Options: --outdir (default results/_published/cards), --prefix (default png_card_),
         --size 1080, --timeout-ms 15000, --json-out <path>

Every render is verified: PNG magic + IHDR geometry must be exactly 1080x1080 and
the image must not be blank (file size floor, plus ImageMagick stddev when magick
is installed). A blank render is a hard failure - it exits non-zero.
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path


def png_geometry(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:33]
    if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def stddev(path: Path) -> float | None:
    magick = shutil.which("magick") or shutil.which("convert")
    if not magick:
        return None
    out = subprocess.run(
        [magick, "identify", "-format", "%[fx:standard_deviation]", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def targets_from_manifest(path: Path) -> list[Path]:
    data = json.load(open(path))
    if isinstance(data, dict):
        data = data.get("models", [])
    cards = Path("results/cards")
    out = []
    for m in data:
        f = cards / f"card_{m['model']}.html"
        if f.exists():
            out.append(f)
        else:
            print(f"  skip (no html): {f}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="*")
    ap.add_argument("--manifest")
    ap.add_argument("--all", action="store_true", help="render every results/cards/*.html")
    ap.add_argument("--outdir", default="results/_published/cards")
    ap.add_argument("--prefix", default="png_card_")
    ap.add_argument("--size", type=int, default=1080)
    ap.add_argument("--timeout-ms", type=int, default=15000)
    ap.add_argument("--min-bytes", type=int, default=20000)
    ap.add_argument("--json-out")
    a = ap.parse_args()

    targets: list[Path] = [Path(p) for p in a.html]
    if a.manifest:
        targets += targets_from_manifest(Path(a.manifest))
    if a.all:
        targets += sorted(Path("results/cards").glob("*.html"))
    targets = [t for t in targets if t.exists()]
    if not targets:
        print("no card html found (run scripts/make_cards.py first)", file=sys.stderr)
        return 2

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    results, bad = [], 0
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--headless=new", "--no-sandbox", "--force-color-profile=srgb"])
        page = browser.new_page(
            viewport={"width": a.size, "height": a.size},
            device_scale_factor=1,
        )
        page.set_default_timeout(a.timeout_ms)
        for src in targets:
            slug = src.stem.replace("card_", "")
            dst = outdir / f"{a.prefix}{slug}.png"
            page.goto(src.resolve().as_uri(), wait_until="load")
            page.wait_for_timeout(120)  # let webfonts/metrics settle
            page.screenshot(path=str(dst), animations="disabled")
            w, h = png_geometry(dst)
            sd = stddev(dst)
            size = dst.stat().st_size
            ok = w == a.size and h == a.size and size >= a.min_bytes and (sd is None or sd >= 0.02)
            if not ok:
                bad += 1
            results.append({
                "src": str(src), "dst": str(dst), "w": w, "h": h,
                "bytes": size, "stddev": sd, "ok": ok,
            })
            print(f"{'OK ' if ok else 'BAD'} {dst} {w}x{h} {size}B stddev={sd}")
        browser.close()

    if a.json_out:
        Path(a.json_out).write_text(json.dumps({"size": a.size, "renders": results}, indent=1))
    print(f"{len(results) - bad}/{len(results)} rendered and verified")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
