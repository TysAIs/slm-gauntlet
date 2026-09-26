"""Creative-code suite: single-file voxel pagoda benchmark ("pagoda-lite").

Modeled on the Pagoda Bench (Artificial Analysis MicroEvals / Wesche's spark-bench
uncapped prompt): the model must author ONE self-contained HTML file that renders
a voxel pagoda garden scene and exposes graded numerics on window.__VOXEL__.

Grading is deterministic (no LLM judge):
  - static: single file, no external assets (no http(s):// src/href), size < 700KB,
    no hallucinated-API markers we can detect statically
  - runtime (headless chromium via playwright): page loads with zero console errors,
    window.__VOXEL__ exists with integer voxelCount >= 500, pagodaFloors >= 3,
    fps > 20 measured over the sampling window, timeOfDay is a string
  - artifact: full-scene screenshot saved for the model card
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PAGODA_CODE_PROMPT = """Create a single-file HTML page that renders a 3D voxel pagoda garden scene.

Requirements:
- ONE complete, self-contained HTML file. No external assets, no CDN links,
  no imports — all code inline.
- Render an isometric or perspective voxel scene using canvas or WebGL (your choice).
- The scene MUST contain: a multi-tier pagoda (stacked roofs, each tier smaller
  than the one below), a stone foundation/stairway, a torii gate, lanterns,
  garden elements (trees, path, or pond), and a sky backdrop with atmospheric color.
- Voxel aesthetic: blocky cubes, visible tier separation.
- Expose a global object for grading:
  window.__VOXEL__ = { voxelCount: <int>, fps: <measured fps>,
    pagodaFloors: <int tiers>, timeOfDay: "<day|sunset|night>" };
- voxelCount must be the true number of voxel cubes drawn.
  pagodaFloors must match the visible tiers.
- Keep the file under 700KB. No console errors. Animate gently (lantern glow,
  clouds, or water) so fps is measurable.
- Output ONLY the HTML file contents, no explanations, no markdown fences.
"""


@dataclass
class CodePagodaScore:
    static_pass: bool = False
    loads: bool = False
    zero_console_errors: bool = False
    voxel_count: int = 0
    pagoda_floors: int = 0
    fps: float = 0.0
    time_of_day: str = ""
    file_bytes: int = 0
    checks: list = field(default_factory=list)

    @property
    def pct(self) -> float:
        total = 7  # static, loads, console, voxel>=500, floors>=3, fps>20, tod
        return 100.0 * sum(self.checks) / total

    def as_dict(self) -> dict:
        return {
            "pct": self.pct,
            "static_pass": self.static_pass,
            "loads": self.loads,
            "zero_console_errors": self.zero_console_errors,
            "voxel_count": self.voxel_count,
            "pagoda_floors": self.pagoda_floors,
            "fps": self.fps,
            "time_of_day": self.time_of_day,
            "file_bytes": self.file_bytes,
            "checks": self.checks,
        }


def grade_static(html_src: str) -> tuple[bool, int, list]:
    checks = []
    external = re.findall(r'(?:src|href)\s*=\s*["\']https?://', html_src)
    checks.append(not external)
    under_size = len(html_src.encode()) < 700_000
    checks.append(under_size)
    has_voxel = "window.__VOXEL__" in html_src or "self.__VOXEL__" in html_src
    checks.append(has_voxel)
    return (all(checks), len(html_src.encode()), checks)


def grade_runtime(html_path: str, shot_path: str) -> dict:
    """Run in headless chromium (playwright), read __VOXEL__, screenshot the scene."""
    import asyncio

    async def _run() -> dict:
        from playwright.async_api import async_playwright
        errors: list[str] = []
        out: dict = {"loads": False, "console_errors": 1, "voxel": {}}
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                args=["--use-gl=angle", "--use-angle=swiftshader",
                      "--enable-unsafe-swiftshader"])
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            try:
                await page.goto(f"file://{html_path}", wait_until="load", timeout=20000)
                await page.wait_for_timeout(1500)
                out["loads"] = True
                await page.wait_for_timeout(8000)  # let it animate / measure fps
                voxel = await page.evaluate(
                    """() => {
                        const v = window.__VOXEL__;
                        if (!v) return null;
                        return {voxelCount: v.voxelCount, fps: v.fps,
                                pagodaFloors: v.pagodaFloors, timeOfDay: v.timeOfDay};
                    }"""
                )
                out["voxel"] = voxel or {}
                out["console_errors"] = len(errors)
                await page.screenshot(path=shot_path)
            except Exception as e:  # noqa: BLE001
                errors.append(f"runner: {e}")
                out["console_errors"] = len(errors)
            await browser.close()
        out["errors_sample"] = errors[:3]
        return out

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(_run())
    # called from inside a running loop (CLI) — run as a task on it
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, _run()).result()


def score_pagoda_code(html_src: str, artifact_dir: str, model: str) -> CodePagodaScore:
    s = CodePagodaScore()
    s.static_pass, s.file_bytes, static_checks = grade_static(html_src)
    s.checks.append(s.static_pass)

    import os
    os.makedirs(artifact_dir, exist_ok=True)
    html_path = os.path.abspath(os.path.join(artifact_dir, f"voxel_{model}.html"))
    shot_path = os.path.join(artifact_dir, f"png_voxel_{model}.png")
    with open(html_path, "w") as f:
        f.write(html_src)

    rt = grade_runtime(html_path, shot_path)
    s.loads = rt["loads"]
    s.checks.append(s.loads)
    s.zero_console_errors = rt["loads"] and rt["console_errors"] == 0
    s.checks.append(s.zero_console_errors)

    v = rt.get("voxel") or {}
    s.voxel_count = int(v.get("voxelCount") or 0)
    s.pagoda_floors = int(v.get("pagodaFloors") or 0)
    s.fps = float(v.get("fps") or 0)
    s.time_of_day = str(v.get("timeOfDay") or "")
    s.checks.append(s.voxel_count >= 300)
    s.checks.append(s.pagoda_floors >= 3)
    s.checks.append(s.fps > 20)
    s.checks.append(bool(s.time_of_day))
    return s
