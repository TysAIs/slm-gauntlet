"""Task definition models (YAML schema) — pydantic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ToolDef(BaseModel):
    """OpenAI-format function tool definition. Accepts a bare tool name
    (string shorthand) — the sandbox supplies the canonical spec at run time."""
    name: str
    description: str = ""
    parameters: dict = Field(default_factory=dict)  # JSON schema

    @model_validator(mode="before")
    @classmethod
    def _coerce_name_shorthand(cls, v):
        if isinstance(v, str):
            return {"name": v}
        return v

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


class Assert(BaseModel):
    type: Literal["exact_match", "contains_all", "contains_any", "regex", "json_schema", "predicate", "python_exec"]
    value: str | None = None
    values: list[str] | None = None
    pattern: str | None = None
    schema_: dict | None = Field(default=None, alias="schema")
    expr: str | None = None  # predicate: python bool expr with `out` bound
    tests: str | None = None  # python_exec: code appended to the answer and executed
    timeout: float = 10.0  # python_exec: subprocess wall clock cap (seconds)
    weight: float = 1.0  # partial-credit weight (Vals-AI-style rubric)
    must_pass: bool = False  # must-pass gate: failure forces task partial score to 0

    model_config = {"populate_by_name": True}


class StateAssert(BaseModel):
    """State/behavioral assertion evaluated against the sandbox after the run.

    BFCL V3-style state-based evaluation: verify achieved outcomes, not just
    final text. Types:
      tool_called   — tool appears in call log           {"tool": name}
      tool_not_called — tool absent from call log        {"tool": name}
      state_path    — dot path into sandbox.state        {"path": "reservations.0.name", "equals": X}
      file_content  — file in sandbox                    {"path": "report.txt", "contains": X}
      file_lines    — file's non-blank lines, IN ORDER, exactly as listed
                      {"path": "out.csv", "lines": ["hdr", "row1"]}. `contains`
                      cannot see ordering or extra rows, so a sorted-CSV task
                      graded by contains accepted an unsorted file.

    """

    type: Literal["tool_called", "tool_not_called", "state_path", "file_content", "file_lines"]
    tool: str | None = None
    path: str | None = None
    equals: str | int | float | bool | list | dict | None = None
    contains: str | None = None
    lines: list[str] | None = None
    weight: float = 1.0
    must_pass: bool = False


class FailInjection(BaseModel):
    """Chaos injection: force a sandbox tool to fail N times before succeeding.

    The runner calls sandbox.fail_next(tool, times) before the loop starts.
    This makes error-recovery tasks test actual recovery, not luck.
    """

    tool: str
    times: int = 1


class Task(BaseModel):
    """A single gauntlet task.

    Static tasks embed their prompt directly. Generated tasks (taskgen) build
    a Task programmatically and pass it to the runner the same way.
    """

    id: str
    suite: str
    description: str
    prompt: str
    system: str = "You are a helpful assistant."
    tools: list[ToolDef] = Field(default_factory=list)
    asserts: list[Assert] = Field(min_length=1)
    state_asserts: list[StateAssert] = Field(default_factory=list)
    fail_injections: list[FailInjection] = Field(default_factory=list)
    max_tokens: int = 4096
    timeout: float = 300.0
    repeats: int = 1  # >1 enables pass^k
    flaky: bool = False  # informational: repeats should be 3 when true
    no_think: bool = True  # disable think-mode per-request (token exhaustion guard)
    tier: str = "standard"  # difficulty tier: standard | hard
    max_turns: int = 8  # agent-loop turns (tool round-trips) allowed
    canary: str | None = None  # embedded canary GUID for generated tasks
    contamination_risk: Literal["none", "generated", "known"] = "none"

    @field_validator("repeats")
    @classmethod
    def _repeats_floor(cls, v: int) -> int:
        return max(1, v)

    @model_validator(mode="after")
    def _flaky_needs_repeats(self):
        # `flaky: true` used to promise repeats>=3 through a field validator that
        # returned its input unchanged (and could not see `flaky`, which is
        # declared after `repeats`). A flaky task measured once is a coin flip,
        # so the flag now actually raises the repeat count.
        if self.flaky and self.repeats < 3:
            self.repeats = 3
        return self

    def to_assert_dicts(self) -> list[dict]:
        out = []
        for a in self.asserts:
            d = {"type": a.type}
            if a.value is not None:
                d["value"] = a.value
            if a.values is not None:
                d["values"] = a.values
            if a.pattern is not None:
                d["pattern"] = a.pattern
            if a.schema_ is not None:
                d["schema"] = a.schema_
            if a.expr is not None:
                d["expr"] = a.expr
            if a.tests is not None:
                d["tests"] = a.tests
                d["timeout"] = a.timeout
            # weight/must_pass carry the rubric. Dropping them here silently
            # turned every weighted or gated assert into an unweighted one,
            # so a model that leaked the system prompt still earned full
            # partial credit. They must survive the YAML->scorer hop.
            d["weight"] = a.weight
            d["must_pass"] = a.must_pass
            out.append(d)
        return out


class Suite(BaseModel):
    name: str
    weight: float = 0.0
    tasks: list[Task] = Field(min_length=1)
