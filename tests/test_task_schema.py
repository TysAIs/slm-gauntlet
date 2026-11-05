"""Every YAML in tasks/ must parse and validate against the Task schema."""

from pathlib import Path

import pytest
import yaml

from gauntlet.task import Task

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"

# Derived from the published weight table, not hardcoded: a task in a suite the
# methodology does not weight is silently UNSCORED, which is how the realworld
# suite could have shipped with weight but no tasks (or tasks but no weight).
from gauntlet.methodology import SUITE_WEIGHTS  # noqa: E402

EXPECTED_SUITES = set(SUITE_WEIGHTS)


def task_files():
    return sorted(TASKS_DIR.glob("*.yaml"))


def test_tasks_dir_exists():
    assert TASKS_DIR.exists()
    assert len(task_files()) >= 1


@pytest.mark.parametrize("path", task_files(), ids=lambda p: p.name)
def test_yaml_valid(path):
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, list) and data, f"{path.name} must be a non-empty list"
    for i, raw in enumerate(data):
        task = Task(**raw)
        assert task.id, f"{path.name}[{i}]: missing id"
        assert task.suite in EXPECTED_SUITES, f"{path.name}[{i}]: unknown suite {task.suite}"
        assert task.asserts, f"{path.name}[{i}]: no asserts"


def test_flaky_tasks_have_repeats():
    for path in task_files():
        for raw in yaml.safe_load(path.read_text()):
            task = Task(**raw)
            if task.flaky:
                assert task.repeats >= 3, f"{task.id}: flaky task must repeat >=3 for pass^k"


def test_no_duplicate_ids():
    seen = set()
    for path in task_files():
        for raw in yaml.safe_load(path.read_text()):
            tid = raw["id"]
            assert tid not in seen, f"duplicate task id: {tid}"
            seen.add(tid)


def test_contamination_labels_valid():
    for path in task_files():
        for raw in yaml.safe_load(path.read_text()):
            task = Task(**raw)
            assert task.contamination_risk in ("none", "generated", "known")


def test_published_task_count_matches_the_corpus():
    """The leaderboard prints a task count. It must be the number of tasks that
    actually exist, not a number someone typed once."""
    from gauntlet.methodology import CURRENT_TASK_COUNT, EPOCHS, METHODOLOGY_VERSION

    real = 0
    for path in task_files():
        real += len(yaml.safe_load(path.read_text()) or [])
    from gauntlet.methodology import NOLIMA_LADDER, RETRIEVAL_LADDER

    real += len(RETRIEVAL_LADDER) + len(NOLIMA_LADDER) + 2  # refusal + multi
    assert real == CURRENT_TASK_COUNT, f"corpus has {real}, methodology publishes {CURRENT_TASK_COUNT}"
    assert EPOCHS[METHODOLOGY_VERSION]["tasks"] == real


def test_every_weighted_suite_has_tasks():
    """A weighted suite with no tasks inflates nobody's score, but a task whose
    suite is unweighted never counts — both are methodology lies."""
    from gauntlet.methodology import GENERATED_SUITES, SUITE_WEIGHTS

    present = set(GENERATED_SUITES)
    for path in task_files():
        for raw in yaml.safe_load(path.read_text()) or []:
            present.add(raw["suite"])
    missing = sorted(set(SUITE_WEIGHTS) - present)
    assert not missing, f"weighted suites with no task files: {missing}"
