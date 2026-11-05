#!/usr/bin/env python3
"""VOXEL comparison animation: 3D voxel towers built from real gauntlet scores.

Output is a deterministic 1920x1080 H.264 MP4 (plus poster PNG and the source
HTML) intended for X/socials: model towers rise out of a voxel floor while the
camera orbits, then hold with labels. No GPU, no network, no blender/manim:
canvas-2D software renderer + playwright frame capture + ffmpeg mux.

Determinism comes from window.__frame(t): every screenshot sets the animation
clock explicitly, so the same input bytes always produce the same frames.

Data comes from the card JSONs that make_cards.py/gen-leaderboard.py already
produce (results/cards/*.json) *and* from results/cards/manifest.json, which is
where the published headline cards for older models live. Both are
scripts/leaderboard_check.py sources, so the animation cannot drift from the
published table. Model families are collapsed with the same display-name
normalisation the published leaderboard uses, and each rendered model prints a
selection receipt naming the JSON it came from.

Self-checks that gate exit 0: geometry (in frame, spread, tower heights), ink
density, subtitle actually inside the frame, the subtitle naming every model
with its quantization, and a read-back of the MODELS payload from the written
HTML (what renders == what was selected).

Usage
  /usr/bin/python3 scripts/voxel_compare.py --top 5            # writes results/_published/voxel_compare/
  /usr/bin/python3 scripts/voxel_compare.py --models minicpm5-2b-q8_0,gemma4-e4b-q4_K_M
  /usr/bin/python3 scripts/voxel_compare.py --top 8 --seconds 8 --fps 30 --keep-frames
Exit 0 only when the mp4 exists, decodes (ffprobe) and is at least 1 frame long.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# `--top N` must select the same models the published leaderboard ranks, so the
# family normaliser is imported from the leaderboard generator instead of being
# re-invented here. The renderer stays usable standalone: if that module cannot
# be imported (moved, renamed, dependency broken) we fall back to the same
# regex and say so out loud rather than silently ranking differently.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from leaderboard_check import norm_name as _norm_name  # noqa: E402
    _NORM_SRC = "scripts/leaderboard_check.py::norm_name"
except Exception as _exc:  # pragma: no cover - only on a broken checkout
    def _norm_name(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

    _NORM_SRC = f"local fallback ({_exc.__class__.__name__}: {_exc})"

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
 html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#07090f;}
 canvas{position:absolute;left:0;top:0;width:1920px;height:1080px;}
 .hud{position:absolute;left:0;top:0;width:1920px;height:1080px;
      font-family:'DejaVu Sans','Noto Sans',sans-serif;color:#e6edf3;}
 .title{position:absolute;left:64px;top:48px;font-size:64px;font-weight:800;letter-spacing:-1px;}
 .sub{position:absolute;left:64px;top:126px;font-size:26px;color:#8b949e;letter-spacing:1px;}
 .src{position:absolute;right:64px;top:56px;font-size:22px;color:#8b949e;text-align:right;line-height:1.5;}
 .label{position:absolute;transform:translate(-50%,-100%);text-align:center;opacity:0;
        transition:none;}
 .label .n{font-size:30px;font-weight:800;white-space:nowrap;}
 .label .s{font-size:40px;font-weight:900;margin-top:2px;}
 .label .q{font-size:20px;color:#8b949e;}
 .foot{position:absolute;left:64px;bottom:44px;font-size:22px;color:#6e7681;}
</style></head>
<body>
<canvas id="c" width="1920" height="1080"></canvas>
<div class="hud" id="hud">
  <div class="title">SLM GAUNTLET</div>
  <div class="sub">__SUB__</div>
  <div class="src">voxel comparison · __N__ models<br>height = weighted gauntlet score</div>
  <div class="foot">__FOOT__</div>
</div>
<script>
const MODELS = __MODELS__;
const DURATION = __DURATION__;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const hud = document.getElementById('hud');
const W = 1920, H = 1080;

const labels = MODELS.map(m => {
  const d = document.createElement('div');
  d.className = 'label';
  d.innerHTML = `<div class="n">${m.name}</div>`
              + `<div class="s" style="color:${m.color}">${m.score.toFixed(1)}%</div>`
              + `<div class="q">${m.quant}</div>`;
  hud.appendChild(d);
  return d;
});

function sub(a,b){return [a[0]-b[0],a[1]-b[1],a[2]-b[2]];}
function cross(a,b){return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];}
function norm(a){const l=Math.hypot(a[0],a[1],a[2])||1;return [a[0]/l,a[1]/l,a[2]/l];}
function dot(a,b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}

// ---- scene ----
const VS = 1.0;               // voxel edge in world units
const FLOOR = 9;              // floor grid radius
const SPACING = 5.0;          // tower spacing along x
const MAXH = 14;              // world height at 100%

function scoreHeight(p){ return Math.max(1.0, (p/100) * MAXH); }

function buildScene(t){
  const cubes = [];
  // floor: thin voxel slab grid
  for(let x=-FLOOR;x<=FLOOR;x++) for(let z=-FLOOR;z<=FLOOR;z++){
    const d = Math.hypot(x,z);
    if(d > FLOOR+0.35) continue;
    const shade = 0.62 + 0.16*((x+z)&1) + 0.10*(1-d/FLOOR);
    cubes.push({x:x*VS,y:-0.5,z:z*VS,kind:'floor',shade});
  }
  // towers
  const n = MODELS.length;
  MODELS.forEach((m, i) => {
    const cx = (i - (n-1)/2) * SPACING;
    const hgt = scoreHeight(m.score) * VS;
    const buildT = 0.12 + 0.42 * (i / Math.max(1,n-1));      // staggered build window
    const grow = Math.max(0, Math.min(1, (t - buildT) / 0.26));
    const visible = Math.ceil(grow * hgt);
    for(let y=0;y<visible;y++){
      // two-voxel footprint for mass, slight inward taper near the top
      const inset = y > hgt-2 ? 0.5*VS : 0;
      for(const dx of [-0.5*VS, 0.5*VS]) for(const dz of [-0.5*VS, 0.5*VS]){
        cubes.push({x:cx+dx,y:y*VS,z:dz+inset*0, kind:'tower', color:m.rgb, seed:(i*31+y*7)});
      }
    }
    m._top = [cx, hgt + 0.4, 0];
    m._grow = grow;
  });
  return cubes;
}

function faceShade(nrm, base, light){
  const k = Math.max(0, dot(norm(nrm), light));
  return [base[0]*(0.52+0.48*k), base[1]*(0.52+0.48*k), base[2]*(0.52+0.48*k)];
}
function rgb(a){return `rgb(${Math.min(255,a[0])|0},${Math.min(255,a[1])|0},${Math.min(255,a[2])|0})`;}

function camAt(t){
  const orbit = -0.30 + 0.085*t;   // narrow orbit: keeps the row legible
  const R = 30, CAMH = 12;
  const pos = [R*Math.sin(orbit), CAMH, R*Math.cos(orbit)];
  const target = [0, 7.5, 0];
  const fwd = norm(sub(target,pos));
  const right = norm(cross(fwd,[0,1,0]));
  const up = cross(right,fwd);
  return {pos,fwd,right,up,orbit};
}
// ORTHOGRAPHIC on purpose: a perspective divide makes a nearer tower look
// taller than an equal-height tower further away, which is a lying chart.
const PX_PER_UNIT = 46;

function projectWith(p, cam){
  const d = sub(p, cam.pos);
  const xc = dot(d, cam.right), yc = dot(d, cam.up), zc = dot(d, cam.fwd);
  if(zc <= 0.35) return null;
  return [W/2 + PX_PER_UNIT*xc, H/2 + 40 - PX_PER_UNIT*yc, zc];
}

function draw(t){
  ctx.fillStyle = '#07090f'; ctx.fillRect(0,0,W,H);
  // sky wash
  const g = ctx.createLinearGradient(0,0,0,H);
  g.addColorStop(0,'#0d1426'); g.addColorStop(0.62,'#080b13'); g.addColorStop(1,'#05070c');
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);

  const cam = camAt(t);
  const pos = cam.pos;
  const light = norm([0.35,0.9,0.42]);

  const cubes = buildScene(t);
  // painter's algorithm: far -> near
  for(const c of cubes) c._z = dot(sub([c.x,c.y,c.z],pos),cam.fwd);
  cubes.sort((a,b)=>b._z-a._z);

  const s = VS/2;
  for(const c of cubes){
    const base = c.kind==='floor'
      ? [54,62,86].map(v=>v*(c.shade||1))
      : c.color.map(v=>Math.min(255, v*1.18));
    // 6 faces, drawn only when front-facing
    const faces = [
      {n:[0,1,0], q:[[-s,s,-s],[s,s,-s],[s,s,s],[-s,s,s]]},
      {n:[0,-1,0],q:[[-s,-s,-s],[-s,-s,s],[s,-s,s],[s,-s,-s]]},
      {n:[0,0,1], q:[[-s,-s,s],[s,-s,s],[s,s,s],[-s,s,s]]},
      {n:[0,0,-1],q:[[s,-s,-s],[-s,-s,-s],[-s,s,-s],[s,s,-s]]},
      {n:[1,0,0], q:[[s,-s,s],[s,-s,-s],[s,s,-s],[s,s,s]]},
      {n:[-1,0,0],q:[[-s,-s,-s],[-s,-s,s],[-s,s,s],[-s,s,-s]]},
    ];
    for(const f of faces){
      const fc = [c.x+f.n[0]*s, c.y+f.n[1]*s, c.z+f.n[2]*s];
      if(dot(f.n, sub(pos,fc)) <= 0) continue;
      const pts = f.q.map(v => projectWith([c.x+v[0], c.y+v[1], c.z+v[2]], cam));
      if(pts.some(p=>!p)) continue;
      ctx.beginPath();
      ctx.moveTo(pts[0][0],pts[0][1]);
      for(let i=1;i<4;i++) ctx.lineTo(pts[i][0],pts[i][1]);
      ctx.closePath();
      const sh = faceShade(f.n, base, light);
      ctx.fillStyle = rgb(sh); ctx.fill();
      ctx.strokeStyle = rgb(sh.map(v=>v*0.86)); ctx.lineWidth = 0.6; ctx.stroke();
    }
  }

  // labels
  MODELS.forEach((m,i)=>{
    const p = projectWith(m._top, cam);
    const L = labels[i];
    if(p && m._grow > 0.98){
      L.style.left = p[0]+'px'; L.style.top = (p[1]-14)+'px';
      L.style.opacity = Math.min(1, (m._grow-0.98)*14 + Math.min(1, Math.max(0,(t-0.78))*3));
    } else {
      L.style.opacity = Math.min(1, Math.max(0, m._grow*0.0));
    }
  });
}

// Deterministic geometry self-check: proves the towers and their labels are
// inside the frame without a human looking at the picture.
//
// Label auto-fit + overlap proof. Tower pitch on screen is fixed by SPACING and
// PX_PER_UNIT (~220 px), so a wide model name ("MiniCPM-V 5 · 2B") runs into
// its neighbour at the default 30 px font. Names are measured and the name font
// is scaled down ONCE, uniformly, to the widest name that fits the pitch; then
// every label box is replayed across the whole tail of the animation (labels
// are only all-visible from t>=0.80) to prove zero overlaps and zero
// out-of-frame labels. No vision model required.
const LABEL_FONT = 30, LABEL_GAP = 16, LABEL_FROM = 0.80, LABEL_STEP = 0.02;

function labelBoxes(t){
  const cam = camAt(t);
  return MODELS.map((m, i) => {
    const p = projectWith(m._top, cam);
    const buildT = 0.12 + 0.42 * (i / Math.max(1, MODELS.length - 1));
    const grow = Math.max(0, Math.min(1, (t - buildT) / 0.26));
    if (!p || grow <= 0.98) return null;
    const w = labels[i].offsetWidth, h = labels[i].offsetHeight;
    return {id: m.id, i, l: p[0] - w/2, r: p[0] + w/2, tp: p[1] - 14 - h, bt: p[1] - 14};
  });
}

function labelPitch(){
  let min = Infinity;
  for(let t = LABEL_FROM; t <= DURATION + 1e-9; t += LABEL_STEP){
    const cam = camAt(t);
    const xs = MODELS.map(m => { const p = projectWith(m._top, cam); return p ? p[0] : null; });
    for(let i = 1; i < xs.length; i++){
      if(xs[i] === null || xs[i-1] === null) continue;
      min = Math.min(min, Math.abs(xs[i] - xs[i-1]));
    }
  }
  return isFinite(min) ? min : 220;
}

window.__fitlabels = function(){
  const names = labels.map(L => L.querySelector('.n'));
  names.forEach(n => { n.style.fontSize = LABEL_FONT + 'px'; });
  const widths = names.map(n => n.offsetWidth);
  const widest = Math.max(...widths);
  const allowed = Math.max(72, labelPitch() - LABEL_GAP);
  const scale = Math.min(1, allowed / widest);
  const px = Math.round(LABEL_FONT * scale * 10) / 10;
  names.forEach(n => { n.style.fontSize = px + 'px'; });
  return {name_font_px: px, widest_name_at_default: widest, allowed_px: Math.round(allowed),
          min_pitch_px: Math.round(labelPitch()), name_widths: widths};
};

window.__labelcheck = function(){
  const overlaps = [], outside = [];
  let samples = 0, minGap = Infinity;
  for(let t = LABEL_FROM; t <= DURATION + 1e-9; t += LABEL_STEP){
    samples++;
    const boxes = labelBoxes(t).filter(Boolean);
    for(const b of boxes){
      if(b.l < 20 || b.r > W - 20 || b.tp < 20) outside.push({t: +t.toFixed(2), id: b.id});
    }
    for(let i = 0; i < boxes.length; i++) for(let j = i+1; j < boxes.length; j++){
      const a = boxes[i], b = boxes[j];
      const ox = Math.min(a.r, b.r) - Math.max(a.l, b.l);
      const oy = Math.min(a.bt, b.bt) - Math.max(a.tp, b.tp);
      if(ox > 0 && oy > 0) overlaps.push({t: +t.toFixed(2), a: a.id, b: b.id, px: Math.round(Math.min(ox, oy))});
      else if(ox > 0) minGap = Math.min(minGap, -oy);
    }
  }
  return {samples, min_pitch_px: Math.round(labelPitch()),
          name_font_px: parseFloat(labels[0].querySelector('.n').style.fontSize),
          overlaps: overlaps.slice(0, 6), overlap_count: overlaps.length,
          out_of_frame: outside.slice(0, 6), out_of_frame_count: outside.length};
};

window.__selfcheck = function(){
  const t = DURATION, cam = camAt(t);
  const rows = MODELS.map(m => {
    const top = projectWith(m._top, cam);
    const base = projectWith([m._top[0], 0, 0], cam);
    return {
      id: m.id,
      top_y: top ? Math.round(top[1]) : null,
      base_y: base ? Math.round(base[1]) : null,
      x: top ? Math.round(top[0]) : null,
      screen_h: (top && base) ? Math.round(base[1]-top[1]) : null,
      in_frame: !!(top && base && top[1] > 150 && base[1] < 1045 && top[0] > 90 && top[0] < 1830),
    };
  });
  const ctx2 = document.getElementById('c').getContext('2d');
  const d = ctx2.getImageData(0,0,W,H).data;
  let ink = 0, total = 0;
  for(let i=0;i<d.length;i+=4*37){
    total++;
    if(d[i] > 32 || d[i+1] > 32 || d[i+2] > 46) ink++;
  }
  const xs = rows.map(r=>r.x).filter(v=>v!==null);
  const spread = xs.length ? Math.max(...xs) - Math.min(...xs) : 0;
  // the subtitle must name every tower it labels and must not run off the frame
  const subEl = document.querySelector('.sub');
  const subRect = subEl.getBoundingClientRect();
  const sub = {
    text: subEl.textContent,
    width: Math.round(subRect.width),
    in_frame: subRect.left >= 0 && subRect.right <= W - 40,
  };
  return {rows, spread_px: spread, ink_fraction: +(ink/total).toFixed(4),
          orbit: +cam.orbit.toFixed(3), sub};
};

window.__frame = function(t){ draw(Math.max(0, Math.min(DURATION, t))); };
draw(0);
</script></body></html>
"""


