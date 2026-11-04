#!/usr/bin/env python3
"""VOXEL comparison animation: 3D voxel towers built from real gauntlet scores.

Output is a deterministic 1920x1080 H.264 MP4 (plus poster PNG and the source
HTML) intended for X/socials: model towers rise out of a voxel floor while the
camera orbits, then hold with labels. No GPU, no network, no blender/manim:
canvas-2D software renderer + playwright frame capture + ffmpeg mux.

Determinism comes from window.__frame(t): every screenshot sets the animation
clock explicitly, so the same input bytes always produce the same frames.

Data comes from the card JSONs that make_cards.py/gen-leaderboard.py already
produce (results/cards/*.json), so the animation can never drift from the
leaderboard numbers.

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
import shutil
import subprocess
import sys
from pathlib import Path

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
  d.innerHTML = `<div class="n">${m.name}</div><div class="s" style="color:${m.color}">${m.score.toFixed(1)}%</div><div class="q">${m.quant}</div>`;
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
  return {rows, spread_px: spread, ink_fraction: +(ink/total).toFixed(4), orbit: +cam.orbit.toFixed(3)};
};

window.__frame = function(t){ draw(Math.max(0, Math.min(DURATION, t))); };
draw(0);
</script></body></html>
"""


def card_entries() -> dict[str, dict]:
    """model id -> card entry, from the repo's own card JSONs (newest wins)."""
    out: dict[str, dict] = {}
    for f in sorted(glob.glob("results/cards/*.json")):
        if f.endswith("manifest.json"):
            continue
        try:
            data = json.load(open(f))
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            mid = it.get("model")
            if not mid:
                continue
            prev = out.get(mid)
            if prev is None or str(it.get("ts", "")) >= str(prev.get("ts", "")):
                out[mid] = it
    return out


def top_models(n: int) -> list[str]:
    ents = card_entries()
    ranked = sorted(ents.values(), key=lambda e: -float(e.get("overall_pct") or 0))
    seen, picked = set(), []
    for e in ranked:
        base = e["model"].split("-q")[0].split("-iq")[0].split("-ud")[0]
        if base in seen:      # one quant per model family, like the leaderboard headline
            continue
        seen.add(base)
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
            "color": "#%02x%02x%02x" % PALETTE[i % len(PALETTE)],
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
    sub = " · ".join(f"{m['name']} {m['quant']}" for m in models[:4])
    foot = f"measured on GTX 1070 Ti 8GB · scores from results/cards · seed 1 · temp 0"
    html = (HTML
            .replace("__MODELS__", json.dumps(models))
            .replace("__DURATION__", repr(a.seconds))
            .replace("__SUB__", sub)
            .replace("__N__", str(len(models)))
            .replace("__FOOT__", foot))
    html_path = outdir / f"{slug}.html"
    html_path.write_text(html)

    from playwright.sync_api import sync_playwright

    n_frames = int(round(a.seconds * a.fps))
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--headless=new", "--no-sandbox", "--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        pg.goto(html_path.resolve().as_uri(), wait_until="load")
        pg.wait_for_timeout(150)
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
    print("selfcheck:", json.dumps(check))
    if not (frame_ok and ink_ok):
        print(f"BAD FRAME: in_frame+spread={frame_ok} ink_fraction={ink} (want 0.08-0.65)",
              file=sys.stderr)
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
        "models": [{"id": m["id"], "score": m["score"]} for m in models],
        "ok": ok,
    }, indent=1))
    if not a.keep_frames:
        shutil.rmtree(frames)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
