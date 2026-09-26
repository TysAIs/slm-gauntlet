#!/usr/bin/env python3
"""Generate model trading cards (HTML+CSS, screenshot to PNG) from gauntlet results.

Square card, dense layout: rank badge, percentage scores per suite, capacity
stats (weights VRAM in GB, KV pool in context tokens, max concurrent subagents),
tok/s, Pagoda %, verdict. Self-contained HTML; screenshot at 1080x1080.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

RANKS = [
    (0.95, "S", "#f5c518", "DAILY DRIVER"),
    (0.85, "A", "#7bd88f", "SUBAGENT GRADE"),
    (0.70, "B", "#57a8ff", "CAPABLE GAPS"),
    (0.50, "C", "#c792ea", "SPECIALIST ONLY"),
    (0.00, "D", "#ff6b6b", "NOT VIABLE"),
]


def rank_for(pct: float) -> tuple[str, str, str]:
    for floor, letter, color, label in RANKS:
        if pct >= floor * 100:
            return letter, color, label
    return "D", "#ff6b6b", "NOT VIABLE"


def load_latest(pattern: str) -> dict | None:
    files = sorted(glob.glob(pattern))
    return json.load(open(files[-1])) if files else None


def perf_latest(model: str) -> dict | None:
    f = f"results/perf_{model}.json"
    return json.load(open(f)) if Path(f).exists() else None


def cap_latest(model: str) -> dict | None:
    f = f"results/cap_{model}.json"
    return json.load(open(f)) if Path(f).exists() else None


def pagoda_latest(model: str) -> dict | None:
    f = f"results/pagoda_{model}.json"
    return json.load(open(f)) if Path(f).exists() else None


def suite_color(pct: float) -> str:
    if pct >= 90:
        return "#7bd88f"
    if pct >= 70:
        return "#f5c518"
    if pct >= 40:
        return "#e3b341"
    return "#ff6b6b"


CARD_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0d1117; font-family:'SF Pro Display','Segoe UI',sans-serif; }
.card { width:1080px; height:1080px; background:linear-gradient(145deg,#161b22,#1a2230);
  border:1px solid #30363d; border-radius:22px; padding:44px 44px; color:#e6edf3;
  position:relative; overflow:hidden; display:flex; flex-direction:column; }
.card::before { content:''; position:absolute; top:0; left:0; right:0; height:5px;
  background:linear-gradient(90deg,#f5c518,#ff6b6b,#57a8ff); }
.hrow { display:flex; justify-content:space-between; align-items:center; }
.model-name { font-size:48px; font-weight:800; letter-spacing:-1px; line-height:1.05; }
.model-quant { font-size:18px; color:#8b949e; margin-top:5px; }
.rank { text-align:center; display:flex; align-items:center; gap:22px; }
.rank-num { font-size:20px; color:#8b949e; font-weight:700; }
.rank-letter { font-size:64px; font-weight:900; line-height:1; }
.rank-label { font-size:12px; font-weight:700; letter-spacing:2px; }
.scoreband { display:flex; align-items:center; gap:26px; margin:20px 0 18px; }
.overall-pct { font-size:96px; font-weight:900; line-height:0.95; }
.overall-sub { font-size:13px; color:#8b949e; letter-spacing:2px; font-weight:600; margin-top:6px; }
.suites { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:24px 0 20px; }
.suite { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:18px 12px; text-align:center; }
.suite-name { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1.2px; }
.suite-val { font-size:32px; font-weight:800; margin-top:3px; }
.stats { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:24px; }
.stat { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:16px 15px; }
.stat-k { font-size:10.5px; color:#8b949e; text-transform:uppercase; letter-spacing:1.2px; }
.stat-v { font-size:27px; font-weight:800; margin-top:3px; }
.stat-v small { font-size:13px; color:#8b949e; font-weight:600; }
.verdict { font-size:19px; line-height:1.5; color:#c9d1d9; border-left:3px solid #f5c518;
  padding-left:13px; margin:18px 0 6px; }
.foot { margin-top:auto; font-size:11px; color:#6e7681; display:flex; justify-content:space-between; }
.bar { height:7px; border-radius:4px; background:#21262d; margin-top:7px; overflow:hidden; }
.bar>i { display:block; height:100%; border-radius:4px; }
"""


