#!/usr/bin/env python3
"""Regenerate and verify the published SLM-gauntlet leaderboard from the card corpus.

WHY THIS EXISTS
---------------
The README table and the card corpus used to be produced by hand, and they drifted:

  * the README table's headline numbers were a *equal-suite mean* of the seven
    suite percentages (see the "weights" string in
    results/_published/leaderboard.json) while every model card, the detailed
    LEADERBOARD.md and `gauntlet run` itself use the CLI weighted aggregate
    (SUITE_WEIGHTS in gauntlet/cli.py). Same suites, different aggregation ->
    a different number for the same run, which is not a measurement difference;
  * that table omitted the whole 218-configuration variant sweep, so it called
    Gemma 4 E4B (87.9% equal-weight) the winner while the corpus contains
    Spark-X2.6 4B IQ3_M at 91.5% on the same task set;
  * one row (Ternary Bonsai-2, 65 tasks) sat under a "71 tasks" header and was
    therefore ranked against models it never ran the same suite against.

This script is now the only producer of that table. It reads results/cards/*.json,
recomputes every score from the run log the card came from using the documented
aggregate, ranks the corpus, writes the README block between the GENERATED
markers, and exits non-zero whenever the committed README (or results/_published/
leaderboard.json) disagrees with the corpus.

METHODOLOGY (single definition, used for every row)
--------------------------------------------------
  score = sum(suite_weight[s] * mean(task pass1 in s)) / sum(suite_weight[s] present)
  suite_weight = gauntlet/cli.py SUITE_WEIGHTS (tool .30, structured .15,
                 retrieval .15, coding .10, instruction .10, adversarial .10,
                 agent_chains .10) -- the figure `gauntlet run` reports.
  task pass1 is the BINARY pass rate (all asserts passed, run terminated
                cleanly), as recorded per task in the run log. It is NOT the
                scorer's weighted partial credit: the rubric lives in the same
                log as each attempt's `score`, and `pass1` ignores it. Re-scoring
                the corpus on the rubric would raise rows by up to ~25 pp
                (docs/AUDIT-LOGIC-v0.5.md, F1), so the published table is
                deliberately the strict binary number.
  methodology key = "<task count> tasks, scorer <epoch>", epoch derived from the
  card timestamp and the commit that changed the scorer (v0.3.1 = 8244f05,
  2026-09-26: fixed structured-hard predicates). Rows below the current task
  count (71) or before that epoch are reported separately as legacy/not
  comparable; they are never ranked against current rows.

PROVENANCE
  Every row must resolve to results/<model>_<timestamp>.json. A card is only
  accepted as published if its suites and overall reproduce that log. `--fix-cards`
  rewrites cards that do not (and only those), recording the source log in the
  card so the number can be traced back.

USAGE
  python3 scripts/leaderboard_check.py                 # verify (exit 1 on drift)
  python3 scripts/leaderboard_check.py --write         # rewrite README block, leaderboard.json
                                                       # and the generated detail table
  python3 scripts/leaderboard_check.py --fix-cards     # repair card JSON from its run log
  python3 scripts/leaderboard_check.py --verbose       # family -> model id map, per-row sources
  python3 scripts/leaderboard_check.py --json-out /path/report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# --- methodology constants -------------------------------------------------
# The weight vector is IMPORTED from gauntlet/methodology.py (one source of
# truth); the check still verifies it matches what gauntlet.cli ships, so a
# silent divergence between the runner and the publisher fails loudly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gauntlet.methodology import (  # noqa: E402
    EPOCHS,
    METHODOLOGY_VERSION,
    SUITE_WEIGHTS,
    epoch_spec,
    newest_published_epoch,
)

SCORER_EPOCHS = [        # (epoch, first card timestamp it applies to, commit)
    ("v0.3.1", "20260926", "8244f05"),
    ("0.4.0", "20261105", "v0.4-suite"),
    ("0.5.0", "20261107", "v0.5-realworld-expand"),
]
TOL = 0.2                # published-vs-recomputed tolerance, percentage points
BLOCK_BEGIN = "<!-- BEGIN GENERATED LEADERBOARD: scripts/leaderboard_check.py -->"
BLOCK_END = "<!-- END GENERATED LEADERBOARD -->"


def _epoch_label(version: str) -> str:
    return epoch_spec(version)["label"]


# Set by set_epoch() from the corpus before any row is built. Every row is
# scored with ITS OWN epoch's weights; the headline table only ever holds rows
# from one epoch.
CURRENT_EPOCH = METHODOLOGY_VERSION
FULL_TASKS = epoch_spec(METHODOLOGY_VERSION)["tasks"]
WEIGHT_LABEL = _epoch_label(METHODOLOGY_VERSION)


def set_epoch(version: str) -> None:
    """Publish the newest epoch that actually has rows."""
    global CURRENT_EPOCH, FULL_TASKS, WEIGHT_LABEL
    spec = epoch_spec(version)
    CURRENT_EPOCH = version
    FULL_TASKS = spec["tasks"]
    WEIGHT_LABEL = spec["label"]


# display_name values that denote the same model but were spelled differently
# by hand over time. Keyed on the normalized (lowercase alphanumeric) form.
DISPLAY_ALIASES = {
    "nemotron 3 5 bolt e4b": "bolt e4b",
}


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    return DISPLAY_ALIASES.get(s, s)


def family_of(card: dict) -> str:
    return norm_name(card.get("display_name", ""))


def scorer_epoch(ts: str) -> str:
    """Epoch of the scorer that produced a card, from its own timestamp."""
    t = str(ts or "")
    for epoch, first_ts, _commit in reversed(SCORER_EPOCHS):
        if t[:8] >= first_ts:
            return epoch
    return "pre-v0.3.1"


def weighted_score(suites: dict, weights: dict | None = None) -> float | None:
    """Weighted aggregate under ONE epoch's weights (default: current)."""
    weights = weights or SUITE_WEIGHTS
    active = {s: w for s, w in weights.items() if suites.get(s) is not None}
    if not active:
        return None
    total = sum(active.values())
    return round(sum(float(suites[s]) * w for s, w in active.items()) / total * 100, 2)


