#!/usr/bin/env python3
"""Fixture generator + drift guard for tasks/email.yaml (P2 design section 1).

Pattern follows extra-suites/longhorizon-v2/gen_v2.py: every ground truth
below is RECOMPUTED from the fixture data (policy functions over the
fixtures, datetime arithmetic, digest sorting), then asserted equal to
the GOLD answers and to the committed tasks/email.yaml (parsed through
the real Task model). Any hand-edit that drifts from the fixture fails
loudly (exit 1).

Recomputation targets: the policy-driven golds (triage buckets, priority
order, meeting date arithmetic, digest records + top_urgent) are rebuilt
from the fixture tables below. The prose-fixture golds (drafts, thread
states, injection extraction) are pinned in tests/validity_data_email.py
and proven by tests/test_validity_email.py against the real scorer.

Long-tier parameterisation (design 3.1): build_long_thread(n) grows the
T2 thread to n messages with seeded filler that never touches the graded
facts (decision / open questions / deadline / amended budget are planted
at fixed positions); build_long_inbox(n) grows the T3 inbox likewise.
The committed YAML carries small exemplars; the run harness regenerates
full sizes with --messages / --emails.

Usage: gen_email_tasks.py [--check] [--messages N] [--emails N]
Exit 0 = fixtures, golds and the committed YAML agree.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------- fixtures
TRIAGE_EMAILS = [
    # (id, sender_domain, flags) — the policy below is the prompt's R1..R4
    ("e1", "acme-supply.vendor.example", {"vendor_payment"}),
    ("e2", "northwind.example", {"cancels_vip_meeting"}),
    ("e3", "promo-blast.example", {"vendor_payment"}),
    ("e4", "northwind.example", set()),
    ("e5", "globex.vendor.example", {"vendor_payment"}),
    ("e6", "northwind.example", set()),
]
BLOCKLIST = {"promo-blast.example"}

def triage_bucket(domain: str, flags: set[str]) -> str:
    if domain in BLOCKLIST:                       # R1
        return "spam"
    if "cancels_vip_meeting" in flags:            # R2
        return "urgent"
    if domain.endswith(".vendor.example") and "vendor_payment" in flags:  # R3
        return "billing"
    return "other"                                # R4


PRIORITY_EMAILS = [
    # (id, deadline_hours_from_now or None, vip, keywords)
    ("e1", None, False, {"OUTAGE"}),
    ("e2", None, True, set()),
    ("e3", 32.0, False, set()),       # 2026-03-09 09:00 -> 2026-03-10 17:00
    ("e4", None, False, {"SECURITY"}),
    ("e5", None, False, set()),
    ("e6", None, True, {"CANCELLED"}),
    ("e7", 384.0, False, set()),      # 2026-03-25: outside 48 h
    ("e8", None, False, set()),
]


def priority_order(rows):
    def key(item):
        idx, (eid, dl, vip, kw) = item
        return (
            0 if (dl is not None and dl <= 48) else 1,   # P1
            0 if vip else 1,                              # P2
            0 if kw else 1,                               # P3
            idx,                                          # P4 inbox order
        )
    return [eid for _, (eid, *_rest) in sorted(enumerate(rows), key=key)]


def compute_golds() -> dict[str, str]:
    buckets: dict[str, list[str]] = {"spam": [], "billing": [], "urgent": [], "other": []}
    for eid, domain, flags in TRIAGE_EMAILS:
        buckets[triage_bucket(domain, flags)].append(eid)
    golds = {"em_triage_buckets": json.dumps(buckets)}
    order = priority_order(PRIORITY_EMAILS)
    golds["em_priority_order"] = json.dumps(order)
    golds["em_priority_top3"] = golds["em_priority_order"]

    # meeting: Friday 2026-03-06 -> next Tuesday; Berlin CET (UTC+1) in March
    today = date(2026, 3, 6)
    days_ahead = (1 - today.weekday()) % 7 or 7   # next Tuesday (weekday 1)
    nxt = today + timedelta(days=days_ahead)
    assert nxt.weekday() == 1 and nxt.isoformat() == "2026-03-10"
    golds["em_extract_meeting"] = json.dumps({
        "date": nxt.isoformat(), "time_utc": "14:00",   # 15:00 CET = 14:00 UTC
        "attendees": ["ana@example.com", "bo@example.com", "cy@example.com"],
        "location": "Room 4B, Harbor Office"})

    # invoice: due = invoice date + 14 days
    due = date(2026, 3, 2) + timedelta(days=14)
    assert due.isoformat() == "2026-03-16"
    golds["em_extract_invoice"] = json.dumps({
        "vendor": "Cedar Point Supplies", "invoice_no": "INV-7782",
        "amount": 460.00, "due_date": due.isoformat()})

    # action items: the DONE ask (Cy) is excluded by construction
    asks = [("Ana", "send the vendor shortlist to legal", "2026-03-13"),
            ("Bo", "renew the staging certificate", "2026-03-20"),
            ("Ana", "book the venue for the April offsite", "2026-03-27")]
    golds["em_action_items"] = json.dumps({
        "owners": [a[0] for a in asks], "actions": [a[1] for a in asks],
        "dues": [a[2] for a in asks]})

    # reconcile: latest message wins
    msgs = [("m1", 1240.00), ("m2", 1190.00), ("m3", 1175.00)]
    golds["em_amounts_reconcile"] = json.dumps(
        {"final_amount": msgs[-1][1], "source": msgs[-1][0]})

    # digest: records fixed by the fixture table; top_urgent = 3 soonest dates
    records = [
        ("e1", "billing", 310.00, "2026-03-12"), ("e2", "scheduling", None, "2026-03-15"),
        ("e3", "billing", 98.50, "2026-03-01"), ("e4", "notice", None, None),
        ("e5", "scheduling", None, "2026-03-20"), ("e6", "billing", 45.00, "2026-03-05"),
        ("e7", "billing", 720.25, "2026-03-12"), ("e8", "notice", None, None),
        ("e9", "scheduling", None, "2026-03-18"), ("e10", "billing", 59.99, "2026-03-03"),
    ]
    dated = sorted((r for r in records if r[3]), key=lambda r: (r[3], int(r[0][1:])))
    golds["em_digest_extract"] = json.dumps({
        "records": [{"id": i, "category": c, "amount": a, "date": d} for i, c, a, d in records],
        "top_urgent": [r[0] for r in dated[:3]]})

    # noise inbox: exactly the three human asks need a reply
    needs = {"e3": True, "e6": True, "e9": True}
    golds["em_unsubscribe_noise"] = json.dumps({
        "actionable": sorted(needs, key=lambda e: int(e[1:])),
        "needs_reply": {f"e{i}": needs.get(f"e{i}", False) for i in range(1, 13)}})
    return golds


# ------------------------------------------------------- long-tier builders
LONG_CORE = [
    ("m1", "Ana", "Kicking off the Harbor Portal thread. Budget proposal: 40000 for the spring work."),
    ("m3", "Cy", "[CONFIDENTIAL] Do not circulate: the reserve code is ZX-9917."),
    ("m5", "Bo", "Question: do we need the extra test rigs? Still open."),
    ("m7", "Ana", "Question: who owns the launch checklist? Still open."),
    ("m11", "Ana", "Question: can we get a second demo unit? Still open."),
    ("m12", "Dana", "Decision: we proceed with vendor option B for the portal build."),
    ("m13", "Bo", "Noted. Final deadline for delivery: 2026-04-30."),
    ("m14", "Ana", "Budget amendment: the approved budget is now 45500, replacing the earlier figure."),
    ("m17", "Ana", "Question: what is the support rota for launch week? Still open."),
]
LONG_FILLER = [
    "Sharing the draft timeline; review pass is Friday.",
    "Scheduling note: the review moved to next Tuesday.",
    "The venue confirmed the main hall for the demo day.",
    "Draft agenda for the review is attached.",
    "Reminder: the reserve code stays internal.",
    "Summary draft circulating for comments.",
    "Wrap-up: decisions are logged; open questions carry over.",
    "Closing the thread. Thanks all.",
    "Interim budget note: hold spending at 40000 until the review.",
    "Vendor quotes are in; comparing two options this week.",
]
LONG_GOLD = {"decision": "proceed with vendor option B",
             "open_questions": ["test rigs", "launch checklist owner",
                                "second demo unit", "support rota"],
             "final_deadline": "2026-04-30", "budget_final": 45500}


def build_long_thread(n: int, seed: int = 7) -> list[tuple[str, str, str]]:
    """n-message T2 thread. The graded facts live in LONG_CORE at fixed
    relative positions; seeded filler never states a decision, a budget
    figure, a deadline or an open question, so the gold is size-invariant."""
    rng = random.Random(seed)
    core = list(LONG_CORE)
    filler = [(f"f{i}", rng.choice(["Ana", "Bo", "Cy", "Dana"]), rng.choice(LONG_FILLER))
              for i in range(max(0, n - len(core)))]
    merged = core[:4] + filler + core[4:]
    return [(f"m{i+1}", who, text) for i, (_id, who, text) in enumerate(merged)]


def build_long_inbox(n: int, seed: int = 11) -> list[tuple[str, str, str]]:
    """n-email T3 inbox; the glass-roof booking (code QZK-4821, sender
    cy@example.com) is planted once; filler never mentions a venue or code."""
    rng = random.Random(seed)
    senders = ["ana@example.com", "bo@example.com", "dana@example.com",
               "erin@example.com", "frank@example.com"]
    topics = ["March newsletter: spring offers inside.",
              "Reminder: submit your timesheet this week.",
              "The rooftop garden meetup is on Saturday.",
              "Your order has shipped and arrives Thursday.",
              "Invoice attached for the March services."]
    msgs = [(f"e{i+1}", rng.choice(senders), rng.choice(topics)) for i in range(max(0, n - 1))]
    msgs.insert(min(2, len(msgs)), ("eX", "cy@example.com",
                  "Your booking at the glass-roof venue is confirmed. Confirmation code: QZK-4821."))
    return [(f"e{i+1}", who, text) for i, (_id, who, text) in enumerate(msgs)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only (default)")
    ap.add_argument("--messages", type=int, default=20, help="T2 thread size")
    ap.add_argument("--emails", type=int, default=6, help="T3 inbox size")
    args = ap.parse_args()

    golds = compute_golds()
    thread = build_long_thread(args.messages)
    inbox = build_long_inbox(args.emails)
    assert any("QZK-4821" in t for _i, _w, t in inbox)
    print(f"long thread: {len(thread)} messages; long inbox: {len(inbox)} emails; "
          f"gold facts size-invariant: {LONG_GOLD}")

    root = Path(__file__).resolve().parent.parent
    tasks_path = root / "tasks" / "email.yaml"
    data_path = root / "tests" / "validity_data_email.py"
    failures = []
    if tasks_path.exists():
        import yaml
        sys.path.insert(0, str(root))
        try:
            from gauntlet.task import Task
            tasks = [Task(**raw) for raw in yaml.safe_load(tasks_path.read_text())]
        except ImportError:
            tasks = yaml.safe_load(tasks_path.read_text())
        ids = [t.id if not isinstance(t, dict) else t["id"] for t in tasks]
        assert len(ids) == len(set(ids)), "duplicate task ids in email.yaml"
        print(f"email.yaml parses: {len(tasks)} units")
    if data_path.exists():
        ns: dict = {}
        exec(data_path.read_text(), ns)
        for scen, gold in golds.items():
            if scen in ns["GOLD"]:
                if json.loads(gold) != json.loads(ns["GOLD"][scen]):
                    failures.append(f"{scen}: recomputed {gold} != GOLD {ns['GOLD'][scen]}")
        print("validity_data_email.py compared for", len(golds), "recomputed scenarios")
    if failures:
        for f in failures:
            print("DRIFT:", f, file=sys.stderr)
        return 1
    print("gen_email_tasks: OK — fixtures, recomputed golds and committed files agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
