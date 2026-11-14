"""GOLD / NEAR-MISS fixtures for tasks/calendar.yaml.

Generated data module: the canonical copy lives in scripts/gen_calendar_tasks.py
(the fixture generator), which recomputes every ground truth from the fixture
data and asserts equality with tasks/calendar.yaml. Edit the generator, not
this file, and re-run it to refresh both.

Conventions (test_realworld_validity.py): GOLD is keyed by scenario id;
NEAR_MISS_EDIT is keyed by unit id and is either a (gold substring,
replacement) pair applied to the gold answer, or {{"files": ...}} for
file-state tasks whose near-miss is a wrong work product instead of a
wrong text answer. GOLD_FILES / NEAR_FILES are the write_file products.
SCENARIOS overrides the default scenario key (unit id up to the first "__")
for suites whose scenario ids nest deeper.
"""


GOLD = {'cal_event_extract': '{"title": "Team lunch with Ana Ruiz", "date": "2026-03-12", "start": "12:30", "location": "Harbor Cafe"}', 'cal_tz_convert': '{"utc": "2026-03-10 14:00", "new_york": "2026-03-10 10:00"}', 'cal_recurrence': '{"rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=6", "first_three": ["2026-03-02", "2026-03-09", "2026-03-16"]}', 'cal_free_slot': '{"start": "12:00", "end": "13:00"}', 'cal_conflict_find': '[["A", "B"], ["C", "D"]]', 'cal_reschedule_cascade': '{"X": ["14:00", "15:00"], "Y": ["15:00", "16:00"], "Z": ["16:30", "17:30"]}', 'cal_deadlines': '{"report": "2026-03-13", "slides": "2026-03-15", "invoice": "2026-03-20"}', 'cal_duration_math': 'MINUTES: 150', 'cal_reminder_list': '["2026-03-11 15:00", "2026-03-12 14:00", "2026-03-12 14:45"]', 'cal_vague_bounded': '{"date": "2026-03-02", "start": "09:00"}'}

NEAR_MISS_EDIT = {'cal_event_extract__title': ('Team lunch with Ana Ruiz', 'Team lunch'), 'cal_event_extract__date': ('2026-03-12', '2026-03-13'), 'cal_event_extract__start': ('"start": "12:30"', '"start": "12:00"'), 'cal_event_extract__location': ('Harbor Cafe', 'Harbor Office'), 'cal_tz_convert__utc': ('"utc": "2026-03-10 14:00"', '"utc": "2026-03-10 15:00"'), 'cal_tz_convert__new_york': ('"new_york": "2026-03-10 10:00"', '"new_york": "2026-03-10 09:00"'), 'cal_recurrence__rrule': ('COUNT=6', 'COUNT=4'), 'cal_recurrence__dates': ('"2026-03-16"', '"2026-03-15"'), 'cal_free_slot': ('"start": "12:00"', '"start": "10:30"'), 'cal_conflict_find__set': ('["C", "D"]', '["D", "E"]'), 'cal_conflict_find__count': (']]', '], ["D", "E"]]'), 'cal_reschedule_cascade__y': ('"Y": ["15:00", "16:00"]', '"Y": ["14:00", "15:00"]'), 'cal_reschedule_cascade__z': ('"Z": ["16:30", "17:30"]', '"Z": ["16:00", "17:00"]'), 'cal_reschedule_cascade__x': ('"X": ["14:00", "15:00"]', '"X": ["10:00", "11:00"]'), 'cal_deadlines__report': ('"report": "2026-03-13"', '"report": "2026-03-14"'), 'cal_deadlines__slides': ('"slides": "2026-03-15"', '"slides": "2026-03-08"'), 'cal_deadlines__invoice': ('"invoice": "2026-03-20"', '"invoice": "2026-03-21"'), 'cal_duration_math': ('MINUTES: 150', 'MINUTES: 130'), 'cal_reminder_list': ('"2026-03-12 14:45"', '"2026-03-12 14:30"'), 'cal_vague_bounded': ('"date": "2026-03-02"', '"date": "2026-03-09"')}

GOLD_FILES = {}

NEAR_FILES = {}

GOLD_CALLS = {}

SCENARIOS = {}
