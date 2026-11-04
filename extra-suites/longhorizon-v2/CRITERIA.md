# Long-horizon suite — reformatted criteria (v2r, Oct 2026)

**Suite:** `~/TysAIs/slm-gauntlet/extra-suites/longhorizon-v2/` (AREO repo)
**Document:** `longhorizon_doc_v2.txt` — 519-entry synthetic ledger, 70,748 words
**Tasks:** `longhorizon_tasks_v2r.json` — 25 tasks in 9 families (v2r format)
**Bench:** `lh-bench-v2r.py` — strict deterministic scoring, per-family subscores
**Generator:** `gen_v2.py` (v1 doc -> v2 doc + 21 tasks) and `gen_v2r.py`
  (v2 tasks -> v2r tasks). Ground truths are recomputed from the final
  document by the generators and asserted, never hand-typed.
**Fit list:** `FIT_LIST.md` (212 measured variant keys; 184 sweep-eligible)
**Runbook:** `RUNBOOK_v2.md`
**Version note:** v2r is a REFORMAT of v2, not a new suite. The 21 v2 tasks are
carried over byte-identical (id/question/answer/fields/turns); v2r adds family
organization, per-task scoring metadata, and 4 balancing tasks (25 total).
The v1 suite in `extra-suites/longhorizon/` is untouched.

## Separation rule (non-negotiable)

Long-horizon scores live in their OWN leaderboard section
(`LEADERBOARD_FORMAT.md`). They NEVER overwrite or merge into the 32K
71-task headline scores. A variant's 32K rank and its 100K rank are different
claims; v1 already proved 32K rank does not predict 100K rank.

## Test conditions (all tasks, all models)

- One attempt per task (Success@1), temperature 0, one server at a time.
- Prompt = full ledger document + one question (multiturn tasks: sequential
  calls with history; later turns do NOT repeat the document).
- Generation cap: bench tokenizes each prompt first (server /tokenize,
  falling back to 4096) and uses min(4096, 102400 - prompt - 128), so the
  102400 cap binds gracefully instead of truncating mid-reasoning.
- System prompt: "You are a careful analyst. Answer ONLY from the document
  provided. Follow the reporting policies stated at the start of the
  document." plus each task's own "Reply with just…" instruction.

## Global scoring rules

1. **No partial credit.** Every task scores 0 or 1. Overall = mean of task
   scores. Per-family subscore = mean within that family (n/m shown too).
2. **Empty = failure, never skipped.** Empty responses, HTTP errors, and
   timeouts are scored 0 with a failure mode, and counted in the denominator.
3. **Multiturn = conjunctive.** A multiturn task passes only if EVERY turn
   passes. Per-turn scores are recorded; the task failure mode is the first
   failing turn's mode.
4. **Echoing never passes.** Any response containing ledger boilerplate
   ("The entry was reviewed by the oversight committee") scores 0 with mode
   `echoed`, even if a correct number appears in it.
5. **Diagnostics do not affect score.** Recorded per task: numbers/dates
   found, bad JSON fields, value_present flags, prompt tokens, latency,
   generation cap used, tokenize estimate.
6. **Failure-mode taxonomy (one per failed task):** `empty`, `wrong_value`,
   `wrong_format` (JSON unparseable), `echoed`, `refused` (model refused a
   legitimate task, or refused with the wrong wording where a token was
   required), `leaked` (a forbidden value was disclosed), `error`
   (HTTP/exception/timeout, e.g. prompt over cap).

## The nine families

### 1. Retrieval — plain retrieval and retrieval at distance
*What it proves:* the model can find a stated fact in ~100K tokens, including
across the whole document (entry 0 vs entry 513).
*Tasks (3):* distance-json (Orion lead + Vega status as JSON, both fields
exact), date-policy-early (Willow prose date -> ISO), plain-retrieval
(Iron Vole budget, mid-document).
*Scoring:* JSON rule for distance-json; numeric-set rule for budgets;
exactly-one-ISO-date rule for dates.

### 2. Retrieval under interference — many similar keys, only one right
*What it proves:* the model does not settle for a near-name match.
*Tasks (2):* distractor (Falcon Prime among Falcon / Falcon-II / Falcon Lite
/ Falcon-X), interference-vega-mole (Vega Mole $22,000, NOT Vega $65,000).
*Scoring:* numeric-set rule.

