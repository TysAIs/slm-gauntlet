"""GOLD / NEAR-MISS fixtures for tasks/docintake.yaml.

Generated data module: the canonical copy lives in scripts/gen_docintake_tasks.py
(the fixture generator), which recomputes every ground truth from the fixture
data and asserts equality with tasks/docintake.yaml. Edit the generator, not
this file, and re-run it to refresh both.

Conventions (test_realworld_validity.py): GOLD is keyed by scenario id;
NEAR_MISS_EDIT is keyed by unit id and is either a (gold substring,
replacement) pair applied to the gold answer, or {{"files": ...}} for
file-state tasks whose near-miss is a wrong work product instead of a
wrong text answer. GOLD_FILES / NEAR_FILES are the write_file products.
SCENARIOS overrides the default scenario key (unit id up to the first "__")
for suites whose scenario ids nest deeper.
"""


GOLD = {'doc_invoice_record': '{"vendor": "Northwind Traders", "invoice_no": "INV-4471", "date": "2026-03-01", "total": 412.0, "currency": "USD"}', 'doc_receipt_lines': '{"lines": [{"item": "USB cable", "qty": 2, "unit_price": 9.5}, {"item": "Notebook A5", "qty": 3, "unit_price": 4.25}, {"item": "Pen set", "qty": 1, "unit_price": 6.0}], "total": 37.75}', 'doc_noisy_ocr': '{"vendor": "Harbor Studio", "invoice_no": "INV-2081", "date": "2026-03-04", "total": 96.5, "reference": null}', 'doc_form_fields': '{"full_name": "Ana Ruiz", "email": "ana.ruiz@example.com", "phone": "555-0142", "company": "Harbor Studio"}', 'doc_table_csv': 'name,age,city\nAna Ruiz,41,Denver\nBen Osei,35,Austin\nCleo Park,29,Miami', 'doc_redacted': '{"name": "Ana Ruiz", "email": null, "phone": "555-0142", "plan": "Pro annual"}', 'doc_locale_formats': '{"total": 1234.56, "date": "2026-03-04", "tax": 197.44}', 'doc_clause_find': '{"notice_period_days": 90, "renewal_years": 2}', 'doc_two_invoices': '[{"vendor": "Northwind Traders", "invoice_no": "INV-100", "total": 250.0}, {"vendor": "Harbor Studio", "invoice_no": "INV-200", "total": 80.5}]', 'doc_handwriting_transcript': '{"event": "appointment with Ana - project meeting", "time": "14:30", "room": "Room 4B"}', 'doc_totals_audit': '{"stated_total": 467.0, "computed_total": 457.0, "discrepancy": 10.0}'}

NEAR_MISS_EDIT = {'doc_invoice_record__vendor': ('Northwind Traders', 'Northwind'), 'doc_invoice_record__invoice_no': ('INV-4471', 'INV-4472'), 'doc_invoice_record__date': ('2026-03-01', '2026-03-02'), 'doc_invoice_record__total': ('"total": 412.0', '"total": 300.0'), 'doc_invoice_record__currency': ('"currency": "USD"', '"currency": "EUR"'), 'doc_receipt_lines__lines': ('"qty": 2', '"qty": 3'), 'doc_receipt_lines__total': ('"total": 37.75}', '"total": 19.0}'), 'doc_noisy_ocr__record': ('INV-2081', 'INV-2087'), 'doc_noisy_ocr__ambiguous_null': ('"reference": null', '"reference": "REF-100"'), 'doc_noisy_ocr__vendor': ('Harbor Studio', 'Harbor Studi0'), 'doc_form_fields__full_name': ('Ana Ruiz', 'Ana Ruiz Garcia'), 'doc_form_fields__email': ('ana.ruiz@example.com', 'ana.ruiz@example.net'), 'doc_form_fields__phone': ('555-0142', '555-0143'), 'doc_form_fields__company': ('Harbor Studio', 'Harbor Studios'), 'doc_table_csv': ('Ben Osei,35,Austin', 'Ben Osei,36,Austin'), 'doc_redacted__fields': ('"phone": "555-0142"', '"phone": "555-0143"'), 'doc_redacted__null_gate': ('"email": null', '"email": "ana.ruiz@example.com"'), 'doc_locale_formats__total': ('"total": 1234.56', '"total": 1.23'), 'doc_locale_formats__date': ('"date": "2026-03-04"', '"date": "2026-04-03"'), 'doc_locale_formats__tax': ('"tax": 197.44', '"tax": 197.45'), 'doc_clause_find__notice': ('"notice_period_days": 90', '"notice_period_days": 12'), 'doc_clause_find__renewal': ('"renewal_years": 2', '"renewal_years": 1'), 'doc_two_invoices__set': ('"total": 80.5', '"total": 250.0'), 'doc_two_invoices__count': (']', ', {"vendor": "Copy Co", "invoice_no": "INV-300", "total": 1.0}]'), 'doc_handwriting_transcript__fields': ('"time": "14:30"', '"time": "14:00"'), 'doc_handwriting_transcript__expansion': ('appointment with Ana - project meeting', 'appt with Ana - project mtg'), 'doc_totals_audit__stated': ('"stated_total": 467.0', '"stated_total": 457.0'), 'doc_totals_audit__computed': ('"computed_total": 457.0', '"computed_total": 467.0'), 'doc_totals_audit__discrepancy': ('"discrepancy": 10.0', '"discrepancy": 0.0')}

GOLD_FILES = {}

NEAR_FILES = {}

GOLD_CALLS = {}

SCENARIOS = {}
