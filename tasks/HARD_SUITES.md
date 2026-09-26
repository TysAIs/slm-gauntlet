"""v0.3 hard suites: instruction-hard + tooluse-hard + structured-hard tasks.

These are the limits-testing additions from ROADMAP-v0.3:
- instruction-hard: stacked verifiable constraints (IFBench-style), conflict
  hierarchy, multi-turn persistence, exact counts, verbatim copy
- structured-hard: strict JSON schema with decoys
- tooluse-hard: tool-result validation + self-repair, unknown-tool abstention

All graded deterministically (regex/jsonschema/assertion) — no LLM judge.
Task format matches tasks/*.yaml (Assert schema used by gauntlet.runner).
"""