### 3. Multi-hop tracking — chains and state carried across turns
*What it proves:* the model follows a chain through the document and carries
its own earlier answers forward, including past a blocker.
*Tasks (3):* multihop-sum (Orion + Vega), multiturn-state-3
(Orion $80,000 -> +15% = $92,000 -> minus Falcon Lite $38,000 = $54,000),
multiturn-blocker (missing-record NOT_FOUND, then Orion $80,000 must still
pass — persistence through a blocker).
*Scoring:* numeric-set rule per hop/turn; multiturn tasks conjunctive.

### 4. Whole-document aggregation — no single passage holds the answer
*What it proves:* the model aggregates over the document instead of copying
one passage. Clustered and scattered variants are scored separately so the
difference is visible.
*Tasks (4):* buried-policy-total (Q3 delayed, excluding [INTERNAL]:
$164,000), count (same set: 7), scattered-sum (all Priya-led Q4 projects:
$139,000 across entries 90-497), scattered-count (same set: 7).
*Scoring:* numeric-set rule. Including the two $45,000 internal entries
gives $254,000 / 9 — the policy trap, not a rounding difference.

### 5. Low-overlap reasoning — the question shares few words with the needle
*What it proves:* string matching cannot pass; the model must paraphrase-match.
*Tasks (2):* low-overlap (Falcon-X as "the experimental Falcon line denoted
by a single character": $52,000), low-overlap-lite (Falcon Lite as "the
lightweight Falcon variant": $38,000). Neither question names its target.
*Scoring:* numeric-set rule.

### 6. Agentic reliability — schema-constrained output and routing
*What it proves:* the model does narrow, schema-constrained agent work right
the first time: exact JSON extraction and correct routing decisions.
*Tasks (3):* json-extraction (Vega record as JSON with project/budget/
status/quarter, all fields exact), routing-delayed (Vega -> Escalations
desk per policy P3), routing-ontrack (Orion -> Delivery desk; the
over-routing control — a model that always answers Escalations fails here).
*Scoring:* JSON rule (first {...} block parses; every required field
matches; numbers numerically, strings case-insensitively stripped; extra
keys ignored — strictness is on required fields); routing by exact text
(case-insensitive, one trailing period allowed).

### 7. Faithfulness / groundedness — no answer without document support
*What it proves:* the model does not invent facts for records that do not
exist, in any framing.
*Tasks (3):* missing-budget (Project Zebra budget -> NOT_FOUND),
missing-routing (Zebra desk -> NOT_FOUND), missing-lead (Zebra lead ->
NOT_FOUND). Any invented budget, desk, or lead fails. Note: "Harbor Zebra"
is a different, real project and is never an acceptable answer for
"Project Zebra".
*Scoring:* exact token (case-insensitive, one trailing period allowed).

### 8. Memory / update handling — later facts win, early instructions persist
*What it proves:* facts updated or contradicted later in the document win
over earlier facts, and instructions buried early are followed late.
*Tasks (3):* amendment-harbor (Harbor $120,000 superseded by $145,000),
amendment-kestrel (Kestrel $60,000 superseded by $73,000),
date-policy-late (Alder prose date at entry ~495 -> 2026-09-12 under
policy P2 stated at the start).
*Scoring:* numeric-set rule; exactly-one-ISO-date rule for dates.

### 9. Refusal correctness — refuse where required, never where not
*What it proves:* the model refuses/redacts exactly where the document
requires it, and does not over-refuse legitimate tasks.
*Tasks (2):* confidential-refusal (Cobalt budget -> REFUSED),
confidential-lead (Cobalt lead -> REFUSED). Policy P4: [CONFIDENTIAL]
entries must never be reported. Disclosing $88,888 or the lead "Rosa"
scores `leaked` and fails even if REFUSED also appears.
*Scoring:* exact token REFUSED (case-insensitive) + forbidden-value absence.
*Over-refusal controls:* every non-confidential task — a refusal there
scores `refused` and fails. The distractor and routing-ontrack tasks are
the named controls.

## Document policies (stated at the top of the ledger)

- P1. Reported totals EXCLUDE [INTERNAL] transfers.
- P2. Dates in answers must be ISO (YYYY-MM-DD); prose dates convert.
- P3. Routing: status delayed -> Escalations desk; all else -> Delivery desk.
- P4. Confidentiality: [CONFIDENTIAL] entries must never be reported; if
  asked, reply with exactly REFUSED and nothing else.
- P5. Amendments: where an amended entry states it supersedes an earlier
  entry, only the amended entry counts.

## Document changes from v1 (what was carried, what was added)

Carried unchanged: all 519 entry slots, all v1 test entries (Orion, Vega,
Harbor pair, Falcon family, Willow, Q3-delayed cluster + internal pair),
all v1 questions/answers for the 21 carried tasks (asserted identical).
Added: P3/P4/P5 policies; Kestrel original (entry 100, $60,000) + amended
(entry 480, $73,000, supersedes); Cobalt [CONFIDENTIAL] (entry 490, $88,888,
lead Rosa); Alder prose date (entry 495, September 12, 2026); one
boilerplate repeat removed from entries 200-224 (facts unchanged, token
trim). No Q3-delayed, Priya-Q4, Orion/Vega/Harbor/Falcon/Willow entry was
touched. Word count 71,437 -> 70,748.

## Audit trail: what was wrong in v1 and what v2r changed

1. **Echo-gaming (worst flaw).** v1 numeric scoring passed if the answer
   appeared ANYWHERE in extracted numbers; date/field scoring was substring
   matching. A ledger dump or budget list could pass without answering.
   Fixed: numbers-set rule, date-set rule, boilerplate echo = automatic fail.
   (v1 models happened to answer concisely, so v1 scores were not much
   inflated — but the hole was real.)
2. **Partial credit hid wrong fields.** v1 distance gave 0.5 for one of two
   fields (MiniCPM "Priya; complete" scored 0.5 with Vega's status wrong).
   Fixed: no partial credit; distance is now a JSON task (both fields exact).
3. **Multiturn did not test state as scored.** v1 scored only turn 2 against
   a fixed value, ignoring turn-1 correctness. Fixed: conjunctive scoring,
   per-turn records.
4. **"Whole-document aggregation" was a local cluster.** Q3-delayed entries
   are consecutive (503-511); the filler has no Q3/delayed entries at all.
   Fixed: kept as the clustered baseline + added the scattered Priya-Q4 pair.
5. **Early policy tested only early.** Willow is entry 7. Fixed: Alder at
   entry ~495 tests P2 late.
6. **Missing coverage.** No refusal, missing-record, schema, routing,
   low-overlap, second-amendment, blocker, or 3-turn tests. All added as
   families 5-9 (plus retrieval/interference depth).
7. **Prompt too close to the cap (worst tokenizer).** v1 Spark prompt
   ~100,652 left only ~1,748 tokens of headroom. v2 trims ~25 boilerplate
   repeats; v2r keeps the trim. Honest arithmetic: at a ~100K prompt, a full
   4096-token generation can never fit in a 102400 cap, so the bench caps
   generation from a /tokenize measurement instead of truncating silently.
8. **Known non-errors (do not "fix").** Multihop sum ($145,000) numerically
   equals Harbor's amended budget ($145,000) — different tasks, separate
   calls, no shortcut exists. The multihop question's "exclude internal
   transfers" phrase is noise (neither project is internal); kept verbatim.

## Bench changelog found during validation (v2.0 pilot -> v2r)

- **/tokenize URL bug (v2.0 pilot only).** The v2.0 bench called
  `<endpoint>/tokenize` where endpoint already ends in `/v1`, producing
  `/v1/tokenize` -> HTTP 404 on every turn, so every v2.0 turn silently used
  the 4096 fallback (tokenize_estimate null in the pilot results). The pilot
  scores are still valid (the server truncates generation at the cap), but
  the generation-cap logic never engaged. Fixed in v2r: tokenize is called
  at the server root (endpoint minus `/v1`).
- **Multiturn history overflow (v2.0 pilot only).** In the pilot, the
  multiturn-blocker task errored with HTTP 400: a rambling turn-1 reply
  (echoed boilerplate, thousands of tokens) fed back as history pushed the
  turn-2 prompt over the 102400 cap, and the v2.0 bench discarded the whole
  task on any turn error. Fixed in v2r: per-turn error handling (completed
  turns kept, task fails with mode `error`) and assistant history truncated
  to 1000 chars (genuine answers are far shorter; unaffected).

## Validation results (v2r, Oct 30-31 2026)

### Weak model: LFM2.5-1.2B Q8_0, FP16 KV — 0/25 (0.0%)
Serve: PVE PID 1244390, VRAM 2673 MiB, spare 5519 MiB (matches v1 LH
record). Prompts 99,846-100,087 tokens. Peak GPU 82C. Modes: empty 14,
echoed 10, wrong_value 1. Every family 0/n. Failure pattern matches v1
(0/8 with empties + boilerplate echo) and extends cleanly to the new
tasks: new tasks all fail without accidental passes (plain-retrieval
empty, low-overlap-lite empty, confidential-lead empty — not a leak, not
REFUSED — missing-lead echoed — not NOT_FOUND). A v2.0 pilot run (21
tasks, before the reformat) also scored 0/21 with the same modes, plus
one multiturn-blocker HTTP 400 that the v2r bench fixes (see changelog).

### Strong model: Qwen3.5-9B Q4_K_M, q4_0 KV — 10/25 (40.0%)
Serve: PVE PID 1249703, VRAM 6847 MiB, spare 1345 MiB (matches v1 LH
record). Prompts 92,769-92,852 tokens. Peak GPU 82C. Modes: empty 14,
wrong_value 1. Families: multihop-tracking 2/3, aggregation 0/4,
retrieval 1/3, interference 1/2, memory 2/3, agentic 0/3, faithfulness
1/3, refusal 2/2, low-overlap 1/2.
Passes: multiturn-state-3 (all 3 turns), date-policy-late (2026-09-12),
amendment-kestrel ($73,000), interference-vega-mole ($22,000),
missing-budget (NOT_FOUND), confidential-refusal (REFUSED), low-overlap
($52,000), multiturn-blocker (NOT_FOUND -> $80,000), plain-retrieval
($36,000), confidential-lead (REFUSED).
Near-miss (strictness consequence, the run's only wrong_value):
routing-ontrack answered "Delivery desk" where the required exact text is
"Delivery" — the model knew the desk; the strict rule fails it. Recorded
as a fail, not adjusted.

### Headline finding: Qwen's empties are reasoning exhaustion, PROVEN
14/25 strong tasks are empty, each with latency ~331 s — exactly the full
4096-token generation budget at ~12.4 tok/s. A direct probe of one such
task (distractor, Falcon Prime — passed in v1) with full response capture
showed: finish_reason "length", completion_tokens 4096, content "",
reasoning_content 14,241 chars of thinking ("Thinking Process: 1. Analyze
the Request: Target: Budget of Project Falcon Prime…"), prompt 92,787
tokens (92,289 cached). The bench is NOT misreading the response: content
is genuinely empty. The model spends its whole budget thinking about the
task (including enumerating policies P1/P2/P3) and never emits an answer.
Identical-question flips vs v1 for this same model: buried-policy-total,
distractor, count, date-policy-early, amendment-harbor all passed in v1
and are empty in v2r; multihop-sum is empty in both; multiturn passes in
both (v1 2-turn $92,000; v2r 3-turn $54,000 final). Distance is NOT an
identical comparison (v1 free text -> v2r JSON).
Cause of the flip is NOT proven: candidate contributors are the doc edits
(new policies/entries give a thinking model more constraints to chew on)
and thinking-model trajectory sensitivity at 100K (v1 already proved
run-to-run instability for Spark). What IS proven: (a) the score is
correct under the stated rules, (b) the mechanism is reasoning exhaustion
at the 4096-token harness-standard budget, (c) re-running to chase a better
number would be cherry-picking and is NOT permitted under Success@1 — the
sweep executor records empties with the ~331 s / full-budget signature and
moves on. A future, separately-approved experiment could test whether a
larger generation budget changes Qwen-family empties; it is NOT part of
this sweep and must not be smuggled in.

### Gate assessment (honest)
- Discrimination: PASS. Strong 40.0% vs weak 0.0%; strong wins 7/9
  families, ties 0-0 in aggregation and agentic.
- Strong passes most: FAIL (40% < 50%), cause identified above. The suite
  is still valid and publishable: 10 strong passes prove solvability
  across 7 families, and the empties are a measured model-budget
  phenomenon, not broken tasks (the same questions were passed by this
  model in v1 and by construction have exact answers in the document).
  The gate's "most" wording assumed a concise-answer strong model; Qwen at
  100K is a reasoning-exhaustion case. The sweep will show whether
  concise models (Spark, LFM3, MiniCPM families) pass most tasks — that is
  an empirical question for the sweep, not an assumption.
- Prompt gate: PASS for validated models (LFM <= 100,087; Qwen <=
  92,852). Worst-tokenizer (Spark family, v1 100,652) is ESTIMATED at
  ~99,700 on the v2 doc by word-ratio; the sweep MUST measure it on the
  first Spark-family run and trim more boilerplate if it exceeds 100,500.
- Scorer tests: PASS (24/24 v2 + forbidden-value extension in v2r).
- Failure modes populated: PASS (no `error` rows in either v2r run).

## Validation gates (must hold before the sweep)

- Strong model passes MOST tasks but not all (solvable, not trivial).
- Weak model scores well below strong, with interpretable failure modes
  (not all errors, not all identical).
- Per-model prompt tokens recorded; worst-tokenizer prompt must be
  <= ~100,500 or more boilerplate is trimmed before the sweep.
- Scorer unit tests pass (echo attack, listing attack, partial-field,
  leak, wrong-token cases — 24/24 in v2, extended in v2r for forbidden
  values).
- Failure modes populated for every failed task (no silent errors).

## Sweep rules (summary; full runbook in RUNBOOK_v2.md)

- PVE 1070 Ti only, one server at a time, stop + verify GPU free (2 MiB)
  between runs. Serve at 102400; re-verify VRAM spare >= 1024 MiB at serve.
- Eligible: 184 variants (FIT_LIST.md). Excluded with reasons recorded, not
  skipped silently: all Bolt (65536 context cap), Dory q8_0 (OOM), Spark-4B
  Q8 FP16 (OOM), FP16-flagged Spark-4B quants at FP16 only, not-proven
  variants (fit-test first), offload/classifier/vision tracks (separate).
- Health aborts: RAM available < 500 MB, swap > 4 GB, VRAM headroom < 1 GiB.
  Thermal: see open question 1 below.
- No wipe, no deletions, no Sparks work, no push.

## Open questions for Tyler (nothing silently decided)

1. **Thermal threshold — blocks the sweep as literally written.** Criterion
   says abort at GPU > 80C (hard abort 84C). Measured: sustained 100K
   prefills plateau at 81-82C on this GTX 1070 Ti (v1 log §289; v2r
   validation re-observed 79-82C at 96-97% util). Throttle ~83-84C, max
   94C. A literal > 80C abort kills essentially every 100K run at cold
   prefill. Proposed: hard abort at 84C; > 80C watch-and-record with peak
   temp logged per run. Needs Tyler's explicit decision before the sweep.
2. **Dory v2 fit — gate, not a blocker.** v1 prompt overflowed the cap by
   ~930 tokens on Dory tokenization; the v2 doc is ~690 words shorter, so
   the v2 prompt may land just under 102400 with ~0 generation headroom.
   Sweep executor measures task-1 prompt_tokens first: if prompt + 256 >
   102400, record Dory as does-not-fit for v2r and move on.
3. **Not-proven variants are excluded, not failed.** LFM2.5-1.2B Q4,
   LFM2.5-8B KV variants, Bolt UD-Q8, Qwen q8_0 KV, and all v0.3.1-era
   variants have no 102400 record; they need a fit-test before sweep
   scoring (FIT_LIST.md). Including them is a separate fit-test step.
4. **Cut-off sentence ambiguity — RESOLVED by Tyler Oct 30 ~22:08** (build
   off v1, modern Oct 2026 criteria, full reformat). No other ambiguity
   remains in the brief: full-sweep scope unchanged (184 eligible).
