#!/usr/bin/env python3
"""Generate square Pagoda creative-writing cards (1080x1080) from results/pagoda_*.json.

Same template every time: pagoda SVG motif, score, tier list, full model text.
Usage: python scripts/make_pagoda_cards.py results/cards/manifest.json
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

PAG_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1080px; height:1080px; overflow:hidden; margin:0;
  background:#0d1117; font-family:'Georgia','Times New Roman',serif; }
.card { width:1080px; height:1080px; background:linear-gradient(160deg,#1a1f2b,#10141d);
  border:1px solid #30363d; border-radius:22px; padding:40px 44px; color:#e6edf3;
  position:relative; overflow:hidden; display:flex; flex-direction:column; }
.card::before { content:''; position:absolute; top:0; left:0; right:0; height:5px;
  background:linear-gradient(90deg,#e3b341,#ff6b6b,#57a8ff); }
.hrow { display:flex; justify-content:space-between; align-items:flex-start; }
.pag-title { font-size:26px; letter-spacing:6px; color:#e3b341; font-weight:700; text-transform:uppercase; }
.model-name { font-size:34px; font-weight:800; font-family:'SF Pro Display','Segoe UI',sans-serif; margin-top:6px; }
.model-quant { font-size:16px; color:#8b949e; font-family:'SF Pro Display','Segoe UI',sans-serif; margin-top:4px; }
.pct { text-align:right; }
.pct .v { font-size:64px; font-weight:900; color:#7bd88f; line-height:1;
  font-family:'SF Pro Display','Segoe UI',sans-serif; }
.pct .k { font-size:12px; color:#8b949e; letter-spacing:2px;
  font-family:'SF Pro Display','Segoe UI',sans-serif; margin-top:4px; }
.tiers { margin:18px 0; font-family:'SF Pro Display','Segoe UI',sans-serif; }
.tier-chip { display:inline-block; background:#0d1117; border:1px solid #30363d; border-radius:20px;
  padding:6px 16px; margin:0 8px 8px 0; font-size:14px; color:#c9d1d9; }
.tier-chip b { color:#e3b341; }
.text { font-size:21px; line-height:1.62; color:#d8dee6; flex:1; overflow:hidden;
  border-top:1px solid #21262d; padding-top:20px; }
.text p { margin-bottom:12px; }
.foot { margin-top:16px; font-size:12px; color:#6e7681; display:flex; justify-content:space-between;
  font-family:'SF Pro Display','Segoe UI',sans-serif; }
"""

SVG = """<svg width="88" height="88" viewBox="0 0 100 100" style="margin-top:4px">
  <g fill="none" stroke="#e3b341" stroke-width="2.5" stroke-linecap="round">
    <path d="M50 6 L64 22 L36 22 Z"/>
    <path d="M38 26 L62 26 L70 40 L30 40 Z"/>
    <path d="M34 44 L66 44 L74 58 L26 58 Z"/>
    <path d="M30 62 L70 62 L78 76 L22 76 Z"/>
    <path d="M26 80 L74 80 L82 92 L18 92 Z" opacity="0.7"/>
    <circle cx="50" cy="97" r="2.5" fill="#e3b341" stroke="none"/>
  </g>
</svg>"""

def render(name: str, quant: str, pct: float, tiers: int, text: str, ts: str) -> str:
    paras = "".join(f"<p>{html.escape(p.strip())}</p>" for p in text.split("\n\n") if p.strip())
    chips = "".join(f'<span class=tier-chip><b>T{i+1}</b> tier {i+1} ✓</span>' for i in range(tiers))
    return (f'<!DOCTYPE html><html><head><meta charset=utf-8><style>{PAG_CSS}</style></head>'
        f'<body><div class=card>'
        f'<div class=hrow><div><div class=pag-title>🏯 Pagoda</div>'
        f'<div class=model-name>{html.escape(name)}</div>'
        f'<div class=model-quant>{html.escape(quant)}</div></div>'
        f'{SVG}'
        f'<div class=pct><div class=v>{pct:.0f}%</div><div class=k>ELEMENT COVERAGE</div></div></div>'
        f'<div class=tiers>{chips}</div>'
        f'<div class=text>{paras}</div>'
        f'<div class=foot><span>slm-gauntlet 0.2 · pagoda creative suite · temp 0.7</span>'
        f'<span>GTX 1070 Ti 8GB · {ts}</span></div>'
        f'</div></body></html>')

def main() -> None:
    manifest = {m["model"]: m for m in json.load(open(sys.argv[1]))}
    outdir = Path("results/cards")
    outdir.mkdir(parents=True, exist_ok=True)
    import glob
    for f in sorted(glob.glob("results/pagoda_*.json")):
        d = json.load(open(f))
        model = f.split("pagoda_")[1][:-5]
        m = manifest.get(model, {})
        name = m.get("display_name", model)
        quant = m.get("sub", "")
        tiers = d.get("tiers_mentioned", 0)
        p = outdir / f"pagoda_{model}.html"
        p.write_text(render(name, quant, d.get("pct", 0), tiers, d.get("output", ""), d.get("ts", "2026-09-26")))
        print("wrote", p)

if __name__ == "__main__":
    main()
