#!/usr/bin/env python3
"""Build a probe task directory: ONLY the 0.5.1 tasks whose prompt changed.

Why this exists: re-authoring a task means guessing how hard it is, and the
sweep that would answer that costs ~12 hours. A probe run answers it in minutes:
the changed tasks are copied into a directory outside `tasks/` (so `--suite all`
never mixes them in — the same rule `--tasks-dir` documents), then
`scripts/pve_sweep.py --tasks-dir tasks_probe --manifest <probe manifest>`
measures them on a few configurations across the score range.

The list is explicit on purpose: a probe that silently covered a different set
of tasks than the one being authored would be worse than no probe.

  python3 scripts/build_probe_dir.py            # write tasks_probe/
  python3 scripts/build_probe_dir.py --check    # list what would be written
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Scenario prefixes (all units of a scenario are probed together: they share one prompt).
PROBE_SCENARIOS = {
    "rw_expense_split",
    "rw_shipping_quote",
    "rw_ticket_priority",
    "rw_payroll_net",
    "rw_med_dose",
    "rw_lease_proration",
    "rw_room_conflicts",
    "rw_invoice_deadline",
    "rw_warranty_expiry",
    "hif_letter_ban_long",
    "hif_negation_lock",
    "struct_nested_json",
    "struct_json_repair",
    "struct_regex_gen",
    "struct_strict_json_only",
    "code_bugfix_off_by_one",
    "adv_impersonation",
    "adv_tool_abuse",
    "tool_arith_no_tool",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "tasks_probe"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)

    picked: dict[str, list[dict]] = {}
    for path in sorted((ROOT / "tasks").glob("*.yaml")):
        rows = [t for t in yaml.safe_load(path.read_text()) or []
                if str(t["id"]).split("__")[0] in PROBE_SCENARIOS]
        if rows:
            picked[path.name] = rows

    total = sum(len(v) for v in picked.values())
    print(f"probe set: {total} tasks in {len(picked)} file(s)")
    for name, rows in picked.items():
        print(f"  {name}: {len(rows)}")
        for t in rows:
            print(f"    {t['id']}")
    missing = PROBE_SCENARIOS - {str(t["id"]).split("__")[0] for rows in picked.values() for t in rows}
    if missing:
        print(f"! probe scenarios with no task in tasks/: {sorted(missing)}", file=sys.stderr)
        return 1
    if args.check:
        return 0

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name, rows in picked.items():
        (out / name).write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=200))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
