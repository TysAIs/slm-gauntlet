"""Sandboxed tool implementations the agent loop can execute.

Tools run against local state only — a temp-dir file sandbox and pure-Python
mock services. Nothing here touches the network or the host filesystem beyond
its own temp dir. This is what makes the gauntlet measure *subagent* behavior:
the model's tool calls actually execute and their results flow back.
"""

from __future__ import annotations

import json
import math
import random
import re
import tempfile
import time
from pathlib import Path


class ToolSandbox:
    """Container for the sandbox root + mock service state for one task run."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.root = Path(tempfile.mkdtemp(prefix="gauntlet-sandbox-"))
        self.state: dict = {}  # per-run state (e.g., bookings created)
        self.call_log: list[dict] = []  # every tool invocation, in order
        self._fail_next: dict[str, int] = {}  # tool -> remaining forced failures

    def cleanup(self):
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    # ----- forced-failure control (error-recovery tests) -----
    def fail_next(self, tool: str, times: int = 1):
        self._fail_next[tool] = times

    # ----- executors -----
    def execute(self, name: str, arguments: dict) -> dict:
        """Run a tool. Returns a JSON-serializable dict result."""
        self.call_log.append({"tool": name, "args": arguments, "t": time.time()})
        if self._fail_next.get(name, 0) > 0:
            self._fail_next[name] -= 1
            return {"error": "internal_error", "message": f"{name}: upstream returned 500", "retry_ok": True}

        fn = getattr(self, f"_tool_{name}", None)
        if fn is None:
            return {"error": "unknown_tool", "message": f"no such tool: {name}"}
        try:
            return fn(**arguments)
        except TypeError as e:
            return {"error": "bad_arguments", "message": str(e)}

    # --- calculator: exact arithmetic the model must not do mentally ---
    def _tool_calculator(self, expression: str) -> dict:
        if not re.fullmatch(r"[0-9+\-*/().,%\s^]+", expression):
            return {"error": "invalid_expression", "message": "only arithmetic allowed"}
        expr = expression.replace("^", "**").replace(",", "")
        try:
            value = eval(expr, {"__builtins__": {}}, {"pi": math.pi})  # noqa: S307 — sandboxed regex above
        except ZeroDivisionError:
            return {"error": "division_by_zero"}
        except Exception as e:  # noqa: BLE001
            return {"error": "invalid_expression", "message": str(e)}
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return {"result": value}

    # --- fake flights API: booking workflow ---
    def _tool_search_flights(self, origin: str, destination: str, date: str) -> dict:
        flights = []
        for i in range(3):
            fid = f"FL{self.rng.randint(1000, 9999)}-{i}"
            flights.append(
                {
                    "flight_id": fid,
                    "origin": origin,
                    "destination": destination,
                    "date": date,
                    "price_usd": round(self.rng.uniform(80, 900), 2),
                    "seats_left": self.rng.randint(0, 9),
                }
            )
        return {"flights": flights}

    def _tool_reserve_flight(self, flight_id: str, passenger: dict) -> dict:
        if not passenger.get("name") or not passenger.get("passport"):
            return {"error": "missing_passenger_fields", "message": "passenger needs name and passport"}
        confirmation = f"CONF-{self.rng.randint(100000, 999999)}"
        self.state.setdefault("reservations", []).append(
            {"flight_id": flight_id, "confirmation": confirmation, **passenger}
        )
        return {"confirmation": confirmation, "status": "reserved", "flight_id": flight_id}

    def _tool_get_reservation(self, confirmation: str) -> dict:
        for r in self.state.get("reservations", []):
            if r["confirmation"] == confirmation:
                return {"found": True, "reservation": r}
        return {"found": False}

    def _tool_cancel_reservation(self, confirmation: str, reason: str) -> dict:
        res = self.state.get("reservations", [])
        for r in res:
            if r["confirmation"] == confirmation:
                r["status"] = "cancelled"
                r["cancel_reason"] = reason
                return {"cancelled": True, "confirmation": confirmation, "refund_days": 5}
        return {"cancelled": False, "error": "not_found"}

    # --- file sandbox: read/write inside self.root only ---
    def _tool_write_file(self, path: str, content: str) -> dict:
        target = (self.root / path).resolve()
        if not str(target).startswith(str(self.root)):
            return {"error": "path_escape", "message": "path outside sandbox"}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return {"written": str(path), "bytes": len(content)}

    def _tool_read_file(self, path: str) -> dict:
        target = (self.root / path).resolve()
        if not str(target).startswith(str(self.root)):
            return {"error": "path_escape"}
        if not target.exists():
            return {"error": "not_found", "path": path}
        return {"content": target.read_text(), "bytes": target.stat().st_size}

    def _tool_list_files(self, path: str = ".") -> dict:
        target = (self.root / path).resolve()
        if not str(target).startswith(str(self.root)):
            return {"error": "path_escape"}
        return {"files": sorted(str(p.relative_to(self.root)) for p in target.rglob("*") if p.is_file())}

    def _tool_get_time(self, timezone: str = "UTC") -> dict:
        return {"timezone": timezone, "unix": int(time.time()), "note": "mock clock"}

    def _tool_database_query(self, table: str, filters: dict | None = None) -> dict:
        """Mock records service used by retrieval/data tasks."""
        rows = self.state.setdefault(f"db_{table}", [])
        if filters:
            keys = list(filters.keys())
            rows = [r for r in rows if all(r.get(k) == filters[k] for k in keys)]
        return {"rows": rows, "count": len(rows)}


def tools_for(names: list[str]) -> list[dict]:
    """Build OpenAI tool specs for a subset of sandbox tools."""
    SPECS = {
        "calculator": ("Evaluate an arithmetic expression.", {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. (2+3)*4"}},
            "required": ["expression"],
        }),
        "search_flights": ("Search flights.", {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["origin", "destination", "date"],
        }),
        "reserve_flight": ("Reserve a flight for a passenger.", {
            "type": "object",
            "properties": {
                "flight_id": {"type": "string"},
                "passenger": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "passport": {"type": "string"}},
                    "required": ["name", "passport"],
                },
            },
            "required": ["flight_id", "passenger"],
        }),
        "get_reservation": ("Look up a reservation by confirmation code.", {
            "type": "object",
            "properties": {"confirmation": {"type": "string"}},
            "required": ["confirmation"],
        }),
        "cancel_reservation": ("Cancel a reservation.", {
            "type": "object",
            "properties": {"confirmation": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["confirmation", "reason"],
        }),
        "write_file": ("Write a file in the workspace.", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        }),
        "read_file": ("Read a file from the workspace.", {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }),
        "list_files": ("List files in the workspace.", {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        }),
        "get_time": ("Get the current time.", {
            "type": "object",
            "properties": {"timezone": {"type": "string", "default": "UTC"}},
        }),
        "database_query": ("Query the records database.", {
            "type": "object",
            "properties": {"table": {"type": "string"}, "filters": {"type": "object"}},
            "required": ["table"],
        }),
    }
    out = []
    for n in names:
        if n not in SPECS:
            raise ValueError(f"unknown sandbox tool: {n}")
        desc, params = SPECS[n]
        out.append({"type": "function", "function": {"name": n, "description": desc, "parameters": params}})
    return out


def parse_tool_call_name(raw: str) -> str | None:
    """Extract a bare tool name from common small-model call formats.

    Small models emit tool calls in varied shapes; the agent loop normalizes:
    - OpenAI native: handled by client
    - Text forms: "tool: name", "<tool_call>name", 'name(...)', '{"name": ...}'
    """
    raw = raw.strip()
    m = re.search(r"<tool_call>\s*([A-Za-z_][A-Za-z0-9_]*)", raw)
    if m:
        return m.group(1)
    m = re.match(r"(?:tool|function)\s*[:=]\s*([A-Za-z_][A-Za-z0-9_]*)", raw)
    if m:
        return m.group(1)
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", raw)
    if m:
        return m.group(1)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "name" in obj:
            return obj["name"]
    except (ValueError, TypeError):
        pass
    return None