def card_entries() -> dict[str, dict]:
    """model id -> card entry, from the repo's own card corpus.

    Two card sources live in results/cards and BOTH are published leaderboard
    sources, so both count:

      * card_<config>.json  per-configuration cards (make_cards.py output; they
        carry details.quant and source_log provenance);
      * manifest.json       the 14 headline cards published for models that were
        carded before per-configuration JSONs were kept -- Gemma 4 E4B,
        MiniCPM-V 5 2B and 12 more, including the leaderboard's #2 and #3.

    scripts/leaderboard_check.py reads every *.json in that directory (see its
    card_files()), so skipping manifest.json here made the animation's "top N"
    disagree with the published table: the 2026-11-03 cut dropped #2 and #3.

    A per-configuration card always wins over a manifest row for the same model
    id, so a model present in both can never be counted twice or shadowed by a
    stale headline number. `_src` records the file each number came from.
    """
    out: dict[str, dict] = {}
    manifest = None
    for f in sorted(glob.glob("results/cards/*.json")):
        if f.endswith("manifest.json"):
            manifest = f
            continue
        for it in _card_items(f):
            mid = it["model"]
            prev = out.get(mid)
            if prev is None or str(it.get("ts", "")) >= str(prev.get("ts", "")):
                out[mid] = {**it, "_src": f}
    if manifest:
        for it in _card_items(manifest):
            if it["model"] not in out:      # per-config card is authoritative
                out[it["model"]] = {**it, "_src": manifest}
    return out


