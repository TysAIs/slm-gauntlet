#!/usr/bin/env python3
"""Generate model trading cards (HTML+CSS, screenshot to PNG) from gauntlet results.

One card per model: rank badge, percentage scores per suite, capacity stats
(VRAM, KV pool, max concurrent subagents), tok/s curve, Pagoda %, verdict.
Cards are self-contained HTML; open in a headless browser and screenshot
at 1200x for Telegram-ready PNGs.
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


def summarize(model_glob: str) -> dict | None:
    d = load_latest(model_glob)
    if d is None:
        return None
    if "results" in d:
        suites: dict[str, list[float]] = {}
        for r in d["results"]:
            suites.setdefault(r["suite"], []).append(r["pass1"])
        per = {s: sum(v) / len(v) for s, v in suites.items()}
        overall = sum(per.values()) / len(per) if per else 0.0
        return {"suites": per, "overall_pct": overall * 100, "n": len(d["results"]),
                "model": d["meta"]["model"], "ts": d["meta"]["timestamp"]}
    return None


def perf_latest(model: str) -> dict | None:
    f = f"results/perf_{model}.json"
    return json.load(open(f)) if Path(f).exists() else None


def cap_latest(model: str) -> dict | None:
    f = f"results/cap_{model}.json"
    return json.load(open(f)) if Path(f).exists() else None


def pagoda_latest(model: str) -> dict | None:
    f = f"results/pagoda_{model}.json"
    return json.load(open(f)) if Path(f).exists() else None


CARD_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0d1117; font-family:'SF Pro Display','Segoe UI',sans-serif; }
.card { width:1100px; background:linear-gradient(145deg,#161b22,#1a2230);
  border:1px solid #30363d; border-radius:24px; padding:40px 44px; color:#e6edf3;
  position:relative; overflow:hidden; }
.card::before { content:''; position:absolute; top:0; left:0; right:0; height:6px;
  background:linear-gradient(90deg,#f5c518,#ff6b6b,#57a8ff); }
.hrow { display:flex; justify-content:space-between; align-items:flex-start; }
.model-name { font-size:44px; font-weight:800; letter-spacing:-1px; }
.model-quant { font-size:20px; color:#8b949e; margin-top:4px; }
.rank { text-align:center; }
.rank-letter { font-size:72px; font-weight:900; line-height:1; }
.rank-label { font-size:14px; font-weight:700; letter-spacing:2px; margin-top:6px; }
.overall { margin:28px 0 24px; }
.overall-pct { font-size:88px; font-weight:900; line-height:1; }
.overall-sub { font-size:16px; color:#8b949e; letter-spacing:3px; font-weight:600; }
.suites { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:26px; }
.suite { background:#0d1117; border:1px solid #30363d; border-radius:14px; padding:14px 12px; text-align:center; }
.suite-name { font-size:12px; color:#8b949e; text-transform:uppercase; letter-spacing:1.5px; }
.suite-val { font-size:30px; font-weight:800; margin-top:4px; }
.stats { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }
.stat { background:#0d1117; border:1px solid #30363d; border-radius:14px; padding:14px 16px; }
.stat-k { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1.5px; }
.stat-v { font-size:22px; font-weight:800; margin-top:4px; }
.stat-v small { font-size:13px; color:#8b949e; font-weight:600; }
.verdict { font-size:17px; line-height:1.5; color:#c9d1d9; border-left:3px solid #f5c518; padding-left:14px; }
.foot { margin-top:18px; font-size:12px; color:#6e7681; }
.bar { height:8px; border-radius:4px; background:#21262d; margin-top:8px; overflow:hidden; }
.bar>i { display:block; height:100%; border-radius:4px; }
"""


def suite_color(pct: float) -> str:
    if pct >= 90:
        return "#7bd88f"
    if pct >= 70:
        return "#f5c518"
    if pct >= 40:
        return "#e3b341"
    return "#ff6b6b"


def render_card(m: dict, perf: dict | None, cap: dict | None, pag: dict | None) -> str:
    letter, color, label = rank_for(m["overall_pct"])
    suites = m["suites"]
    order = ["tooluse", "coding", "instruction", "structured", "retrieval"]
    suite_html = ""
    for s in order:
        v = suites.get(s)
        if v is None:
            continue
        pct = v * 100
        suite_html += (
            f'<div class=suite><div class=suite-name>{s}</div>'
            f'<div class=suite-val style="color:{suite_color(pct)}">{pct:.0f}%</div>'
            f'<div class=bar><i style="width:{pct:.0f}%;background:{suite_color(pct)}"></i></div></div>'
        )
    stats_html = ""
    if perf:
        c1 = perf["concurrency"][0]["aggregate_tok_s"]
        c8 = perf["concurrency"][-1]["aggregate_tok_s"]
        ttft = perf["baseline_short"]["ttft_s"]
        stats_html += (
            f'<div class=stat><div class=stat-k>Speed (1 stream)</div>'
            f'<div class=stat-v>{c1}<small> tok/s</small></div></div>'
            f'<div class=stat><div class=stat-k>Speed (8 streams)</div>'
            f'<div class=stat-v>{c8}<small> tok/s</small></div></div>'
            f'<div class=stat><div class=stat-k>TTFT</div>'
            f'<div class=stat-v>{ttft:.1f}<small> s</small></div></div>'
        )
    if cap:
        agents = cap.get("max_concurrent_agents_at_8k_ctx", "—")
        pool = cap.get("kv_pool_available_mb", "—")
        wts = cap.get("weights_mb", "—")
        stats_html += (
            f'<div class=stat><div class=stat-k>Max subagents (8K ctx)</div>'
            f'<div class=stat-v>{agents}</div></div>'
            f'<div class=stat><div class=stat-k>KV pool</div>'
            f'<div class=stat-v>{pool}<small> MB</small></div></div>'
            f'<div class=stat><div class=stat-k>Weights VRAM</div>'
            f'<div class=stat-v>{wts}<small> MB</small></div></div>'
        )
    pag_html = ""
    if pag:
        tiers = pag.get("tiers_mentioned", "?")
        pag_html = (
            f'<div class=stat style="margin-bottom:22px;display:block">'
            f'<div class=stat-k>Pagoda build</div>'
            f'<div class=stat-v>{pag["pct"]:.0f}%<small> elements ({tiers} tiers)</small></div></div>'
        )
    verdict = m.get("verdict", "")
    return (
        f'<!DOCTYPE html><html><head><meta charset=utf-8><style>{CARD_CSS}</style></head>'
        f'<body><div class=card>'
        f'<div class=hrow>'
        f' <div><div class=model-name>{m["display_name"]}</div><div class=model-quant>{m.get("sub","")}</div></div>'
        f' <div class=rank><div class=rank-letter style="color:{color}">{letter}</div>'
        f'<div class=rank-label style="color:{color}">{label}</div></div>'
        f'</div>'
        f'<div class=overall><span class=overall-pct style="color:{color}">{m["overall_pct"]:.1f}%</span>'
        f'<div class=overall-sub>GAUNTLET SCORE — {m["n"]} TESTS</div></div>'
        f'<div class=suites>{suite_html}</div>'
        f'<div class=stats>{stats_html}{pag_html}</div>'
        f'<div class=verdict>{verdict}</div>'
        f'<div class=foot>slm-gauntlet 0.1 · seed=1 · all layers on an 8GB GPU · zero offload · {m.get("ts","")}</div>'
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
