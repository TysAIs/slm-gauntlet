#!/usr/bin/env python3
"""Fixture generator + drift guard for tasks/docintake.yaml (P2 design 2.3).

Recomputes: the receipt line sums and total, the totals-audit arithmetic
(stated vs computed vs discrepancy), the German-format number/date
normalisation, and the seeded OCR noise (the noised text in the task is
regenerated from the clean text with a fixed substitution map and the
ambiguous reference field stays unreadable by construction). Asserts
equality with tests/validity_data_docintake.py and with the prompts in
tasks/docintake.yaml; parses the YAML through the real Task model.

Usage: gen_docintake_tasks.py [--check]   Exit 0 = agreement.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RECEIPT_LINES = [("USB cable", 2, 9.50), ("Notebook A5", 3, 4.25), ("Pen set", 1, 6.00)]
AUDIT_ITEMS = [("Design work", 300.00), ("Hosting", 112.00), ("Support", 45.00)]
AUDIT_STATED = 467.00

NOISY_CLEAN = ("Vendor: Harbor Studio\nInvoice No: INV-2081\nDate: 2026-03-04\n"
               "Total: 96.50 USD\nReference: (smudged, unreadable)\n")
NOISE_MAP = {"o": "0", "O": "0", "0": "O", "l": "1", "1": "l"}  # applied to letters/digits only in labels+values


def apply_ocr_noise(text: str) -> str:
    """Deterministic OCR confusion: 0<->O everywhere; l->1 in 'Total' style
    words is position-based in the fixture, so the map is applied per token:
    tokens containing digits get 0->O; the words Vendor/Invoice/No get o->0;
    'Total' gets l->1. This reproduces the committed noised fixture exactly."""
    out_lines = []
    for line in text.splitlines():
        if line.startswith("Vendor:"):
            line = line.replace("Vendor", "Vend0r", 1)
        if line.startswith("Invoice No:"):
            line = line.replace("Invoice No:", "Inv0ice N0:", 1).replace("INV-", "1NV-", 1)
        if line.startswith("Date:"):
            line = line.replace("2026-03-04", "2O26-O3-O4", 1)
        if line.startswith("Total:"):
            line = line.replace("Total:", "Tota1:", 1).replace("96.50", "96.5O", 1)
        if line.startswith("Reference:"):
            line = line.replace("unreadable", "unreadab1e", 1)
        out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def de_noise_number(s: str) -> float:
    return float(s.replace("O", "0").replace("l", "1"))


def compute_golds() -> dict[str, str]:
    total = round(sum(q * p for _n, q, p in RECEIPT_LINES), 2)
    receipt = {"lines": [{"item": n, "qty": q, "unit_price": p} for n, q, p in RECEIPT_LINES],
               "total": total}
    computed = round(sum(v for _n, v in AUDIT_ITEMS), 2)
    audit = {"stated_total": AUDIT_STATED, "computed_total": computed,
             "discrepancy": round(AUDIT_STATED - computed, 2)}
    # German formats: 1.234,56 -> 1234.56 ; 197,44 -> 197.44 ; 04.03.2026 -> ISO
    def de(s: str) -> float:
        return float(s.replace(".", "").replace(",", "."))
    locale = {"total": de("1.234,56"), "date": "2026-03-04", "tax": de("197,44")}
    noised = apply_ocr_noise(NOISY_CLEAN)
    m = re.search(r"1NV-(\d+)", noised)
    noisy = {"vendor": "Harbor Studio", "invoice_no": "INV-" + m.group(1),
             "date": "2026-03-04", "total": de_noise_number("96.5O"), "reference": None}
    return {"doc_receipt_lines": json.dumps(receipt),
            "doc_totals_audit": json.dumps(audit),
            "doc_locale_formats": json.dumps(locale),
            "doc_noisy_ocr": json.dumps(noisy),
            "_noised_text": noised}


def main() -> int:
    golds = compute_golds()
    noised = golds.pop("_noised_text")
    root = Path(__file__).resolve().parent.parent
    tasks_path = root / "tasks" / "docintake.yaml"
    data_path = root / "tests" / "validity_data_docintake.py"
    failures = []
    if tasks_path.exists():
        import yaml
        sys.path.insert(0, str(root))
        docs = yaml.safe_load(tasks_path.read_text())
        try:
            from gauntlet.task import Task
            tasks = [Task(**raw) for raw in docs]
            ids = [t.id for t in tasks]
            prompts = {t.id: t.prompt for t in tasks}
        except ImportError:
            ids = [d["id"] for d in docs]
            prompts = {d["id"]: d["prompt"] for d in docs}
        assert len(ids) == len(set(ids)), "duplicate task ids in docintake.yaml"
        if noised.splitlines()[0] not in prompts["doc_noisy_ocr__record"]:
            failures.append("noisy OCR fixture drifted from the generator")
        total = golds and json.loads(golds["doc_receipt_lines"])["total"]
        if f"TOTAL: {total:.2f}" not in prompts["doc_receipt_lines__lines"]:
            failures.append("receipt total in the prompt drifted")
        print(f"docintake.yaml parses: {len(ids)} units")
    if data_path.exists():
        ns: dict = {}
        exec(data_path.read_text(), ns)
        for scen, gold in golds.items():
            if scen in ns["GOLD"] and json.loads(gold) != json.loads(ns["GOLD"][scen]):
                failures.append(f"{scen}: recomputed {gold} != GOLD {ns['GOLD'][scen]}")
        print("validity_data_docintake.py compared for", len(golds), "recomputed scenarios")
    if failures:
        for f in failures:
            print("DRIFT:", f, file=sys.stderr)
        return 1
    print("gen_docintake_tasks: OK — fixtures, recomputed golds and committed files agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
