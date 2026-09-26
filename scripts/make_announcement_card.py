#!/usr/bin/env python3
"""Generate the SLM Gauntlet announcement card (1080x1080).

Same visual language as the model cards: same palette, fonts, rainbow
gradient strip, tile grid, progress bars. Explains what the gauntlet is,
how it was run, and shows the top finishers.

Usage: python scripts/make_announcement_card.py results/cards/manifest.json
"""
from __future__ import annotations

import html
import json
import sys
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gauntlet.device import detect_device


def suite_color(pct: float) -> str:
    if pct >= 90:
        return "#7bd88f"
    if pct >= 70:
        return "#f5c518"
    if pct >= 40:
        return "#e3b341"
    return "#ff6b6b"


# Same design tokens as make_cards.py
CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1080px; height:1080px; overflow:hidden; margin:0;
  background:#0d1117; font-family:'SF Pro Display','Segoe UI',sans-serif; }
.card { width:1080px; height:1080px; background:linear-gradient(145deg,#161b22,#1a2230);
  border:1px solid #30363d; border-radius:22px; padding:48px 52px; color:#e6edf3;
  position:relative; overflow:hidden; display:flex; flex-direction:column; }
.card::before { content:''; position:absolute; top:0; left:0; right:0; height:5px;
  background:linear-gradient(90deg,#f5c518,#ff6b6b,#57a8ff); }
.kicker { font-size:15px; color:#8b949e; letter-spacing:4px; font-weight:700; text-transform:uppercase; }
.title { font-size:84px; font-weight:900; letter-spacing:-2px; line-height:1.0; margin-top:8px; }
.title .accent { color:#f5c518; }
.tagline { font-size:23px; color:#c9d1d9; line-height:1.45; margin-top:18px; }
.tagline b { color:#e6edf3; }
.suites { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:30px; }
.suite:last-child { grid-column:span 1; }
.suite { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:18px 10px; text-align:center; }
.suite-name { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1.2px; }
.suite-n { font-size:26px; font-weight:800; margin-top:4px; color:#e6edf3; }
.suite-n small { font-size:12px; color:#8b949e; font-weight:600; }
.section { font-size:13px; color:#8b949e; letter-spacing:3px; font-weight:700;
  text-transform:uppercase; margin-top:34px; }
.podium { display:flex; flex-direction:column; gap:10px; margin-top:12px; }
.row { display:flex; align-items:center; background:#0d1117; border:1px solid #30363d;
  border-radius:12px; padding:14px 20px; gap:18px; }
.medal { font-size:30px; width:44px; text-align:center; }
.p-name { font-size:22px; font-weight:800; flex:1; }
.p-name small { display:block; font-size:13px; color:#8b949e; font-weight:600; margin-top:2px; }
.p-pct { font-size:34px; font-weight:900; margin-left:auto; }
.p-bar { width:180px; }
.bar { height:7px; border-radius:4px; background:#21262d; overflow:hidden; }
.bar>i { display:block; height:100%; border-radius:4px; }
.how { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:12px; }
.how .cell { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:16px 18px; }
.cell-k { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1.2px; }
.cell-v { font-size:19px; font-weight:700; margin-top:5px; line-height:1.35; }
.cell-v small { display:block; font-size:13px; color:#8b949e; font-weight:600; margin-top:4px; line-height:1.4; }
.foot { margin-top:auto; font-size:12px; color:#6e7681; display:flex;
  justify-content:space-between; gap:24px; }
.foot span { white-space:nowrap; }
"""


def render(manifest: list[dict], dev: tuple[str, int, str]) -> str:
    dev_name, dev_vram, dev_kind = dev
    kind_label = {"nvidia": "GPU", "amd": "GPU",
                  "apple": "Unified memory", "cpu": "Device"}.get(dev_kind, "Device")
    dev_mem = ""
    if dev_vram:
        dev_mem = f"{dev_vram/1000:.0f}GB" if dev_vram >= 100000 else f"{dev_vram/1024:.0f}GB"

    top = [e for e in manifest if e["rank"] <= 3]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    podium = ""
    for e in top:
        pct = e["overall_pct"]
        color = suite_color(pct)
        podium += (
            f'<div class=row><div class=medal>{medals.get(e["rank"], e["rank"])}</div>'
            f'<div class=p-name>{html.escape(e["display_name"])}'
            f'<small>{html.escape(e["sub"].split(" ·")[0])} · zero offload</small></div>'
            f'<div class=p-bar><div class=bar><i style="width:{pct:.0f}%;background:{color}"></i></div></div>'
            f'<div class=p-pct style="color:{color}">{pct:.1f}%</div></div>'
        )

    suites = [
        ("Tool use", "19", "real tools, real state"),
        ("Adversarial", "8", "injection resistance"),
        ("Agent chains", "6", "multi-turn pipelines"),
        ("Structured", "10", "strict JSON schemas"),
        ("Retrieval", "8", "long-context needles"),
        ("Coding", "6", "real bug fixes"),
        ("Instruction", "14", "stacked constraints"),
    ]
    suite_html = "".join(
        f'<div class=suite><div class=suite-name>{name}</div>'
        f'<div class=suite-n>{n}<small> tasks</small></div></div>'
        for name, n, _ in suites
    )
    total_tasks = sum(int(n) for _, n, _ in suites)

    return (
        f'<!DOCTYPE html><html><head><meta charset=utf-8><style>{CSS}</style></head>'
        f'<body><div class=card>'
        f'<div class=kicker>Open-source benchmark · MIT · 13 models tested</div>'
        f'<div class=title>SLM <span class=accent>Gauntlet</span></div>'
        f'<div class=tagline>Can small models actually <b>do work as subagents</b> — call tools, '
        f'recover from errors, follow instructions, retrieve from long context — '
        f'not just answer trivia? <b>{total_tasks} tasks · 7 suites · zero LLM judging.</b></div>'
        f'<div class=suites>{suite_html}</div>'
        f'<div class=section>Top finishers of 13 · pass@1 · seed 1 · temp 0 · sep 2026</div>'
        f'<div class=podium>{podium}</div>'
        f'<div class=section>How it ran</div>'
        f'<div class=how>'
        f'<div class=cell><div class=cell-k>Grading</div>'
        f'<div class=cell-v>Deterministic'
        f'<small>state checks, schemas, predicates — no LLM judge anywhere</small></div></div>'
        f'<div class=cell><div class=cell-k>This run on</div>'
        f'<div class=cell-v>{html.escape(dev_name)}'  # noqa: E501
        f'<small>{kind_label}{(" · " + dev_mem) if dev_mem else ""} · any device works, cards auto-detect yours</small></div></div>'  # noqa: E501
        f'<div class=cell><div class=cell-k>Reproducible</div>'
        f'<div class=cell-v>One command<small>same seed → identical results · cards generated from your run</small></div></div>'  # noqa: E501
        f'</div>'
        f'<div class=foot><span>Run it yourself → github.com/TysAIs/slm-gauntlet</span>'
        f'<span>results on {html.escape(dev_name)}{(" " + dev_mem) if dev_mem else ""} · v0.3.1</span></div>'
        f'</div></body></html>'
    )


def main() -> None:
    manifest = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else []
    outdir = Path("results/cards")
    outdir.mkdir(parents=True, exist_ok=True)
    dev = detect_device()
    p = outdir / "announcement.html"
    p.write_text(render(manifest, dev))
    print("wrote", p)


if __name__ == "__main__":
    main()