def equal_suite_mean(suites: dict) -> float | None:
    vals = [float(v) for v in suites.values() if v is not None]
    return round(sum(vals) / len(vals) * 100, 2) if vals else None


# --- corpus + run logs -----------------------------------------------------

def card_files(cards_dir: Path) -> list[Path]:
    return sorted(p for p in cards_dir.glob("*.json") if p.name != "announcement.json")


def load_cards(cards_dir: Path) -> list[dict]:
    """Flatten every card object in every card json (files are 1-element lists)."""
    out = []
    for f in card_files(cards_dir):
        try:
            data = json.loads(f.read_text())
        except Exception as e:  # a broken card file must not silently vanish
            print(f"! unreadable card {f}: {e}", file=sys.stderr)
            continue
        items = data if isinstance(data, list) else [data]
        for i, obj in enumerate(items):
            if not isinstance(obj, dict) or "overall_pct" not in obj:
                continue
            out.append({
                "file": str(f),
                "index": i,
                "shape": "list" if isinstance(data, list) else "dict",
                "model": obj.get("model", ""),
                "display_name": obj.get("display_name", ""),
                "suites": obj.get("suites") or {},
                "overall_pct": obj.get("overall_pct"),
                "n": obj.get("n"),
                "ts": obj.get("ts"),
                "details": obj.get("details") or {},
                "sub": obj.get("sub", ""),
            })
    return out


def index_logs(results_dir: Path) -> dict[str, list[tuple[str, str, int]]]:
    """model -> [(timestamp, path, task_count)] for every scored run log."""
    idx: dict[str, list[tuple[str, str, int]]] = {}
    for p in sorted(results_dir.glob("*.json")):
        if p.name.startswith(("perf_", "cap_", "provenance_")):
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict) or not isinstance(d.get("results"), list):
            continue
        meta = d.get("meta") or {}
        model = meta.get("model")
        if not model:
            continue
        idx.setdefault(model, []).append((str(meta.get("timestamp", "")), str(p), len(d["results"])))
    for v in idx.values():
        v.sort()
    return idx


def score_log(path: str, weights: dict | None = None) -> dict:
    """Recompute suites + weighted score from a run log, under the epoch weights
    that run was produced with (never today's, unless they are the same)."""
    from gauntlet.run_health import transport_failure, zero_token_error_share

    d = json.loads(Path(path).read_text())
    by: dict[str, list] = {}
    for r in d["results"]:
        by.setdefault(r["suite"], []).append(float(r.get("pass1", 0.0)))
    suites = {s: sum(v) / len(v) for s, v in sorted(by.items())}
    binary = {s: sum(1.0 if x >= 1.0 else 0.0 for x in v) / len(v) for s, v in by.items()}
    return {
        "suites": suites,
        "binary_suites": binary,
        "overall": weighted_score(suites, weights),
        "equal_mean": equal_suite_mean(suites),
        "n": len(d["results"]),
        "tasks": {s: len(v) for s, v in by.items()},
        "meta": d.get("meta") or {},
        "zero_token_error_share": zero_token_error_share(d["results"]),
        "transport_failure": transport_failure(d["results"]),
    }


