#!/usr/bin/env python3
"""Verify every SCOREBOARD.md board against the artifact it claims to come from.

WHY THIS EXISTS
---------------
SCOREBOARD.md is written by hand. Twice now a headline cell was typed from one
run while its card — and the board's own matrix — pointed at another: the T1 row
carried Gemma 4 E4B 90.0 (an earlier, duplicate 32K session) against a card of
90.2, and Ornith-1.5-9B 82.8 against a card of 83.1. No run was wrong; the board
was quoting a different session for two models. That class of drift is invisible
to review but mechanical to detect, so this script re-derives each cell from its
source and fails on any disagreement.

WHAT IT CHECKS
--------------
  T1 screen        -> results/cards/*.json (canonical 32K, KV q8_0 card per model)
  Phase M matrix   -> results/cards/*.json (each KV-precision cell)
  L2 (65,536 ctx)  -> results/<model>-l2-kv<f16|q8|q4>_<ts>.json, re-scored
  L3 long-horizon  -> extra-suites/longhorizon-v2/results_*-l3-v2r.json
  Variance         -> canonical card (seed 1) + results/<model>-s23_<ts>.json
  OCR board        -> extra-suites/ocr/results_*.json

  The extended matrix is NOT re-derived: its 209 cells are sweep-best
  configurations whose per-cell artifacts do not ship as cards. That is the one
  named exception, printed on every run so it cannot be mistaken for a pass.

USAGE
  .venv/bin/python scripts/scoreboard_check.py            # verify, exit 1 on drift
  .venv/bin/python scripts/scoreboard_check.py --verbose  # print every cell
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from leaderboard_check import score_log  # noqa: E402  (single definition of the aggregate)

BOARD = ROOT / "SCOREBOARD.md"
CARDS = ROOT / "results" / "cards"
L2_LOGS = ROOT / "results"
L3_DIR = ROOT / "extra-suites" / "longhorizon-v2"
OCR_DIR = ROOT / "extra-suites" / "ocr"

# Hand-authored names that differ from the card's display_name (norm() form).
ALIASES = {
    "sharp spark x2.6 4b": "sharp spark 4b",
}

# L2 rows name a configuration, not a card; the run log is the instrument.
L2_SOURCES_RAW = {
    ("Bolt E4B", "UD-Q8_K_XL"): "bolt-e4b-udq8kxl",
    ("Gemma 4 12B", "IQ3_XXS"): "gemma4-12b-iq3xxs",
    ("Gemma 4 E2B", "Q4_0"): "gemma4-e2b-q4_0",
    ("Gemma 4 E4B", "Q4_K_M"): "gemma4-e4b-q4km",
    ("MiMo-V2.6-9B", "Q4_K_M"): "mimo-v2.6-9b-q4km",
    ("MiniCPM5-2B", "Q4_K_M"): "minicpm5-2b-q4km",
    ("Ministral 3 8B", "Q4_K_M"): "ministral3-8b-q4km",
    ("Ornith-1.5-9B", "Q4_K_M"): "ornith-1.5-9b-q4km",
    ("Qwen3.5-4B", "Q4_K_M"): "qwen3.5-4b-q4km",
    ("Qwen3.5-9B", "Q4_K_M"): "qwen3.5-9b-q4km",
    ("Spark-X2.6-4B", "Q8_0"): "spark-x2.6-4b-q8",
}

L3_SOURCES_RAW = {
    "MiniCPM5-2B": "results_minicpm5-2b-q4km-l3-v2r.json",
    "Qwen3.5-9B": "results_qwen3.5-9b-q4km-l3-v2r.json",
    "MiMo-V2.6-9B": "results_mimo-v2.6-9b-q4km-l3-v2r.json",
    "Qwen3.5-4B": "results_qwen3.5-4b-q4km-l3-v2r.json",
    "Ornith-1.5-9B": "results_ornith-1.5-9b-q4km-l3-v2r.json",
    "Gemma 4 12B": "results_gemma4-12b-iq3xxs-l3-v2r.json",
    "Spark-X2.6-4B": "results_spark-x2.6-4b-iq3m-l3-v2r.json",
    "Gemma 4 E2B": "results_gemma4-e2b-q4_0-l3-v2r.json",
    "Gemma 4 E4B": "results_gemma4-e4b-q4km-l3-v2r.json",
}

OCR_SOURCES_RAW = {
    "MiniCPM-V 4.7 1B": "results_minicpmv47-1b-q4km-mmproj.json",
    "LFM3-VL-2B": "results_lfm3-vl-2b-q4km-mmproj.json",
    "MiniCPM-OCR 1.0": "results_minicpm-ocr-1.0-q4km-mmproj.json",
}

KV_COLUMNS = ["FP16", "q8_0", "q4_0"]
KV_LOGS = {"FP16": "kvf16", "q8_0": "kvq8", "q4_0": "kvq4"}

TOL = 0.05  # percentage points; cells are published to one decimal


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", str(s).strip().lower()).strip()


def flat(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def display_key(name: str) -> str:
    return norm(name)


def alias(name: str) -> str:
    k = norm(name)
    return ALIASES.get(k, k)


def _keyed(raw: dict) -> dict:
    if raw and isinstance(next(iter(raw)), tuple):
        return {(alias(k), norm(q)): v for (k, q), v in raw.items()}
    return {alias(k): v for k, v in raw.items()}


L2_SOURCES = _keyed(L2_SOURCES_RAW)
L3_SOURCES = {alias(k): v for k, v in L3_SOURCES_RAW.items()}
OCR_SOURCES = {alias(k): v for k, v in OCR_SOURCES_RAW.items()}

HEADER_CELLS = {
    "model", "cell", "quant", "score", "license", "#", "model quant",
    "kv f16", "kv q8_0", "kv q4_0", "seed 1", "seed 2", "seed 3", "mean",
    "spread", "passed", "field score", "best cell", "cells",
}


class Checker:
    def __init__(self, verbose: bool = False) -> None:
        self.failures: list[str] = []
        self.unverifiable: list[str] = []
        self.checked = 0
        self.verbose = verbose
        self.cards = self._load_cards()

    # -- corpus -------------------------------------------------------------
    def _load_cards(self):
        by_cell: dict[tuple[str, str, str], dict] = {}
        for p in sorted(CARDS.glob("card_*.json")):
            try:
                doc = json.loads(p.read_text())
            except Exception:
                continue
            arr = doc if isinstance(doc, list) else [doc]
            for c in arr:
                det = c.get("details") or {}
                if c.get("overall_pct") is None:
                    continue
                key = (alias(c.get("display_name", "")), norm(det.get("quant", "")), det.get("kv_type", ""))
                rank = (int(c.get("n") or 0), str(det.get("methodology") or ""), str(c.get("ts") or ""))
                prev = by_cell.get(key)
                # Prefer the current battery (320 tasks), then the newest epoch and card.
                if prev is None or rank > prev["rank"]:
                    by_cell[key] = {"card": c, "path": str(p.relative_to(ROOT)), "rank": rank}
        return by_cell

    def lookup(self, model: str, quant: str, kv: str) -> dict | None:
        key = (alias(model), norm(quant), kv)
        hit = self.cards.get(key)
        if hit is None:
            return None
        card = hit["card"]
        det = card.get("details") or {}
        return {
            "value": round(float(card["overall_pct"]), 2),
            "source": det.get("run_log", hit["path"]),
            "card": hit["path"],
        }

    def compare(self, board: str, label: str, published: float | None, found: dict | None) -> None:
        self.checked += 1
        if published is None:
            self.failures.append(f"{board}: {label} — unparseable published score")
            return
        if found is None:
            self.failures.append(f"{board}: {label} — no source artifact found")
            return
        if abs(published - found["value"]) > TOL:
            self.failures.append(
                f"{board}: {label} — SCOREBOARD says {published}, source says {found['value']:.2f} ({found['source']})"
            )
        elif self.verbose:
            print(f"  ok  {board}: {label} {published} == {found['value']:.2f}")

    def skip(self, board: str, label: str, why: str) -> None:
        if self.verbose:
            print(f"  --  {board}: {label} skipped ({why})")

    # -- parsing ------------------------------------------------------------
    @staticmethod
    def sections() -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        current = ""
        for line in BOARD.read_text().splitlines():
            if line.startswith("## "):
                current = norm(line[3:])
                out[current] = []
            elif current:
                out[current].append(line)
        return out

    @staticmethod
    def rows(lines: list[str]):
        for line in lines:
            if line.startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if not cells:
                    continue
                if set(cells[0]) <= {"-", ":"}:
                    continue
                if norm(cells[0]) in HEADER_CELLS or norm(cells[0]) == "":
                    continue
                yield cells

    @staticmethod
    def num(cell: str) -> float | None:
        m = re.search(r"(\d+(?:\.\d+)?)", cell.replace("**", ""))
        return float(m.group(1)) if m else None

    # -- boards -------------------------------------------------------------
    def t1(self, lines):
        for cells in self.rows(lines):
            if len(cells) < 5:
                continue
            model = re.sub(r"\s*†\s*$", "", cells[1])
            score = self.num(cells[3])
            if score is None:
                continue
            self.compare("T1 screen", f"{model} {cells[2]}", score, self.lookup(model, cells[2], "q8_0"))

    def phase_m(self, lines):
        for cells in self.rows(lines):
            if len(cells) != 4:
                continue
            label = cells[0]
            for idx, kv in enumerate(KV_COLUMNS, start=1):
                if "does-not-fit" in cells[idx]:
                    continue
                score = self.num(cells[idx])
                if score is None:
                    continue
                model, quant = self._split_model_quant(label)
                self.compare("Phase M", f"{label} {kv}", score, self.lookup(model, quant, kv))

    def _split_model_quant(self, label: str) -> tuple[str, str]:
        best = (label, "")
        for key in self.cards:
            disp = key[0]
            if norm(label).startswith(disp) and len(disp) > len(norm(best[0])):
                best = (label[: len(disp)], label[len(disp):].strip())
        if best[1]:
            return best[0], best[1]
        parts = label.rsplit(" ", 1)
        return (parts[0], parts[1]) if len(parts) == 2 else (label, "")

    def l2(self, lines):
        if not any(L2_LOGS.glob("*-l2-kv*.json")):
            self.unverifiable.append("L2 (raw l2 run logs are not part of the publish surface)")
            return
        for cells in self.rows(lines):
            if len(cells) != 5:
                continue
            model, quant = cells[0], cells[1]
            base = L2_SOURCES.get((alias(model), norm(quant)))
            if base is None:
                self.failures.append(f"L2: {model} {quant} — no source mapping for this row")
                continue
            for idx, kv in enumerate(KV_COLUMNS, start=2):
                if "does-not-fit" in cells[idx]:
                    continue
                score = self.num(cells[idx])
                if score is None:
                    continue
                pattern = str(L2_LOGS / f"{base}-l2-{KV_LOGS[kv]}_*.json")
                paths = sorted(glob.glob(pattern))
                if not paths:
                    self.failures.append(f"L2: {model} {quant} {kv} — no run log at {pattern}")
                    continue
                log = paths[-1]
                found = {"value": round(float(score_log(log)["overall"]), 2),
                         "source": str(Path(log).relative_to(ROOT))}
                self.compare("L2", f"{model} {quant} {kv}", score, found)

    def l3(self, lines):
        for cells in self.rows(lines):
            if len(cells) < 5:
                continue
            model = cells[1]
            passed_txt = cells[2]
            score = self.num(cells[3])
            src = L3_SOURCES.get(norm(model))
            if src is None:
                self.skip("L3", model, "no source mapping (excluded by design)")
                continue
            path = L3_DIR / src
            if not path.exists():
                self.failures.append(f"L3: {model} — missing artifact {path.name}")
                continue
            doc = json.loads(path.read_text())
            rows = doc.get("rows") or []
            passed = sum(1 for r in rows if float(r.get("score") or 0) >= 1.0)
            total = int(doc.get("n_tasks") or len(rows))
            found = {"value": round(float(doc.get("overall_score")), 2), "source": str(path.relative_to(ROOT))}
            self.compare("L3", f"{model} score", score, found)
            self.checked += 1
            m = re.match(r"(\d+)\s*/\s*(\d+)", passed_txt.replace("**", ""))
            if not m:
                self.failures.append(f"L3: {model} — unparseable pass count {passed_txt!r}")
            elif (int(m.group(1)), int(m.group(2))) != (passed, total):
                self.failures.append(
                    f"L3: {model} — SCOREBOARD says {passed_txt}, artifact says {passed}/{total} ({path.name})"
                )

    def variance(self, lines):
        if not any(L2_LOGS.glob("*-s23_*.json")):
            self.unverifiable.append("Variance (seed-2/3 run logs are not part of the publish surface)")
            return
        for cells in self.rows(lines):
            if len(cells) != 6:
                continue
            model, quant = self._split_model_quant(cells[0])
            seeds = [self.num(c) for c in cells[1:4]]
            mean, spread = self.num(cells[4]), self.num(cells[5])
            if any(s is None for s in seeds) or mean is None:
                continue
            seeds_f = [s for s in seeds if s is not None]
            card = self.lookup(model, quant, "q8_0")
            if card is None:
                self.failures.append(f"Variance: {cells[0]} — no canonical card")
                continue
            base = card["source"].split("/")[-1].split("_")[0].replace("-kvq8", "")
            got = [round(card["value"], 1)]
            for seed in (2, 3):
                paths = sorted(glob.glob(str(L2_LOGS / f"{base}-s23_*.json")))
                hit = None
                for p in paths:
                    meta = json.loads(Path(p).read_text()).get("meta") or {}
                    if meta.get("seed") == seed:
                        hit = p
                if hit is None:
                    self.failures.append(f"Variance: {cells[0]} — no seed-{seed} log under {base}-s23_*")
                    got = None
                    break
                got.append(round(float(score_log(hit)["overall"]), 1))
            if got is None:
                continue
            for i, (pub, g) in enumerate(zip(seeds_f, got, strict=False)):
                self.checked += 1
                if abs(pub - g) > TOL:
                    self.failures.append(
                        f"Variance: {cells[0]} seed {i + 1} — SCOREBOARD says {pub}, artifact says {g}"
                    )
            self.checked += 2
            calc_mean = round(sum(got) / len(got), 1)
            calc_spread = round(max(got) - min(got), 1)
            if abs(mean - calc_mean) > TOL:
                self.failures.append(f"Variance: {cells[0]} mean — SCOREBOARD says {mean}, artifacts give {calc_mean}")
            if spread is not None and abs(spread - calc_spread) > TOL:
                self.failures.append(
                    f"Variance: {cells[0]} spread — SCOREBOARD says {spread}, artifacts give {calc_spread}"
                )

    def ocr(self, lines):
        for cells in self.rows(lines):
            if len(cells) < 3:
                continue
            model = cells[0]
            score = self.num(cells[1])
            src = OCR_SOURCES.get(norm(model))
            if src is None:
                self.failures.append(f"OCR: {model} — no source mapping")
                continue
            path = OCR_DIR / src
            if not path.exists():
                self.failures.append(f"OCR: {model} — missing artifact {src}")
                continue
            doc = json.loads(path.read_text())
            found = {"value": round(float(doc.get("overall_field_score")), 2), "source": str(path.relative_to(ROOT))}
            self.compare("OCR", model, score, found)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if not BOARD.exists():
        print("scoreboard_check: SCOREBOARD.md not found", file=sys.stderr)
        return 1

    chk = Checker(verbose=args.verbose)
    sec = chk.sections()

    def section(prefix: str):
        for name, lines in sec.items():
            if name.startswith(prefix):
                return lines
        return []

    chk.t1(section("t1 screen"))
    chk.phase_m(section("phase m matrix"))
    chk.l2(section("l2"))
    chk.l3(section("l3"))
    chk.variance(section("variance"))
    chk.ocr(section("ocr board"))

    print("== scoreboard check ==")
    print(f"cells verified: {chk.checked}")
    print("named exception: extended matrix (209 sweep-best cells; per-cell artifacts do not ship as cards)")
    for item in chk.unverifiable:
        print(f"not verifiable here: {item}")
    if chk.failures:
        print(f"DISAGREEMENTS ({len(chk.failures)}):")
        for f in chk.failures:
            print(f"  - {f}")
        return 1
    print("SCOREBOARD.md agrees with its instruments on every verified cell.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
