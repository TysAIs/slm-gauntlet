"""GOLD / NEAR-MISS fixtures for tasks/summarize.yaml.

Generated data module: the canonical copy lives in scripts/gen_summarize_tasks.py
(the fixture generator), which recomputes every ground truth from the fixture
data and asserts equality with tasks/summarize.yaml. Edit the generator, not
this file, and re-run it to refresh both.

Conventions (test_realworld_validity.py): GOLD is keyed by scenario id;
NEAR_MISS_EDIT is keyed by unit id and is either a (gold substring,
replacement) pair applied to the gold answer, or {{"files": ...}} for
file-state tasks whose near-miss is a wrong work product instead of a
wrong text answer. GOLD_FILES / NEAR_FILES are the write_file products.
SCENARIOS overrides the default scenario key (unit id up to the first "__")
for suites whose scenario ids nest deeper.
"""


GOLD = {'sum_meeting_decisions': '["Decision: the launch date moves to 2026-04-15.", "Decision: the support rota gains a weekend shift.", "Decision: the legacy export feature is retired on 2026-05-01."]', 'sum_sentence_select': '["S2", "S4", "S7"]', 'sum_headline_pick': 'H1', 'sum_brief_coverage': '- Database migration finished on 2026-03-04, ahead of plan.\n- Ana Ruiz leads the remaining API work.\n- Risk: the payment gateway sandbox tests failed twice.\n- Budget spent so far: 61 percent.\n- Next milestone: beta release on 2026-03-20.', 'sum_tldr_lock': 'The library extends its opening hours from April, closing at 21:00 on weekdays and opening on Sundays from 10:00 to 14:00, after 1,240 residents asked for longer hours.', 'sum_multidoc_status': '{"api": "done", "web": "in progress", "mobile": "blocked", "overall": "at risk"}', 'sum_changelog': '[{"field": "timeout", "from": "30 seconds", "to": "60 seconds"}, {"field": "theme", "from": "light", "to": "dark"}]', 'sum_speaker_map': '{"Ana": "support", "Ben": "oppose", "Cleo": "neutral"}', 'sum_numbers_guard': 'Revenue reached 1.25 million, up from 1.10 million last quarter, and churn stayed at 3.5 percent. The team grew to 42 people, and the office lease runs until 2027.', 'sum_thread_catchup': '{"topic": "staging release and the blank login page", "decision": "we hold the release until the login page is fixed", "open_questions": 1}'}

NEAR_MISS_EDIT = {'sum_meeting_decisions__set': ('Decision: the support rota gains a weekend shift.', 'Decision: the roadmap is approved.'), 'sum_meeting_decisions__count': (']', ', "Decision: the roadmap is approved."]'), 'sum_sentence_select__set': ('"S7"', '"S3"'), 'sum_sentence_select__count': (']', ', "S3"]'), 'sum_headline_pick': ('H1', 'H2'), 'sum_brief_coverage': ('beta release on 2026-03-20.', 'beta release on 2026-03-27.'), 'sum_tldr_lock': ('longer hours.', 'longer hours in a survey by 900 residents.'), 'sum_multidoc_status__api': ('"api": "done"', '"api": "in progress"'), 'sum_multidoc_status__web': ('"web": "in progress"', '"web": "done"'), 'sum_multidoc_status__mobile': ('"mobile": "blocked"', '"mobile": "in progress"'), 'sum_multidoc_status__overall': ('"overall": "at risk"', '"overall": "on track"'), 'sum_changelog__set': ('"to": "dark"', '"to": "blue"'), 'sum_changelog__count': (']', ', {"field": "retries", "from": "2", "to": "2"}]'), 'sum_speaker_map__ana': ('"Ana": "support"', '"Ana": "neutral"'), 'sum_speaker_map__ben': ('"Ben": "oppose"', '"Ben": "support"'), 'sum_speaker_map__cleo': ('"Cleo": "neutral"', '"Cleo": "oppose"'), 'sum_numbers_guard': ('churn stayed at 3.5 percent', 'churn fell to 2.9 percent'), 'sum_thread_catchup__decision': ('we hold the release until the login page is fixed', 'we ship the release on Friday'), 'sum_thread_catchup__open': ('"open_questions": 1', '"open_questions": 0'), 'sum_thread_catchup__topic': ('staging release and the blank login page', 'weekend plans and photos')}

GOLD_FILES = {}

NEAR_FILES = {}

GOLD_CALLS = {}

SCENARIOS = {}
