# Task-validity audit — 0.5.0 corpus (94 tasks)

Measured 2026-11-07 on the PVE GTX 1070 Ti corpus (33 complete 94-task runs, 33 model
configurations, all under the 120 W sustained-load pin and the 89 °C abort). Reproduce with:

```
python3 scripts/audit_task_discrimination.py --json results/_published/discrimination_0.5.0.json
```

Nothing here was inferred from source; every number comes from the run logs named in
`results/_published/discrimination_0.5.0.json`.

## Headline

| measure | value |
|---|---|
| tasks passed by **nobody** in 33 runs | **13** (11 realworld, 2 instruction) |
| tasks passed by **everybody** in 33 runs | **12** |
| weighted cost of the unwinnable set | **8.0 pp subtracted from every published row** |

Consequences, stated plainly:

1. **The unwinnable set is a flat 8.0 pp tax.** It lowers every row by the same amount and
   cannot change rank order. Absolute scores in the 0.5.0 table are therefore *not* comparable
   with 0.3.1/0.4.0 numbers, and the ceiling of the table is 92.0 %, not 100 %.
2. **13 + 12 = 25 of 94 tasks carry no ranking information** at the current model frontier.
   That is 26.6 % of the task set doing no discriminating work. 69 tasks do.
3. **Multi-answer tasks give no partial credit at all.** Every one of the 11 realworld failures
   is graded by 3–4 `must_pass` asserts, so a model that answers 2 of 3 correctly still scores
   `0.00` — visible in the audit as `mean_partial 0.00` for tasks where models demonstrably got
   the first two values right. The published score is binary pass@1 anyway, so this does not
   change the table; it does mean the *rubric* number in each run log is also 0 and carries
   less diagnostic value than it should.

## Are the tasks wrong, or are the models?

Every gold answer in the 11 unwinnable realworld tasks was re-derived by hand from the prompt
text, independently of the assert (the shipped `tests/test_realworld_validity.py` only proves a
gold answer scores 1.0 — it cannot catch a gold answer that is itself wrong). All 11 are correct:

| task | gold | derivation | verdict |
|---|---|---|---|
| rw_expense_split | 200.00 / 36.00 / 59.00 | 216/1.08 = 200 pre-tax; 18 % of 200 = 36; (200+36)/4 = 59 | gold correct, wording wart (below) |
| rw_shipping_quote | 8.00 / 19.50 / 36.00 / 63.50 | 5+1.5·2; 5+1.5·7+4; 5+1.5·12+4+9 | correct |
| rw_payroll_net | 1078.00 / 145.20 / 847.80 | 40·22 + 6·33 = 1078; 0.12·880 + 0.20·198 = 145.2; −85 premium | correct |
| rw_med_dose | 2 / 3 / 0.75 | 250 mcg = 0.25 mg = 2 × 0.125 mg tablets; (1.00 − 0.20)/0.25 = 3.2 → 3 doses; 0.75 mg | correct |
| rw_lease_proration | 1360 / 120 / 2400 / 1480 | 2400·17/30 (Nov 14–30 = 17 days); max(75, 0.05·2400) = 120; cap = 1 month | correct |
| rw_retry_schedule | 12, 16, 24, 40, 70, 100 | first retry held to Retry-After 12; 12+4, +8, +16, +30 (cap), +30 (cap) | correct |
| rw_invoice_deadline | 2026-03-06 / 8247.00 | 2026-02-25 + 10 d = Mar 7 = Saturday → preceding business day Mar 6; 8400·0.98 + 15 | correct |
| rw_warranty_expiry | 2028-02-29 / 2026-02-28 | 2026-08 + 18 mo = 2028-02 (leap year); 2025-01 + 13 mo = 2026-02 | correct |
| rw_ticket_priority | T-2, T-1, T-7, T-9, T-4 | severity 1 (T-2 4 d before T-1 1 d), severity 2 (T-7, T-9 tie → id), severity 3 | correct |
| rw_room_conflicts | B2/B3, B2/B4, B3/B4 | B2→B3 gap 10 min < 15; B2∩B4; B3∩B4; B1→B2 gap exactly 15 min = allowed | correct |
| rw_recipe_scale | 6 / 366 / 43 | ratio 117/64 = 1.828; ceil(3·1.828) = 6; round(200·1.828) = 366; round(32·√1.828) = 43 | correct |

What models actually do on them, from the logs:

* `rw_ticket_priority` — 8 of the first 8 models answer `["T-1","T-2",…]`: they sort severity
  ascending and then **ignore the age-descending key**. Genuine failure, not ambiguity.
* `rw_room_conflicts` — answers like `[[B1,B4],[B2,B4],[B3,B4]]`: the 15-minute buffer is
  dropped, and the pair that *does* overlap (B2/B4, B3/B4) is half-found. Genuine failure.
* `rw_expense_split` — the two arithmetic answers are often right (200.00 / 36.00) and the split
  is wrong: models divide the tax-inclusive receipt by four (216/4 = 54.00) and drop the tip.
* The two unwinnable instruction tasks are also genuine: `hif_letter_ban_long` is a long-output
  letter ban (one slip fails it) and `hif_system_conflict` requires an exact output shape that
  models wrap as `{"answer": …}`.

**Verdict: the graders are correct, the golds are correct, and the models really do fail these
tasks.** The defect is discrimination and credit structure, not correctness.

## One real wording wart

`rw_expense_split` opens with "a receipt totals $216.00, and that total already includes 8 %
sales tax" and then defines "the total cost (subtotal + tip) is split equally by 4". The
parenthetical defines the tax away: the restaurant collects 216, but the split is of 236. Per
the written spec 59.00 is correct, and that is what the assert expects; the answer a person
would give (252/4 = 63.00) is marked wrong. Not a grading bug — a prompt that should not rely on
a parenthetical to override the arithmetic a reader does naturally. Fix queued for 0.5.1.

## Decisions taken here

* **0.5.0 is frozen as measured.** The 33 runs are valid against these task definitions; editing
  an assert now would silently redefine the epoch and invalidate them. The 8.0 pp tax is
  published with the table, not hidden.
* **No task is deleted for being hard.** An unwinnable task at the current frontier is a
  legitimate ceiling measurement; it is reported, not removed, so the next model generation has
  something to win.
* **Queued for 0.5.1** (needs one full re-run, so it is a separate epoch, not a patch):
  1. split multi-answer tasks so each sub-answer is a scored unit, with `must_pass` reserved for
     the answers that are actually gating correctness;
  2. repair `rw_expense_split`'s tax wording;
  3. replace or retire the 12 "everybody passes" items so the low end of the table can
     discriminate (they currently give a free floor to every row);
  4. re-derive the realworld suite size so 12 % weight is not 55 %-dead at the frontier.