def pick_log(card: dict, logs: dict[str, list[tuple[str, str, int]]],
             weights: dict | None = None) -> tuple[dict | None, str]:
    """Choose the run log a card should be sourced from, and say why.

    A card is a mirror of one run. Identify that run from the card itself:
    a log whose per-suite values equal the card's suites, or whose weighted
    score equals its headline, is the run the card came from (suite match wins,
    because suite bars only ever come from one run). Only when no run matches
    either is the card unsupported, and then the latest complete run -- a re-run
    -- is used and the repair is flagged. Partial suite runs (n < FULL_TASKS)
    never source a full card.
    """
    cands = [(ts, p, n) for ts, p, n in logs.get(card["model"], []) if n == card["n"]]
    if not cands:
        return None, "no run log with {} tasks".format(card.get("n"))
    scored = []
    for ts, p, n in cands:
        try:
            s = score_log(p, weights)
        except Exception:
            continue
        suite_eq = bool(card.get("suites")) and set(card["suites"]) == set(s["suites"]) and all(
            abs(float(card["suites"][k]) - v) <= 0.002 for k, v in s["suites"].items())
        head_eq = card.get("overall_pct") is not None and abs(s["overall"] - card["overall_pct"]) <= TOL
        scored.append((suite_eq, head_eq, ts, p, n, s))
    if not scored:
        return None, "no readable run log with {} tasks".format(card.get("n"))
    # preference: suite+headline match, suite match, headline match, then latest run
    order = sorted(scored, key=lambda t: (t[0] and t[1], t[0], t[1], t[2]))
    suite_eq, head_eq, ts, p, n, s = order[-1]
    if suite_eq or head_eq:
        which = ("suites" if suite_eq else "") + ("+headline" if suite_eq and head_eq else
                                                  ("headline" if head_eq else ""))
        note = f"published run matched by {which} ({os.path.basename(p)})"
        if len(cands) > 1:
            others = [x for x in scored if x[3] != p]
            if others:
                note += "; %d other run(s) of this model exist" % len(others)
        return {"path": p, "score": s, "note": note}, note
    ts, p, n, s = order[-1][2], order[-1][3], order[-1][4], order[-1][5]
    return {"path": p, "score": s,
            "note": "latest complete re-run (no run reproduces the card)"}, "repaired from latest run"


# --- eligibility / ranking -------------------------------------------------

def classify(card: dict, src: dict | None) -> tuple[bool, str]:
    """Is a card rankable in the current methodology, and if not, why not."""
    epoch = scorer_epoch(card.get("ts", ""))
    n = card.get("n")
    if epoch != CURRENT_EPOCH:
        return False, f"scorer {epoch} (pre-{CURRENT_EPOCH})"
    if n != FULL_TASKS:
        return False, "%s tasks (current methodology is %d)" % (n, FULL_TASKS)
    if src is None:
        return False, "no complete run log (not reproducible)"
    failed, why = (src.get("score") or {}).get("transport_failure", (False, ""))
    if failed:
        return False, "transport failure: " + why
    return True, ""


def best_config_label(card: dict) -> str:
    det = card["details"]
    quant = det.get("quant")
    kv = det.get("kv_type")
    if not quant:  # older model-card rows keep the quant in `sub`
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)", card.get("sub", ""))
        quant = m.group(1) if m else "?"
    ctx = det.get("context_tokens")
    bits = [str(quant)]
    if kv:
        bits.append("KV " + str(kv))
    if ctx:
        bits.append("%dK ctx" % round(ctx / 1024))
    return " · ".join(bits)


