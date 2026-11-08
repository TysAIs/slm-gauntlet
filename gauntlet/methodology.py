"""Single source of truth for the gauntlet's published methodology.

Three places used to carry their own weight table (cli.SUITE_WEIGHTS,
report.DEFAULT_WEIGHTS, scripts/leaderboard_check.py). Two of them disagreed
about the same suites, so "the score" depended on which code path printed it.
Everything now imports from here, and every results file records the
methodology version it was produced under.
"""

from __future__ import annotations

METHODOLOGY_VERSION = "0.5.1"

# Published weights. They sum to 1.0 over the suites the gauntlet scores.
# realworld is new in 0.4: multi-constraint everyday agent work, graded on
# state/arithmetic, not keyword presence.
SUITE_WEIGHTS: dict[str, float] = {
    "tooluse": 0.26,
    "structured": 0.12,
    "retrieval": 0.12,
    "coding": 0.12,
    "instruction": 0.10,
    "adversarial": 0.08,
    "agent_chains": 0.08,
    "realworld": 0.12,
}

# Suites that exist as separate, opt-in YAML (not part of `--suite all`).
EXTRA_SUITES = {"routing"}

# Suites built at run time by gauntlet/cli.py instead of from a task YAML
# (contamination-resistant retrieval: fresh needles per seed).
GENERATED_SUITES = {"retrieval"}

# Context ladder for the generated retrieval tasks, in target tokens. The lane
# this runs on exposes a 32768-token window; a 32k *target* tokenized to 34,976
# real tokens and every request 400'd, so the 32k cell measured nothing at all
# (230 of 276 attempts were client errors). 24k tokenizes to ~26k and fits with
# room for the answer.
RETRIEVAL_LADDER = (8000, 16000, 24000)
NOLIMA_LADDER = (8000, 24000)
SERVED_CONTEXT_TOKENS = 32768


def check_weights() -> None:
    total = sum(SUITE_WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        raise SystemExit(f"SUITE_WEIGHTS must sum to 1.0, got {total:.4f}")


def methodology_line(task_count: int) -> str:
    return f"{METHODOLOGY_VERSION} · {task_count} tasks · context ladder {RETRIEVAL_LADDER[-1] // 1000}K"


# ---------------------------------------------------------------------------
# Published epochs. A historical score keeps the weights and task count it was
# RUN under. Re-scoring an old run with today's weights changes the number
# without changing the measurement, so the publisher must not do it silently:
# each row is recomputed with its own epoch's table, and rows from different
# epochs are never ranked against each other.
# ---------------------------------------------------------------------------
EPOCH_ORDER = ("v0.3.1", "0.4.0", "0.5.0", "0.5.1")


def _count_current_tasks() -> int:
    """Real size of the current suite: every YAML task plus the retrieval tasks
    cli.py generates at run time. A hardcoded count is a promise the task files
    can silently break — the published "85 tasks" was already wrong (the corpus
    was 77 YAML + 7 generated = 84).
    """
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parent.parent / "tasks"
    n = 0
    for path in sorted(root.glob("*.yaml")):
        n += len(yaml.safe_load(path.read_text()) or [])
    n += len(RETRIEVAL_LADDER) + len(NOLIMA_LADDER) + 1 + 1  # needles, nolima, refusal, multi
    return n


CURRENT_TASK_COUNT = _count_current_tasks()

EPOCHS: dict[str, dict] = {
    "v0.3.1": {
        "weights": {
            "tooluse": 0.30,
            "structured": 0.15,
            "retrieval": 0.15,
            "coding": 0.10,
            "instruction": 0.10,
            "adversarial": 0.10,
            "agent_chains": 0.10,
        },
        "tasks": 71,
        "label": (
            "7-suite weights (tool .30 / structured .15 / retrieval .15 / coding .10 / "
            "instruction .10 / adversarial .10 / chains .10), 71 tasks"
        ),
    },
    "0.4.0": {
        "weights": SUITE_WEIGHTS,
        # FROZEN: 84 = 77 YAML tasks + 7 generated retrieval tasks as they were
        # when this epoch was authored. A live-derived count let a later task
        # addition retroactively change what an old epoch means.
        "tasks": 84,
        "label": "CLI 8-suite weights ("
        + " / ".join(f"{k} {v:.2f}" for k, v in SUITE_WEIGHTS.items())
        + "), 84 tasks",
    },
    "0.5.0": {
        "weights": SUITE_WEIGHTS,
        # FROZEN at 94: the epoch was measured with 94 tasks. It used to read
        # CURRENT_TASK_COUNT, which would have redefined a measured epoch the
        # moment 0.5.1 added a task (the same defect 0.4.0 documents).
        "tasks": 94,
        "label": "CLI 8-suite weights ("
        + " / ".join(f"{k} {v:.2f}" for k, v in SUITE_WEIGHTS.items())
        + "), 94 tasks",
    },
    "0.5.1": {
        "weights": SUITE_WEIGHTS,
        "tasks": CURRENT_TASK_COUNT,
        "label": "CLI 8-suite weights ("
        + " / ".join(f"{k} {v:.2f}" for k, v in SUITE_WEIGHTS.items())
        + f"), {CURRENT_TASK_COUNT} tasks (realworld multi-answer scenarios scored as "
        "sub-answer units)",
    },
}


def epoch_spec(version: str) -> dict:
    if version not in EPOCHS:
        raise KeyError(f"unknown methodology epoch {version!r}; known: {sorted(EPOCHS)}")
    return EPOCHS[version]


def newest_published_epoch(present: set[str]) -> str:
    """The newest epoch that actually has results. Publishing an epoch with no
    rows would silently empty the leaderboard."""
    known = [e for e in EPOCH_ORDER if e in present]
    if not known:
        raise KeyError(f"no known epoch among {sorted(present)}")
    return known[-1]

