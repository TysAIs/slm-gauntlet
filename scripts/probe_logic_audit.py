"""Static probes for the SLM Gauntlet logic audit (docs/AUDIT-LOGIC-v0.5.md).

No model calls; CPU only. Each section prints the EVIDENCE lines the audit
quotes. Run from the repo root:

    .venv/bin/python scripts/probe_logic_audit.py
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, ".")

from gauntlet.report import aggregate_results
from gauntlet.sandbox import ToolSandbox
from gauntlet.scorer import Scorer
from gauntlet.state_check import evaluate_state_asserts
from gauntlet.task import StateAssert, Task


def p1_state_path_false_pass():
    print("== P1 state_path: a missing key satisfies equals=False (bool==int identity) ==")
    for want in (False, 0, None, [], {}):
        sb = ToolSandbox(seed=0)
        r = evaluate_state_asserts(
            sb, [StateAssert(type="state_path", path="flags.enabled", equals=want)]
        )
        print(f"  asked flags.enabled == {want!r} on an EMPTY sandbox -> "
              f"passed={r['passed']} score={r['score']}")
        sb.cleanup()


def p2_rubric_dropped():
    print("== P2 rubric score is dropped by aggregation (pass1 only) ==")
    fake = [{"task_id": "x", "suite": "instruction", "repeats": 1, "pass1": 0.0, "pass_k": 0.0,
             "attempts": [{"terminated": "completed", "passed": False, "score": 0.667}]}]
    print("  attempt rubric score recorded:", fake[0]["attempts"][0]["score"])
    print("  aggregate:", json.dumps(aggregate_results(fake)))


def p3_partial_coverage():
    print("== P3 partial-coverage run publishes a full-looking score (weights renormalize) ==")
    one = [{"task_id": "a", "suite": "tooluse", "repeats": 1, "pass1": 0.5, "pass_k": 0.0,
            "attempts": [{"terminated": "completed", "passed": False, "score": 0.5}]}]
    print("  one tooluse task only -> capability score:",
          aggregate_results(one)["subagent_capability_score"],
          "(tooluse weight is 0.26 of 1.0)")


def p4_flaky():
    print("== P4 'flaky' field vs repeats ==")
    t = Task(id="t", suite="s", description="d", prompt="p",
             asserts=[{"type": "contains_all", "values": ["x"]}], flaky=True)
    print(f"  flaky=True repeats={t.repeats} (3 = the flag is enforced)")


def p5_comma_normalization():
    print("== P5 comma stripping applies to contains/exact only ==")
    print("  exact_match 'Hello, world':",
          Scorer().score("Hello, world",
                         [{"type": "exact_match", "value": "Hello, world"}]).passed)
    print("  regex needs the commas a contains_all check ignores:",
          Scorer().score("1284.50", [{"type": "regex", "pattern": r"1,284\.50"}]).passed)


def p6_answer_leak():
    print("== P6 answer-leak scan: assert tokens that already appear in the prompt ==")
    leaks = []
    for path in sorted(Path("tasks").glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text()) or []:
            t = Task(**raw)
            prompt_l = (t.prompt + " " + t.system).lower()
            for a in t.asserts:
                vals = list(a.values) if a.values else ([a.value] if a.value else [])
                for v in vals:
                    if len(v) >= 4 and v.lower() in prompt_l:
                        leaks.append((t.id, a.type, v))
    print(f"  tasks with an assert value already present verbatim in the prompt: {len(leaks)}")
    for row in leaks[:12]:
        print("   ", row)


if __name__ == "__main__":
    p1_state_path_false_pass()
    p2_rubric_dropped()
    p3_partial_coverage()
    p4_flaky()
    p5_comma_normalization()
    p6_answer_leak()