def _card_items(path: str) -> list[dict]:
    try:
        data = json.load(open(path))
    except Exception:
        return []
    items = data if isinstance(data, list) else [data]
    return [it for it in items if isinstance(it, dict) and it.get("model")]


def family_of(entry: dict) -> str:
    """One tower per model family, normalised exactly like the published
    leaderboard (scripts/leaderboard_check.py::family_of), so `--top N` selects
    the published leaderboard's top N and not a second quantization of a model
    that is already on the podium."""
    return _norm_name(entry.get("display_name") or entry.get("model", ""))


def comparable_n(ents: dict[str, dict]) -> int:
    """Task count of the current methodology (mode of the corpus). Rows that ran
    fewer tasks -- e.g. the 65-task Bonsai-2 row -- stay in the corpus for
    provenance but are never ranked against full-count rows, which is the rule
    the published table states in its "legacy rows" section."""
    counts: dict[int, int] = {}
    for e in ents.values():
        n = e.get("n")
        if isinstance(n, int):
            counts[n] = counts.get(n, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else 0


def top_models(n: int) -> list[str]:
    ents = card_entries()
    full = comparable_n(ents)
    ranked = sorted((e for e in ents.values() if not full or e.get("n") == full),
                    key=lambda e: -float(e.get("overall_pct") or 0))
    seen, picked = set(), []
    for e in ranked:
        fam = family_of(e)
        if fam in seen:      # one configuration per model, like the leaderboard
            continue
        seen.add(fam)
        picked.append(e["model"])
        if len(picked) >= n:
            break
    return picked


PALETTE = [
    (255, 196, 61), (86, 196, 255), (124, 220, 140), (206, 140, 255),
    (255, 122, 122), (120, 230, 220), (255, 170, 90), (170, 190, 255),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated card ids")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--seconds", type=float, default=7.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--outdir", default="results/_published/voxel_compare")
    ap.add_argument("--keep-frames", action="store_true")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("ffmpeg missing", file=sys.stderr)
        return 2

    ents = card_entries()
    ids = [s.strip() for s in a.models.split(",")] if a.models else top_models(a.top)
    models = []
    for i, mid in enumerate(ids):
        e = ents.get(mid)
        if not e:
            print(f"unknown card id: {mid}", file=sys.stderr)
            return 2
        det = e.get("details") or {}
        models.append({
            "id": mid,
            "name": e.get("display_name") or mid,
            "score": float(e["overall_pct"]),
            "quant": det.get("quant") or (e.get("sub", "").split("·")[0].strip()),
            "rgb": list(PALETTE[i % len(PALETTE)]),
            "color": "#{:02x}{:02x}{:02x}".format(*PALETTE[i % len(PALETTE)]),
            "n": e.get("n"),
        })

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    frames = outdir / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()

    if a.models:
        slug = "voxel_compare_" + "_".join(m["id"].split("-")[0] for m in models[:3])
    else:
        import datetime as _dt
        slug = f"voxel_top{len(models)}_{_dt.date.today():%Y%m%d}"
    sub = " · ".join(f"{m['name']} {m['quant']}" for m in models)

    # selection receipt: every rendered tower names the JSON its number came
    # from, so a published frame can be traced without re-deriving anything.
    print(f"selection ({'explicit --models' if a.models else f'--top {a.top}'}, "
          f"family rule {_NORM_SRC}):")
    for i, m in enumerate(models, 1):
        print(f"  #{i} {m['score']:5.1f}  n={m['n']}  {m['name']} / {m['quant']}"
              f"  <- {ents[m['id']].get('_src')}")

    foot = "measured on GTX 1070 Ti 8GB · scores from results/cards · seed 1 · temp 0"
    html = (HTML
            .replace("__MODELS__", json.dumps(models))
            .replace("__DURATION__", repr(a.seconds))
            .replace("__SUB__", sub)
            .replace("__N__", str(len(models)))
            .replace("__FOOT__", foot))
    html_path = outdir / f"{slug}.html"
    html_path.write_text(html)

    # read the payload back out of the file on disk: what the browser will
    # render has to be the selection that was just printed, not a hope.
    written = html_path.read_text()
    m_models = re.search(r"const MODELS = (\[.*?\]);\n", written, re.S)
    m_sub = re.search(r'<div class="sub">(.*?)</div>', written, re.S)
    rendered = json.loads(m_models.group(1)) if m_models else []
    rendered_sub = m_sub.group(1) if m_sub else ""
    if ([r["id"] for r in rendered] != ids
            or [r["score"] for r in rendered] != [m["score"] for m in models]):
        print(f"HTML READ-BACK MISMATCH: wrote {[r['id'] for r in rendered]} / "
              f"{[r['score'] for r in rendered]}, selected {ids} / "
              f"{[m['score'] for m in models]}", file=sys.stderr)
        return 1
    print(f"html read-back ok: {len(rendered)} models, subtitle {len(rendered_sub)} chars")

    from playwright.sync_api import sync_playwright

    n_frames = int(round(a.seconds * a.fps))
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--headless=new", "--no-sandbox", "--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        pg.goto(html_path.resolve().as_uri(), wait_until="load")
        pg.wait_for_timeout(150)
        # fit the tower labels once, before any frame is captured, then prove no
        # label touches its neighbour anywhere in the tail of the animation
        pg.evaluate("t => window.__frame(t)", a.seconds)
        fit = pg.evaluate("() => window.__fitlabels()")
        lcheck = pg.evaluate("() => window.__labelcheck()")
        print("labelfit:", json.dumps(fit))
        print("labelcheck:", json.dumps(lcheck))
        if lcheck["overlap_count"] or lcheck["out_of_frame_count"]:
            print(f"BAD LABELS: {lcheck['overlap_count']} overlapping pairs, "
                  f"{lcheck['out_of_frame_count']} out-of-frame label samples",
                  file=sys.stderr)
            b.close()
            return 1
        for i in range(n_frames):
            t = i / a.fps
            pg.evaluate("t => window.__frame(t)", t)
            pg.screenshot(path=str(frames / f"f_{i:04d}.png"))
        pg.evaluate("t => window.__frame(t)", a.seconds)
        check = pg.evaluate("() => window.__selfcheck()")
        poster = outdir / f"{slug}.png"
        pg.screenshot(path=str(poster))
        b.close()

    # a frame nobody can read is a failed render: geometry + ink must be sane
    frame_ok = all(r["in_frame"] and r["screen_h"] >= 120 for r in check["rows"]) and check["spread_px"] >= 450
    ink = check["ink_fraction"]
    ink_ok = 0.08 <= ink <= 0.65
    # and the subtitle the viewer reads must name every tower, in frame
    sub_live = check.get("sub") or {}
    sub_text = sub_live.get("text") or ""
    sub_missing = [f"{m['name']} {m['quant']}" for m in models if f"{m['name']} {m['quant']}" not in sub_text]
    sub_ok = bool(sub_live.get("in_frame")) and not sub_missing
    print("selfcheck:", json.dumps(check))
    if not (frame_ok and ink_ok and sub_ok):
        print(f"BAD FRAME: in_frame+spread={frame_ok} ink_fraction={ink} (want 0.08-0.65) "
              f"subtitle_in_frame={sub_live.get('in_frame')} subtitle_width={sub_live.get('width')} "
              f"subtitle_missing={sub_missing}", file=sys.stderr)
        return 1

    mp4 = outdir / f"{slug}.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-framerate", str(a.fps), "-i", str(frames / "f_%04d.png"),
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:], file=sys.stderr)
        return 1

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate,duration",
         "-of", "json", str(mp4)], capture_output=True, text=True)
    info = json.loads(probe.stdout or "{}")
    st = (info.get("streams") or [{}])[0]
    ok = int(st.get("nb_read_frames") or 0) == n_frames and mp4.stat().st_size > 50000
    print(json.dumps({
        "mp4": str(mp4), "poster": str(poster), "html": str(html_path),
        "frames": n_frames, "decoded_frames": st.get("nb_read_frames"),
        "size": st.get("width"), "height": st.get("height"),
        "fps": st.get("r_frame_rate"), "bytes": mp4.stat().st_size,
        "models": [{"id": m["id"], "name": m["name"], "quant": m["quant"],
                    "score": m["score"], "n": m["n"],
                    "src": ents[m["id"]].get("_src")} for m in models],
        "subtitle": sub_live.get("text"),
        "labelfit": fit, "labelcheck": {k: lcheck[k] for k in
                                        ("overlap_count", "out_of_frame_count",
                                         "min_pitch_px", "name_font_px")},
        "ok": ok,
    }, indent=1, ensure_ascii=False))
    if not a.keep_frames:
        shutil.rmtree(frames)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