def build_rows(cards: list[dict], logs, verbose=False) -> dict:
    """Rank the corpus: one row per model family, best scoring configuration."""
    rows, legacy, families = [], [], {}
    repaired, notes = [], []
    for c in cards:
        # score the card's run with the weights THAT run was produced under
        card_epoch = scorer_epoch(c.get("ts", ""))
        w = EPOCHS[card_epoch]["weights"] if card_epoch in EPOCHS else None
        src, note = pick_log(c, logs, w)
        rankable, why = classify(c, src)
        canon = src["score"] if src else None
        entry = {
            "model": c["model"],
            "display_name": c["display_name"],
            "family": family_of(c),
            "file": c["file"],
            "ts": c["ts"],
            "n": c["n"],
            "published": c["overall_pct"],
            "recomputed": canon["overall"] if canon else None,
            "source_log": src["path"] if src else None,
            "source_note": note,
            "suites": canon["suites"] if canon else c["suites"],
            "config": best_config_label(c),
            "category": c["details"].get("category") or "on-GPU ≤12B",
            "epoch": scorer_epoch(c.get("ts", "")),
            "rankable": rankable,
            "not_rankable_because": why,
            "card_suites_match_log": bool(canon) and all(
                abs(c["suites"].get(s, -1) - v) <= 0.002 for s, v in canon["suites"].items()
            ) and set(c["suites"]) == set(canon["suites"]),
            "card_headline_matches_log": bool(canon) and c["overall_pct"] is not None and abs(
                c["overall_pct"] - canon["overall"]) <= TOL,
        }
        if not rankable:
            legacy.append(entry)
            continue
        families.setdefault(entry["family"], []).append(entry)
        if not entry["card_suites_match_log"] or not entry["card_headline_matches_log"]:
            repaired.append(entry)
            notes.append({
                "model": entry["model"],
                "card": os.path.relpath(entry["file"]),
                "published": entry["published"],
                "recomputed": entry["recomputed"],
                "suites_match": entry["card_suites_match_log"],
                "headline_matches": entry["card_headline_matches_log"],
                "source_log": os.path.relpath(entry["source_log"]) if entry["source_log"] else None,
                "source_note": entry["source_note"],
            })

    for _fam, entries in families.items():
        entries.sort(key=lambda e: -e["recomputed"])
        best = entries[0]
        best = dict(best)
        best["variants"] = len(entries)
        rows.append(best)

    ongpu = [r for r in rows if r["category"] != "offload"]
    offload = [r for r in rows if r["category"] == "offload"]
    ongpu.sort(key=lambda r: -r["recomputed"])
    offload.sort(key=lambda r: -r["recomputed"])
    if verbose:
        for r in ongpu + offload:
            print("family=%-30s best=%-34s %5.1f%% of %d variant(s)" % (
                r["family"], r["model"], r["recomputed"], r["variants"]), file=sys.stderr)
    return {
        "rows": ongpu,
        "offload": offload,
        "legacy": sorted(legacy, key=lambda r: (r["family"], -(r["published"] or 0))),
        "card_repairs": notes,
        "families": {k: [e["model"] for e in v] for k, v in families.items()},
    }


# --- rendering -------------------------------------------------------------

MEDALS = {0: "🥇", 1: "🥈", 2: "🥉"}


def pct(v, digits=1):
    return "—" if v is None else ("%." + str(digits) + "f%%") % v


