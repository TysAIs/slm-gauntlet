#!/usr/bin/env python3
"""Patch scripts/make_cards.py: add details grid + failure-modes line, tighten padding.
Preserves style/colors/layout/rank bands. Idempotent: refuses to run twice.
"""
import sys
from pathlib import Path

p = Path("scripts/make_cards.py")
src = p.read_text()
assert "details-grid" not in src, "already patched"

# 1. tighter padding to make room for the details block (stays in 1080px)
src = src.replace(
    ".suite { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:10px 10px; text-align:center; }",
    ".suite { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:8px 10px; text-align:center; }")
src = src.replace(
    ".stat { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:9px 12px; }",
    ".stat { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:7px 10px; }")
src = src.replace(
    ".verdict { font-size:22px; line-height:1.45; color:#c9d1d9; border-left:4px solid #f5c518;\n  padding-left:18px; margin:16px 0 12px; }",
    ".verdict { font-size:22px; line-height:1.45; color:#c9d1d9; border-left:4px solid #f5c518;\n  padding-left:18px; margin:12px 0 10px; }\n"
    ".details-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:10px 0 2px; }\n"
    ".detail { background:#0d1117; border:1px solid #30363d; border-radius:10px; padding:6px 10px; }\n"
    ".detail-k { font-size:14px; color:#8b949e; text-transform:uppercase; letter-spacing:1.2px; }\n"
    ".detail-v { font-size:20px; font-weight:700; margin-top:2px; word-break:break-all; }\n"
    ".failmodes { font-size:18px; color:#c9d1d9; margin:8px 0 2px; }\n"
    ".failmodes b { color:#e3b341; }")

# 2. details + failure-modes HTML, inserted between stats and verdict
old = """        f'<div class=suites>{suite_html}</div>'
        f'<div class=stats>{stats_html}</div>'
        f'<div class={vcls}>{verdict}</div>'"""
new = """        f'<div class=suites>{suite_html}</div>'
        f'<div class=stats>{stats_html}</div>'
        f'{details_html}'
        f'{failmodes_html}'
        f'<div class={vcls}>{verdict}</div>'"""
assert old in src
src = src.replace(old, new)

# 3. build details_html / failmodes_html before the return
anchor = """    n = m.get("n", 61)"""
build = '''    d = m.get("details", {}) or {}
    def _gb(nbytes):
        return f"{nbytes/1e9:.2f} GB" if nbytes else "—"
    def _cell(k, v):
        return f'<div class=detail><div class=detail-k>{k}</div><div class=detail-v>{v}</div></div>'
    dcells = []
    if d.get("release_date"):
        dcells.append(_cell("Release", d["release_date"]))
    if d.get("gguf_file"):
        dcells.append(_cell("GGUF", d["gguf_file"] + f' ({_gb(d.get("gguf_size_bytes"))})'))
    if d.get("quant"):
        dcells.append(_cell("Quant", d["quant"]))
    if d.get("kv_type"):
        dcells.append(_cell("KV cache", d["kv_type"]))
    if d.get("context_tokens"):
        dcells.append(_cell("Context", f'{d["context_tokens"]:,} tok'))
    if d.get("vram_used_mb"):
        dcells.append(_cell("VRAM used", f'{d["vram_used_mb"]:,} / {d.get("vram_total_mb", 8192):,} MiB'))
    else:
        dcells.append(_cell("VRAM used", "not recorded"))
    if d.get("kv_pool_tokens"):
        dcells.append(_cell("KV pool", f'{d["kv_pool_tokens"]:,} tok'))
    if d.get("max_subagents") is not None:
        dcells.append(_cell("Max 8K subagents", str(d["max_subagents"])))
    if d.get("server_build"):
        dcells.append(_cell("Server build", d["server_build"]))
    if d.get("category"):
        dcells.append(_cell("Category", d["category"]))
    details_html = f'<div class=details-grid>{"".join(dcells)}</div>' if dcells else ""
    fm = m.get("failure_modes", {}) or {}
    if fm:
        fm_txt = " · ".join(f"{k} {v}" for k, v in sorted(fm.items()))
        failmodes_html = f'<div class=failmodes>Failure modes: <b>{fm_txt}</b></div>'
    else:
        failmodes_html = '<div class=failmodes>Failure modes: none</div>'
    n = m.get("n", 61)'''
assert anchor in src
src = src.replace(anchor, build, 1)

p.write_text(src)
print("patched OK")
