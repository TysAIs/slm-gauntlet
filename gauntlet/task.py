"""Task definition models (YAML schema) — pydantic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ToolDef(BaseModel):
    """OpenAI-format function tool definition."""
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)  # JSON schema

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


class Assert(BaseModel):
    type: Literal["exact_match", "contains_all", "contains_any", "regex", "json_schema", "predicate"]
    value: str | None = None
    values: list[str] | None = None
    pattern: str | None = None
    schema_: dict | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


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
    max_tokens: int = 1024
    timeout: float = 300.0
    repeats: int = 1  # >1 enables pass^k
    flaky: bool = False  # informational: repeats should be 3 when true
    max_turns: int = 8  # agent-loop turns (tool round-trips) allowed
    canary: str | None = None  # embedded canary GUID for generated tasks
    contamination_risk: Literal["none", "generated", "known"] = "none"

    @field_validator("repeats")
    @classmethod
    def _flaky_needs_repeats(cls, v: int, info) -> int:
        return v

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
            out.append(d)
        return out


class Suite(BaseModel):
    name: str
    weight: float = 0.0
    tasks: list[Task] = Field(min_length=1)