def render_card(m: dict, perf: dict | None, cap: dict | None, pag: dict | None) -> str:
    letter, color, label = rank_for(m["overall_pct"])
    suites = m["suites"]
    order = ["tooluse", "adversarial", "agent_chains", "structured", "retrieval", "coding", "instruction"]
    suite_html = ""
    for s in order:
        v = suites.get(s)
        if v is None:
            continue
        pct = v * 100
        suite_html += (
            f'<div class=suite><div class=suite-name>{s.replace("_"," ")}</div>'
            f'<div class=suite-val style="color:{suite_color(pct)}">{pct:.0f}%</div>'
            f'<div class=bar><i style="width:{pct:.0f}%;background:{suite_color(pct)}"></i></div></div>'
        )
    stats_html = ""
    if perf:
        c1 = perf["concurrency"][0]["aggregate_tok_s"]
        c8 = perf["concurrency"][-1]["aggregate_tok_s"]
        ttft = perf["baseline_short"]["ttft_s"]
        stats_html += (
            f'<div class=stat><div class=stat-k>Speed 1→8 streams</div>'
            f'<div class=stat-v>{c1:.0f}<small> → </small>{c8:.0f}<small> tok/s</small></div></div>'
            f'<div class=stat><div class=stat-k>TTFT</div>'
            f'<div class=stat-v>{ttft:.1f}<small> s</small></div></div>'
        )
    if cap:
        wgb = cap.get("weights_mb", 0) / 1000
        max_tok = cap.get("kv_max_tokens_pool")
        if max_tok and max_tok >= 1000:
            kv_disp = f"{max_tok/1000:.0f}K tok"
        elif max_tok is not None:
            kv_disp = f"{max_tok} tok"
        else:
            kv_disp = "—"
        stats_html += (
            f'<div class=stat><div class=stat-k>Weights VRAM</div>'
            f'<div class=stat-v>{wgb:.1f}<small> GB</small></div></div>'
            f'<div class=stat><div class=stat-k>KV pool</div>'
            f'<div class=stat-v>{kv_disp}</div></div>'
            f'<div class=stat><div class=stat-k>Max context</div>'
            f'<div class=stat-v>{(cap.get("tested_ctx") or 0)/1000:.0f}<small> K tok</small></div></div>'
            f'<div class=stat><div class=stat-k>Streams tested</div>'
            f'<div class=stat-v>{cap.get("tested_slots") or 0}</div></div>'
            f'<div class=stat><div class=stat-k>KV per token</div>'
            f'<div class=stat-v>{(cap.get("kv_bytes_per_token") or 0)/1000:.1f}<small> KB</small></div></div>'
            f'<div class=stat><div class=stat-k>GPU</div>'
            f'<div class=stat-v>1070 Ti<small> 8GB</small></div></div>'
            f'<div class=stat><div class=stat-k>Offload</div>'
            f'<div class=stat-v style="color:#7bd88f">None<small> (100% VRAM)</small></div></div>'
        )
    pag_tile = ""
    if pag:
        pag_tile = (
            f'<div class=suite><div class=suite-name>Pagoda build</div>'
            f'<div class=suite-val style="color:#7bd88f">{pag["pct"]:.0f}%</div>'
            f'<div class=bar><i style="width:{pag["pct"]:.0f}%;background:#7bd88f"></i></div></div>'
        )
    verdict = m.get("verdict", "")
    n = m.get("n", 61)
    rank_num = m.get("rank", "")
    rank_html = (
        f'<div class=rank><span class=rank-num>#{rank_num}</span>'
        f'<div><div class=rank-letter style="color:{color}">{letter}</div>'
        f'<div class=rank-label style="color:{color}">{label}</div></div></div>'
    )
    return (
        f'<!DOCTYPE html><html><head><meta charset=utf-8><style>{CARD_CSS}</style></head>'
        f'<body><div class=card>'
        f'<div class=hrow>'
        f' <div><div class=model-name>{m["display_name"]}</div><div class=model-quant>{m.get("sub","")}</div></div>'
        f'{rank_html}'
        f'</div>'
        f'<div class=scoreband>'
        f'<div><span class=overall-pct style="color:{color}">{m["overall_pct"]:.1f}%</span>'
        f'<div class=overall-sub>GAUNTLET SCORE · {n} TESTS</div></div>'
        f'</div>'
        f'<div class=suites>{suite_html}{pag_tile}</div>'
        f'<div class=stats>{stats_html}</div>'
        f'<div class=verdict>{verdict}</div>'
        f'<div class=foot><span>slm-gauntlet 0.2 · seed 1 · temp 0 · zero offload</span>'
        f'<span>GTX 1070 Ti 8GB · {m.get("ts","")}</span></div>'
        f'</div></body></html>'
    )


def main() -> None:
    models = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else []
    outdir = Path("results/cards")
    outdir.mkdir(parents=True, exist_ok=True)
    for m in models:
        perf = perf_latest(m["model"])
        cap = cap_latest(m["model"])
        pag = pagoda_latest(m["model"])
        html = render_card(m, perf, cap, pag)
        p = outdir / f"card_{m['model']}.html"
        p.write_text(html)
        print("wrote", p)


if __name__ == "__main__":
    main()