def legacy_groups(legacy: list[dict]) -> list[dict]:
    """Collapse the non-comparable rows to one row per (model, epoch).

    Provenance is the point of this table, not completeness: an epoch bump puts every older
    configuration in here at once (0.5.0 moved 228 cards out of the ranking), and 228 legacy
    rows bury the live table. The full list stays in `results/_published/leaderboard.json`
    and in `results/_published/LEADERBOARD.md`; the README shows the best legacy configuration
    of each model and how many sat behind it.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in legacy:
        # Family, not display name: the pre-0.5.0 cards spell the same model several ways
        # ("Spark-X2.6 4B" / "Spark-X2.6-4B"), and one model must not get two legacy rows.
        groups.setdefault((r.get("family") or r["display_name"], r.get("epoch") or ""), []).append(r)
    out = []
    for entries in groups.values():
        entries.sort(key=lambda e: -(e.get("published") if e.get("published") is not None else -1))
        best = dict(entries[0])
        best["variants"] = len(entries)
        out.append(best)
    out.sort(key=lambda r: (r["display_name"], -(r["published"] or 0)))
    return out


def render_block(data: dict) -> str:
    L = [BLOCK_BEGIN, ""]
    L.append("**Current leaderboard — %d tasks, scorer %s, PVE GTX 1070 Ti 8 GB, all layers "
             "on-GPU, zero CPU offload, temp 0, seed 1.**" % (FULL_TASKS, CURRENT_EPOCH))
    L.append("")
    L.append("One row per model: the **best-scoring configuration** of that model in the corpus "
             "(%d scored configurations behind this table). Every score is the weighted aggregate "
             "defined in `scripts/leaderboard_check.py` and is recomputed from that run's log; the "
             "`Method` column carries the task count and scorer version for the row, so no row is "
             "ever compared across methodologies. Full per-configuration data: "
             "[`results/_published/LEADERBOARD.md`](results/_published/LEADERBOARD.md)." % (
                 sum(r["variants"] for r in data["rows"] + data["offload"])))
    L.append("")
    L.append(
        "| Rank | Model | Best configuration | Score | Tool | Adv | Chains | Struct | "
        "Retr | Code | Instr | Method | Card |"
    )
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(data["rows"]):
        su = r["suites"]
        cells = [pct((su.get(k) or 0) * 100, 0) for k in
                 ("tooluse", "adversarial", "agent_chains", "structured", "retrieval", "coding", "instruction")]
        rank = MEDALS.get(i, str(i + 1))
        card = "card_{}.png".format(r["model"])
        L.append("| %s | %s | %s | **%s** | %s | %d t · %s | [png](results/cards/%s) |" % (
            rank, r["display_name"], r["config"], pct(r["recomputed"]),
            " | ".join(cells), FULL_TASKS, r["epoch"], card))
    L.append("")
    if data["legacy"]:
        groups = legacy_groups(data["legacy"])
        L.append("**Legacy rows — NOT comparable, kept for provenance:** one row per model, its "
                 "best-scoring pre-0.5.0 configuration; the %d configurations behind them are "
                 "listed in [`results/_published/LEADERBOARD.md`](results/_published/LEADERBOARD.md)."
                 % len(data["legacy"]))
        L.append("")
        L.append("| Model | Best legacy configuration | Configurations | Score | Why it is not comparable |")
        L.append("|---|---|---|---|---|")
        for r in groups:
            L.append("| {} | {} | {} | {} | {} |".format(
                r["display_name"], r["config"], r["variants"], pct(r["published"]),
                r["not_rankable_because"]))
        L.append("")
    if data["offload"]:
        L.append("**Offload / >12B — scored separately, never merged with the on-GPU table:**")
        L.append("")
        L.append("| Model | Configuration | Score | Method |")
        L.append("|---|---|---|---|")
        for r in data["offload"]:
            L.append("| %s | %s | %s | %d t · %s |" % (
                r["display_name"], r["config"], pct(r["recomputed"]), FULL_TASKS, r["epoch"]))
        L.append("")

    # takeaways are generated from the same rows, so the prose cannot drift either
    L.append("**What this table says:**")
    L.append("")
    if data["rows"]:
        top = data["rows"][0]
        L.append("- **Best on-GPU: %s (%s) at %s** — %d configuration(s) of this model were scored; "
                 "this is the best of them." % (top["display_name"], top["config"],
                                                 pct(top["recomputed"]), top["variants"]))
    if len(data["rows"]) > 1:
        nxt = data["rows"][1]
        gap = data["rows"][0]["recomputed"] - nxt["recomputed"]
        verdict = (" — inside the weight of a single task (0.7-1.6 pp here depending on the "
                   "suite), so a tie, not a win."
                   if gap <= 1.5 else f" — {gap:.1f} pp behind.")
        L.append("- Next: {} ({}) at {}{}".format(nxt["display_name"], nxt["config"],
                                              pct(nxt["recomputed"]), verdict))
    if data["legacy"]:
        n_legacy = len(data["legacy"])
        L.append("- %d legacy %s excluded from the ranking (task count or scorer version differs); "
                 "%s %s the published number below but %s never ranked against current rows."
                 % (n_legacy, "row is" if n_legacy == 1 else "rows are",
                    "it" if n_legacy == 1 else "they",
                    "keeps" if n_legacy == 1 else "keep",
                    "is" if n_legacy == 1 else "are"))
    L.append("")
    L.append("_Generated by `scripts/leaderboard_check.py` from `results/cards/*.json`. "
             "`python3 scripts/leaderboard_check.py` fails when this block and the corpus "
             "disagree — edit the generator, not the table._")
    L.append("")
    L.append(BLOCK_END)
    return "\n".join(L)


def publish_json(data: dict) -> str:
    models = []
    for i, r in enumerate(data["rows"]):
        models.append({
            "rank": i + 1,
            "model": r["model"],
            "display_name": r["display_name"],
            "configuration": r["config"],
            "overall_pct": r["recomputed"],
            "suites": {k: round(v, 4) for k, v in r["suites"].items()},
            "tasks": FULL_TASKS,
            "scorer": r["epoch"],
            "variants_scored": r["variants"],
            "card_png": "results/cards/card_{}.png".format(r["model"]),
            "source_log": os.path.relpath(r["source_log"]),
        })
    doc = {
        "benchmark": "slm-gauntlet %s (%d tasks: %s)" % (
            CURRENT_EPOCH, FULL_TASKS,
            ", ".join("%s %d" % (k, v) for k, v in sorted(
                task_inventory(Path(__file__).resolve().parent.parent).items()) if k != "*")),
        "hardware": "8GB-class GPU (GTX 1070 Ti), all layers on-GPU, zero CPU offload, llama.cpp",
        "settings": "temperature 0, seed 1, thinking disabled, pass@1",
        "weights": WEIGHT_LABEL,
        "methodology": "one row per model, best-scoring configuration; scores recomputed from "
                       "each run log by scripts/leaderboard_check.py",
        "generated_by": "scripts/leaderboard_check.py --write",
        "models": models,
        "offload": [{
            "model": r["model"],
            "display_name": r["display_name"],
            "configuration": r["config"],
            "overall_pct": r["recomputed"],
            "tasks": FULL_TASKS,
            "scorer": r["epoch"],
            "source_log": os.path.relpath(r["source_log"]),
        } for r in data["offload"]],
        "legacy_not_comparable": [{
            "model": r["model"],
            "display_name": r["display_name"],
            "configuration": r["config"],
            "overall_pct": r["published"],
            "tasks": r["n"],
            "reason": r["not_rankable_because"],
        } for r in data["legacy"]],
    }
    return json.dumps(doc, indent=1) + "\n"


# --- readme / file io ------------------------------------------------------

def read_readme(path: Path) -> str:
    return path.read_text()


def current_block(text: str) -> str | None:
    b = text.find(BLOCK_BEGIN)
    e = text.find(BLOCK_END)
    if b < 0 or e < 0 or e < b:
        return None
    return text[b:e + len(BLOCK_END)]


def write_readme(path: Path, text: str, block: str) -> None:
    cur = current_block(text)
    if cur is not None:
        new = text.replace(cur, block)
    else:  # first run: drop the hand-written table, insert the generated block
        lines = text.splitlines()
        start = None
        for i, ln in enumerate(lines):
            if ln.startswith("**Current leaderboard"):
                start = i
                break
        end = None
        if start is not None:
            for j in range(start + 1, len(lines)):
                if lines[j].startswith("Full data:"):
                    end = j
                    break
        if start is None or end is None:
            raise SystemExit("cannot find the old README table to replace "
                             "(no '**Current leaderboard' .. 'Full data:' lines)")
        new = "\n".join(lines[:start] + block.split("\n") + lines[end:]) + "\n"
    path.write_text(new)


def diff_lines(a: str, b: str) -> str:
    import difflib
    return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                          "README.md (committed)", "corpus (generated)", lineterm=""))


# --- card repair -----------------------------------------------------------

def fix_cards(data: dict, cards_dir: Path, dry_run=False) -> list[dict]:
    """Rewrite cards that do not reproduce their run log (only those)."""
    changed = []
    by_file: dict[str, list[dict]] = {}
    for r in data["card_repairs"]:
        by_file.setdefault(os.path.abspath(r["card"]), []).append(r)
    for path, repairs in by_file.items():
        p = Path(path)
        raw = json.loads(p.read_text())
        items = raw if isinstance(raw, list) else [raw]
        touched = False
        for rep in repairs:
            for obj in items:
                if obj.get("model") != rep["model"]:
                    continue
                _ep = scorer_epoch(obj.get("ts", ""))
                src = score_log(os.path.abspath(rep["source_log"]),
                                EPOCHS[_ep]["weights"] if _ep in EPOCHS else None)
                before = (obj.get("overall_pct"), dict(obj.get("suites") or {}))
                obj["suites"] = {k: round(v, 4) for k, v in src["suites"].items()}
                obj["overall_pct"] = round(src["overall"], 1)
                obj["n"] = src["n"]
                obj["scorer"] = scorer_epoch(obj.get("ts", ""))
                obj["score_weights"] = "cli-%dsuite" % len(
                    EPOCHS[_ep]["weights"] if _ep in EPOCHS else SUITE_WEIGHTS)
                obj["source_log"] = os.path.relpath(os.path.abspath(rep["source_log"]))
                obj["tasks_per_suite"] = src["tasks"]
                touched = True
                changed.append({
                    "card": os.path.relpath(p),
                    "model": rep["model"],
                    "overall_before": before[0],
                    "overall_after": obj["overall_pct"],
                    "suites_changed": sum(1 for k, v in obj["suites"].items()
                                          if abs(before[1].get(k, -1) - v) > 0.002),
                    "source_log": obj["source_log"],
                    "reason": ("headline was an equal-suite mean, not the weighted score"
                               if rep["suites_match"] and not rep["headline_matches"]
                               else "suite bars were binary pass rates, headline was partial credit; "
                                    "both rebuilt from the run log"),
                })
        if touched and not dry_run:
            p.write_text(json.dumps(raw, indent=1) + "\n")
    return changed


# --- main ------------------------------------------------------------------

def verify_weights() -> str | None:
    """The published weight vector must be the one the runner uses, and it must
    cover the full task set it claims to."""
    total = sum(SUITE_WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        return f"SUITE_WEIGHTS sum to {total:.4f}, not 1.0 — the score is not a percentage"
    try:
        from gauntlet.cli import SUITE_WEIGHTS as SRC  # type: ignore
    except Exception:
        SRC = None  # httpx absent under system python: the runner check is skipped
    if SRC is not None and {k: round(v, 6) for k, v in SRC.items()} != {
        k: round(v, 6) for k, v in SUITE_WEIGHTS.items()
    }:
        return (f"gauntlet/cli.py SUITE_WEIGHTS {SRC} != published weights {SUITE_WEIGHTS} — "
                "methodology changed, update this script and the README method note")
    return None


def task_inventory(root: Path) -> dict[str, int]:
    """Count tasks per suite from the YAML, without importing the httpx stack."""
    counts: dict[str, int] = {}
    for path in sorted((root / "tasks").glob("*.yaml")):
        text = path.read_text()
        for _m in re.finditer(r"^-\s+id:\s*\S+", text, re.M):
            counts.setdefault("*", 0)
            counts["*"] += 1
        for suite in re.findall(r"^\s+suite:\s*(\w+)\s*$", text, re.M):
            counts[suite] = counts.get(suite, 0) + 1
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--readme", default=None)
    ap.add_argument(
        "--write",
        action="store_true",
        help="regenerate the README block + results/_published/leaderboard.json",
    )
    ap.add_argument("--fix-cards", action="store_true", help="repair card JSON that does not reproduce its run log")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.root)
    cards_dir = root / "results" / "cards"
    readme = Path(a.readme) if a.readme else root / "README.md"
    lj = root / "results" / "_published" / "leaderboard.json"
    if not cards_dir.is_dir():
        print(f"no cards dir at {cards_dir}", file=sys.stderr)
        return 2

    bad_weights = verify_weights()
    if bad_weights:
        print("METHODOLOGY DRIFT: " + bad_weights, file=sys.stderr)
        return 1

    cards = load_cards(cards_dir)
    # Publish the newest epoch that actually has results. Without this, bumping
    # METHODOLOGY_VERSION marked the entire existing corpus "legacy" and emptied
    # the leaderboard the same day the new version was written.
    try:
        set_epoch(newest_published_epoch({scorer_epoch(c.get("ts", "")) for c in cards}))
    except KeyError as e:
        print(f"cannot pick a published epoch: {e}", file=sys.stderr)
        return 2
    logs = index_logs(root / "results")
    data = build_rows(cards, logs, verbose=a.verbose)
    block = render_block(data)
    lj_text = publish_json(data)

    print("corpus: %d cards (%d rankable models after family collapse, %d offload, %d legacy)"
          % (len(cards), len(data["rows"]), len(data["offload"]), len(data["legacy"])))
    for r in data["legacy"]:
        print("  legacy: %-28s n=%s published=%s — %s"
              % (r["display_name"], r["n"], pct(r["published"]), r["not_rankable_because"]))
    print(f"methodology: {WEIGHT_LABEL} (scorer {CURRENT_EPOCH})")
    print("card repairs needed: %d" % len(data["card_repairs"]))
    for r in data["card_repairs"]:
        print("  %-38s card %-52s published=%s recomputed=%s (suites_match=%s headline_match=%s)"
              % (r["model"], r["card"], r["published"], r["recomputed"],
                 r["suites_match"], r["headline_matches"]))

    if a.fix_cards:
        changed = fix_cards(data, cards_dir, dry_run=a.dry_run)
        print("%s %d card file(s)" % ("would rewrite" if a.dry_run else "rewrote", len({c['card'] for c in changed})))
        for c in changed:
            print("  %-40s %s -> %s (%d suite cells, %s)"
                  % (c["model"], c["overall_before"], c["overall_after"],
                     c["suites_changed"], c["reason"]))
        cards = load_cards(cards_dir)
        data = build_rows(cards, logs, verbose=a.verbose)
        block = render_block(data)
        lj_text = publish_json(data)
        print("after repair: %d card repairs outstanding" % len(data["card_repairs"]))

    def row_problems(have_block: str) -> list[str]:
        """Readable per-row cross-check (the exact-block compare catches edits; this names them)."""
        out = []
        known = [r["display_name"] for r in data["rows"] + data["offload"]]
        # The legacy section renders ONE row per model (best legacy configuration), so a legacy
        # entry's own display name need not appear - its group's does.
        known += [g["display_name"] for g in legacy_groups(data["legacy"])]
        lines = [ln for ln in have_block.splitlines() if ln.startswith("|")]
        for name in known:
            if not any(name in ln for ln in lines):
                out.append(f"README table is missing a row for {name!r}")
        for ln in lines:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if not cells or set(cells[0]) <= set("-: ") or cells[0] in ("Rank", "Model", "#"):
                continue
            if not any(n in ln for n in known):
                out.append("README table row %r is not in the corpus" % (cells[0] or ln[:40]))
        return out

    def detail_problems() -> list[str]:
        """results/_published/LEADERBOARD.md is generated from the same cards; catch staleness too."""
        gen = root / "gen-leaderboard.py"
        committed = root / "results" / "_published" / "LEADERBOARD.md"
        if not gen.exists():
            return []
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "LEADERBOARD.md"
            r = subprocess.run([sys.executable, str(gen), "--out", str(tmp)],
                               cwd=str(root), capture_output=True, text=True)
            if r.returncode != 0:
                return ["gen-leaderboard.py failed: " + (r.stderr or r.stdout)[-300:]]
            if not committed.exists() or committed.read_text() != tmp.read_text():
                return ["results/_published/LEADERBOARD.md is stale — run python3 gen-leaderboard.py "
                        "(the detail table is generated from the same cards)"]
        return []

    def verify_all() -> list[str]:
        out = []
        text_now = read_readme(readme)
        have_block = current_block(text_now)
        if have_block is None:
            out.append("README.md has no GENERATED LEADERBOARD block (run --write)")
        else:
            if have_block != block:
                out.append("README.md table does not match the corpus:\n" + diff_lines(have_block, block))
            out += row_problems(have_block)
        if not lj.exists():
            out.append("results/_published/leaderboard.json is missing (run --write)")
        elif lj.read_text() != lj_text:
            out.append("results/_published/leaderboard.json does not match the corpus (run --write)")
        if data["card_repairs"]:
            out.append("%d card(s) do not reproduce their run log (run --fix-cards)"
                       % len(data["card_repairs"]))
        for r in data["rows"] + data["offload"]:
            png = root / "results" / "cards" / ("card_{}.png".format(r["model"]))
            if not png.exists():
                out.append("card image missing for {!r}: {}".format(r["display_name"], os.path.relpath(png)))
        out += detail_problems()
        return out

    if a.write:
        if not a.dry_run:
            write_readme(readme, read_readme(readme), block)
            lj.parent.mkdir(parents=True, exist_ok=True)
            lj.write_text(lj_text)
            gen = root / "gen-leaderboard.py"
            if gen.exists():  # detail table comes from the same corpus
                subprocess.run([sys.executable, str(gen)], cwd=str(root), check=False)
        print("{} README block and {}".format("would write" if a.dry_run else "wrote",
                                          os.path.relpath(lj)))

    problems = verify_all()

    if a.json_out:
        Path(a.json_out).write_text(json.dumps({
            "rows": data["rows"], "offload": data["offload"], "legacy": data["legacy"],
            "card_repairs": data["card_repairs"], "problems": problems,
        }, indent=1, default=str) + "\n")

    if problems:
        for p in problems:
            print("\nDRIFT: " + p, file=sys.stderr)
        return 1
    print("OK: README table, results/_published/leaderboard.json and %d cards agree with the corpus"
          % len(cards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
