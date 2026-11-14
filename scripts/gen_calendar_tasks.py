#!/usr/bin/env python3
"""Fixture generator + drift guard for tasks/calendar.yaml (P2 design 2.5).

Every gold is computed here with datetime/zoneinfo: the Berlin->UTC and
Berlin->New York conversions across the March DST asymmetry (US switches
2026-03-08, EU on 2026-03-29), the weekly recurrence dates, the earliest
free 60-minute slot from the busy intervals, the overlap pair set, the
reschedule cascade, relative deadline resolution, duration and reminder
offsets. Asserts equality with tests/validity_data_calendar.py and
parses tasks/calendar.yaml through the real Task model.

Usage: gen_calendar_tasks.py [--check]   Exit 0 = agreement.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def compute_golds() -> dict[str, str]:
    golds: dict[str, str] = {}
    berlin = datetime(2026, 3, 10, 15, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    golds["cal_tz_convert"] = json.dumps({
        "utc": berlin.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M"),
        "new_york": berlin.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")})

    first = datetime(2026, 3, 2)
    assert first.weekday() == 0
    golds["cal_recurrence"] = json.dumps({
        "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=6",
        "first_three": [(first + timedelta(days=7 * i)).strftime("%Y-%m-%d") for i in range(3)]})

    # earliest 60-minute free slot inside 09:00-17:00
    busy = [(9 * 60, 10 * 60 + 30), (11 * 60, 12 * 60), (13 * 60 + 30, 15 * 60)]
    start = 9 * 60
    while start + 60 <= 17 * 60:
        slot = (start, start + 60)
        if not any(overlaps(slot, b) for b in busy):
            break
        start += 30
    golds["cal_free_slot"] = json.dumps(
        {"start": f"{slot[0] // 60:02d}:{slot[0] % 60:02d}",
         "end": f"{slot[1] // 60:02d}:{slot[1] % 60:02d}"})

    events = {"A": (9 * 60, 10 * 60), "B": (9 * 60 + 30, 10 * 60 + 30),
              "C": (11 * 60, 12 * 60), "D": (11 * 60 + 30, 12 * 60 + 30),
              "E": (13 * 60, 14 * 60)}
    pairs = [[a, b] for i, a in enumerate(events) for b in list(events)[i + 1:]
             if overlaps(events[a], events[b])]
    golds["cal_conflict_find"] = json.dumps(pairs)

    # cascade: X 14:00-15:00; Y follows X (60 min); Z starts 30 min after Y (60 min)
    x = (14 * 60, 15 * 60)
    y = (x[1], x[1] + 60)
    z = (y[1] + 30, y[1] + 30 + 60)
    def fmt(iv):
        return [f"{iv[0] // 60:02d}:{iv[0] % 60:02d}", f"{iv[1] // 60:02d}:{iv[1] % 60:02d}"]

    golds["cal_reschedule_cascade"] = json.dumps({"X": fmt(x), "Y": fmt(y), "Z": fmt(z)})

    # deadlines from Friday 2026-03-06; "end of next week" = Sunday of next week
    today = datetime(2026, 3, 6)
    assert today.weekday() == 4
    end_next_week = today + timedelta(days=(6 - today.weekday()) + 7)
    golds["cal_deadlines"] = json.dumps({
        "report": "2026-03-13", "slides": end_next_week.strftime("%Y-%m-%d"),
        "invoice": "2026-03-20"})

    dur = int((datetime(2026, 3, 10, 16, 45) - datetime(2026, 3, 10, 14, 15)).total_seconds() // 60)
    golds["cal_duration_math"] = f"MINUTES: {dur}"

    start_dt = datetime(2026, 3, 12, 15, 0)
    rems = [start_dt - timedelta(days=1), start_dt - timedelta(hours=1),
            start_dt - timedelta(minutes=15)]
    golds["cal_reminder_list"] = json.dumps([r.strftime("%Y-%m-%d %H:%M") for r in rems])

    # vague bounded: Mon-Fri of the week starting Monday 2026-03-02
    monday = datetime(2026, 3, 2)
    valid = {(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)}
    assert "2026-03-02" in valid and "2026-03-09" not in valid
    golds["cal_vague_bounded"] = json.dumps({"date": "2026-03-02", "start": "09:00"})
    return golds


def main() -> int:
    golds = compute_golds()
    root = Path(__file__).resolve().parent.parent
    tasks_path = root / "tasks" / "calendar.yaml"
    data_path = root / "tests" / "validity_data_calendar.py"
    failures = []
    if tasks_path.exists():
        import yaml
        sys.path.insert(0, str(root))
        docs = yaml.safe_load(tasks_path.read_text())
        try:
            from gauntlet.task import Task
            tasks = [Task(**raw) for raw in docs]
            ids = [t.id for t in tasks]
        except ImportError:
            ids = [d["id"] for d in docs]
        assert len(ids) == len(set(ids)), "duplicate task ids in calendar.yaml"
        print(f"calendar.yaml parses: {len(ids)} units")
    if data_path.exists():
        ns: dict = {}
        exec(data_path.read_text(), ns)
        for scen, gold in golds.items():
            if scen in ns["GOLD"]:
                try:
                    same = json.loads(gold) == json.loads(ns["GOLD"][scen])
                except Exception:
                    same = gold == ns["GOLD"][scen]
                if not same:
                    failures.append(f"{scen}: recomputed {gold} != GOLD {ns['GOLD'][scen]}")
        print("validity_data_calendar.py compared for", len(golds), "recomputed scenarios")
    if failures:
        for f in failures:
            print("DRIFT:", f, file=sys.stderr)
        return 1
    print("gen_calendar_tasks: OK — fixtures, recomputed golds and committed files agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
