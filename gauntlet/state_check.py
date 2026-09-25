"""State-based verification (BFCL V3-style): evaluate sandbox outcomes after the run.

Checks the achieved world state, not the model's claims about it:
- tool_called / tool_not_called against the actual call log
- state_path against sandbox.state (e.g. reservations.0.name == "Ada Lovelace")
- file_content against files actually written in the sandbox
"""

from __future__ import annotations

from gauntlet.sandbox import ToolSandbox
from gauntlet.task import StateAssert


def _resolve_path(state: dict, path: str):
    cur = state
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def evaluate_state_asserts(sandbox: ToolSandbox, asserts: list[StateAssert]) -> dict:
    """Returns {score: float, passed: bool, failed: [str], checks: [dict]}."""
    earned = 0.0
    total = 0.0
    must_pass_failed = False
    failed: list[str] = []
    checks: list[dict] = []

    tools_called = [c["tool"] for c in sandbox.call_log]

    for sa in asserts:
        total += sa.weight
        ok = False
        detail = ""
        if sa.type == "tool_called":
            ok = sa.tool in tools_called
            detail = f"tool {sa.tool}"
        elif sa.type == "tool_not_called":
            ok = sa.tool not in tools_called
            detail = f"tool {sa.tool} not called"
        elif sa.type == "state_path":
            value = _resolve_path(sandbox.state, sa.path or "")
            if sa.equals is not None:
                # missing key == empty default when expecting an empty container
                # (e.g. reservations == [] when nothing was ever created)
                if value is None and sa.equals in ([], {}, "", 0):
                    ok = True
                else:
                    ok = value == sa.equals
                detail = f"{sa.path} == {sa.equals!r} (got {value!r})"
            else:
                ok = value is not None
                detail = f"{sa.path} exists (got {value!r})"
        elif sa.type == "file_content":
            target = sandbox.root / (sa.path or "")
            if target.exists():
                content = target.read_text()
                ok = sa.contains in content if sa.contains else True
                detail = f"file {sa.path}"
            else:
                detail = f"file {sa.path} missing"

        if ok:
            earned += sa.weight
        else:
            failed.append(f"state:{sa.type}:{detail}")
            if sa.must_pass:
                must_pass_failed = True
        checks.append({"check": f"state:{sa.type}", "ok": ok, "detail": detail})

    score = 0.0 if must_pass_failed else (earned / total if total else 1.0)
    return {"score": score, "passed": not failed, "failed": failed, "checks": checks}
