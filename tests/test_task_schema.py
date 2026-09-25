"""Every YAML in tasks/ must parse and validate against the Task schema."""

from pathlib import Path

import yaml
import pytest

from gauntlet.task import Task

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"

EXPECTED_SUITES = {"tooluse"}


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
