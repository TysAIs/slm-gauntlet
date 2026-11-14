"""GOLD / NEAR-MISS fixtures for tasks/classify.yaml.

Generated data module: the canonical copy lives in scripts/gen_classify_tasks.py
(the fixture generator), which recomputes every ground truth from the fixture
data and asserts equality with tasks/classify.yaml. Edit the generator, not
this file, and re-run it to refresh both.

Conventions (test_realworld_validity.py): GOLD is keyed by scenario id;
NEAR_MISS_EDIT is keyed by unit id and is either a (gold substring,
replacement) pair applied to the gold answer, or {{"files": ...}} for
file-state tasks whose near-miss is a wrong work product instead of a
wrong text answer. GOLD_FILES / NEAR_FILES are the write_file products.
SCENARIOS overrides the default scenario key (unit id up to the first "__")
for suites whose scenario ids nest deeper.
"""


GOLD = {'cr_route4': 'legal', 'cr_multilabel': '["hiring", "pricing", "support"]', 'cr_priority_ordinal': 'urgent', 'cr_phish_verdict': '{"verdict": "phish", "reason_code": "lookalike_domain"}', 'cr_lang_id': 'fr', 'cr_voice_intent': 'set_timer', 'cr_pii_types': '["email", "name", "phone"]', 'cr_doc_type': 'invoice', 'cr_hier_route': '{"l1": "support", "l2": "technical"}', 'cr_abstain': 'other', 'cr_abstain_control': 'shipping', 'cr_batch_table': '{"i1": "billing", "i2": "shipping", "i3": "technical", "i4": "account", "i5": "billing", "i6": "shipping", "i7": "technical", "i8": "account", "i9": "other", "i10": "billing"}', 'cr_boundary_pairs__b1': 'legal', 'cr_boundary_pairs__b2': 'billing', 'cr_boundary_pairs__b3': 'bug', 'cr_boundary_pairs__b4': 'question'}

NEAR_MISS_EDIT = {'cr_route4': ('legal', 'hr'), 'cr_multilabel__set': ('"support"', '"event"'), 'cr_multilabel__hiring': ('"hiring", ', ''), 'cr_multilabel__pricing': ('"pricing", ', ''), 'cr_multilabel__support': (', "support"', ''), 'cr_multilabel__no_launch': ('["hiring"', '["launch", "hiring"'), 'cr_multilabel__no_event': ('["hiring"', '["event", "hiring"'), 'cr_priority_ordinal': ('urgent', 'high'), 'cr_phish_verdict__verdict': ('"verdict": "phish"', '"verdict": "legit"'), 'cr_phish_verdict__reason': ('lookalike_domain', 'urgency_pressure'), 'cr_lang_id': ('fr', 'es'), 'cr_voice_intent': ('set_timer', 'play_music'), 'cr_pii_types__set': ('"phone"', '"ssn"'), 'cr_pii_types__no_values': ('["email"', '["ana.ruiz@example.com", "email"'), 'cr_doc_type': ('invoice', 'report'), 'cr_hier_route__pair': ('"l2": "technical"', '"l2": "billing"'), 'cr_hier_route__l1': ('"l1": "support"', '"l1": "sales"'), 'cr_abstain': ('other', 'billing'), 'cr_abstain_control': ('shipping', 'other'), 'cr_boundary_pairs__b1': ('legal', 'hr'), 'cr_boundary_pairs__b2': ('billing', 'account'), 'cr_boundary_pairs__b3': ('bug', 'feature'), 'cr_boundary_pairs__b4': ('question', 'complaint'), 'cr_batch_table__i1': ('"i1": "billing"', '"i1": "account"'), 'cr_batch_table__i2': ('"i2": "shipping"', '"i2": "other"'), 'cr_batch_table__i3': ('"i3": "technical"', '"i3": "support"'), 'cr_batch_table__i4': ('"i4": "account"', '"i4": "billing"'), 'cr_batch_table__i5': ('"i5": "billing"', '"i5": "account"'), 'cr_batch_table__i6': ('"i6": "shipping"', '"i6": "other"'), 'cr_batch_table__i7': ('"i7": "technical"', '"i7": "support"'), 'cr_batch_table__i8': ('"i8": "account"', '"i8": "billing"'), 'cr_batch_table__i9': ('"i9": "other"', '"i9": "billing"'), 'cr_batch_table__i10': ('"i10": "billing"', '"i10": "account"')}

GOLD_FILES = {}

NEAR_FILES = {}

GOLD_CALLS = {}

SCENARIOS = {'cr_boundary_pairs__b1': 'cr_boundary_pairs__b1', 'cr_boundary_pairs__b2': 'cr_boundary_pairs__b2', 'cr_boundary_pairs__b3': 'cr_boundary_pairs__b3', 'cr_boundary_pairs__b4': 'cr_boundary_pairs__b4'}
