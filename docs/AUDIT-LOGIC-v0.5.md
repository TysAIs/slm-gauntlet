# Gauntlet logic audit — scoring, judging, task validity (phase 1)

Date: 2026-11-05 (MST)
Auditor: invincible lane. Hardware for every live number below: PVE GTX 1070 Ti test box,
provider `grunt-pve` (the PVE test box's `llama-server` on tailnet port 8891). No GB10 node was touched.
Baseline commit audited: `cbf748e` (working tree clean, 90/90 tests green).
Extended 2026-11-07 with F16 (transport failures published as scores) and the phase-2
suite expansion; the original findings are unchanged.

Suite re-read from disk at audit time (never from a summary):

```
cat tasks/*.yaml extra-suites/longhorizon-v2/longhorizon_tasks_v2r.json | sha256sum
b3b3331529ddfe1e20555d4f8439f304d0fa6961025417ca8ff2bc8a5b386623
```

Corpus: 777 run logs in `results/`, 522 of them with per-attempt records, 84 scored tasks
(77 YAML + 7 generated retrieval tasks).

This audits the **engine** (how a task is run, graded and aggregated). The data-driven
task-corpus audit (ceiling/floor tasks, broken predicates, thin coverage) is separate and
lives in `results/_published/audit_v0.4/AUDIT.md`.

---

## Ranked findings

| # | Finding | Severity | Verdict |
|---|---|---|---|
| F1 | The published score is binary pass@1, but three places document it as task-level partial credit. Re-scoring the existing corpus on the rubric moves rows up by a mean of **+7.1 pp** (max +24.9 pp). | S1 — changes published numbers | FIX (doc corrected now; re-score needs Tyler's wording call) |
| F2 | Nothing in `gauntlet/` enforces a thermal ceiling, and the only watchdog in the repo is hardcoded at **84 C**, below Tyler's 89 C ruling. | S1 — hardware safety + explicit ruling | FIX (applied) |
| F3 | `state_path` accepted a **missing** key as `False` (because `False == 0`), so `equals: false` passed on a sandbox that never set it. | S2 — silent false pass | FIX (applied) |
| F4 | A run covering a subset of suites publishes a full-looking "capability score" (weights renormalize). A 2-task run printed **0.455**, another printed **1.000**. | S2 — misleading headline | FIX (coverage stamp; applied in the run summary) |
| F5 | Graded answers leak into prompts: 27 assert values (28 before the fix) already appear verbatim in the prompt they grade. Live: a model answered `The tide is always there.` and passed `if_multi_constraint` (2 asserts). | S2 — task validity | FIX for real leaks (`rw_timezone_meeting`); KEEP-WITH-NOTE where verbatim copy *is* the task |
| F6 | Only 19 of 77 YAML tasks have more than one assert; 58 are single-assert and 41 mark every assert `must_pass`. The partial-credit rubric therefore barely exists as a measurement. | S2 — benchmark validity | KEEP-WITH-NOTE (phase-2 expansion fixes it; do not fake it with weights) |
| F7 | `pass^k` on an enriched task compares **different instances**: `enrich_task` is called inside the repeat loop with a per-rep seed. | S3 — reliability metric invalid | FIX (applied) |
| F8 | The text+state rubric is averaged 50/50, so a failed `must_pass` gate in either half still yields 0.5 from the clean half. All 23 state-assert tasks also carry text asserts. | S3 — gate dilution | FIX (applied: a failed gate zeroes the rubric) |
| F9 | `flaky: true` (4 tasks) promises "repeats should be 3"; the validator is a no-op. | S3 — dead field | FIX (applied: enforce) |
| F10 | Text-embedded tool calls are ignored when `finish_reason == "stop"`. 0 corpus occurrences today (latent). | S3 — latent judging gap | KEEP-WITH-NOTE (revisit if a tool-capable model regresses) |
| F11 | Loop watchdog aborts on the **third identical call before executing it**; a legitimate poll/cancel-repeat pattern fails. 163 `looped` terminations on `tool_hard_malformed_then_repair`. | S3 — false failure | KEEP-WITH-NOTE (documented; loops must fail) |
| F12 | Comma-stripping normalization applies to `contains_*`/`exact_match` only, not `regex`/`predicate`/`json_schema`: the same answer is graded differently by assert type. | S4 — inconsistency | KEEP-WITH-NOTE |
| F13 | `contamination_risk` and `canary` are recorded and never read. A contamination claim with no enforcement. | S4 — metadata | KEEP-WITH-NOTE |
| F14 | `validate_tasks` skips `json_schema` shape, weight ≤ 0, and `state_path` typo paths. | S4 — preflight gap | KEEP-WITH-NOTE |
| F15 | Phase-0 repo gates were red before this audit touched anything: the hygiene gate failed on 9 tracked files and `ruff check .` on 87 errors, so "green CI" was not true. | S2 — publishability | FIX (applied) |
| F16 | A run whose requests **never reached the model** was published as a score: 79 of 79 attempts terminated `error` with 0 prompt and 0 completion tokens, and the card read `0.0%`. Nothing in the pipeline distinguished "the model failed" from "the endpoint was dead". | S1 — false published number | FIX (applied: `gauntlet/run_health.py`, publisher refuses to rank it) |

---

## Evidence per finding

### F1 — published score is binary, documented as partial credit

Code:
* `gauntlet/runner.py:75` stores the rubric (`"score": round(rubric, 3)`) next to `"passed"`.
* `gauntlet/runner.py:89-90` computes `pass1` from the binary `passed` flags only.
* `scripts/leaderboard_check.py:32` — *"task pass1 is the scorer's partial credit, as recorded per task in the run log"*.
* `scripts/leaderboard_check.py:211` — `by.setdefault(r["suite"], []).append(float(r.get("pass1", 0.0)))`.
* `gauntlet/report.py:24` — `pass1 = sum(i["pass1"] ...)`.

Measured on the existing corpus (522 logs that carry attempts, provider-independent, no new calls):

```
mean delta pp (rubric-binary): 7.08  median 5.96  max 24.91
rows where rubric > binary: 503/522
attempts with 0 < rubric < 1 and passed=False: 2673
```

Worst cases: `minicpm-v-4.7-1b-q4km-kvq8` 59.6 published vs 84.6 under its own rubric;
`minicpm5-2b` 72.2 vs 93.1; `minicpm-v-4.7-1b-q4km-kvq4` 66.7 vs 88.1.

Why the doc was believed: `leaderboard_check.py` exists to recompute each published number from
the log it came from, and its docstring says the recomputation is partial credit. It is not.

Verdict FIX. The docstring is corrected in this commit (no number moves). Publishing the rubric
number instead would raise rows by up to 25 pp, so it is a **publicity decision, not a bug fix** —
see "Needs Tyler" below.

### F2 — thermal rule

Tyler's ruling (2026-11-04): abort at **89 C**; the 1070 Ti is rated to 94 C.

What the code does:
* `gauntlet/` contains **no** `nvidia-smi` call — `gauntlet run` will happily cook the card.
* The only watchdog in the repo is embedded in `extra-suites/longhorizon-v2/sweep_driver.sh:25`:
  `if [ "$t" -ge 84 ]; then touch /tmp/lh2_ABORT; pkill ...` — the pre-ruling threshold, still 84 C.

Live probe around a real 2-task run on `grunt-pve` (2026-11-05 14:54 MST):

```
PRE  38, 8.94 W
POST 47, 51.08 W     (2 tasks, 1 completion each, concurrency 1)
```

A short run stays far below either threshold; the defect is that **nothing would stop a run that
didn't** — which is exactly the multi-hour phase-6 sweep.

Verdict FIX, applied in this commit:
* `sweep_driver.sh` watchdog raised 84 → 89 C (and its comment).
* new `gauntlet/thermal.py`: reads the GPU temperature and refuses to start a run at or above the
  limit; `gauntlet run` calls it in preflight with `--thermal-limit 89` (0 disables, and a host
  with no `nvidia-smi` is a no-op rather than a failure).
* `tests/test_thermal.py` asserts the 89 C boundary: 88.9 passes, 89.0 aborts, missing sensor is a
  no-op.

Mid-run sampling still belongs to the sweep driver (it kills the server, not just the client);
the CLI guarantee is "never start hot".

### F3 — `state_path` false pass

`gauntlet/state_check.py:55`:

```python
if value is None and sa.equals in ([], {}, "", 0):
    ok = True
```

`False in ([], {}, "", 0)` is `True` in Python (`False == 0`). Measured:

```
# before the fix (probe P1):
asked flags.enabled == False on an EMPTY sandbox -> passed=True score=1.0
asked flags.enabled == 0     on an EMPTY sandbox -> passed=True score=1.0
asked flags.enabled == None  on an EMPTY sandbox -> passed=False score=0.0
# after the fix:
asked flags.enabled == False on an EMPTY sandbox -> passed=False score=0.0
```

Latent (no task uses `equals: false` today), but the first boolean state assert — "the tool did
**not** send the email" — would silently pass on a model that never touched state. Verdict FIX
(applied: the empty-default shortcut now covers only containers and the empty string; `0`/`False`
must actually be present).

### F4 — partial coverage publishes a full-looking score

`gauntlet/report.py:29-31` renormalizes weights over suites present, and the printed summary has
no coverage field. Live, both from `grunt-pve` runs today:

```
2 tasks (instruction 1.0, realworld 0.0) -> "subagent_capability_score": 0.455
2 tasks (instruction 1.0, structured 1.0) -> "subagent_capability_score": 1.0
```

A two-task run claiming 1.000 is the failure mode. The published leaderboard is protected
(`leaderboard_check.py` gates rows on epoch and `FULL_TASKS`), but `report.generate_leaderboard`
and the CLI summary are not. Verdict FIX (applied: the summary now states tasks/suites covered and
marks a partial run).

### F5 — prompt leaks into graded answers

Scan of the corpus against itself (`scripts/probe_logic_audit.py`, P6): 28 assert values appeared
verbatim in the prompt they grade (27 after the `rw_timezone_meeting` fix below). Most are intentional copy tasks. The two that are defects:

* `rw_timezone_meeting` grades `2026-01-20T16:30:00+00:00`, and the prompt contains
  `e.g. 2026-01-20T16:30:00+00:00` as its own example — the UTC line is free, and it is
  `must_pass` with weight 2.0.
* `if_multi_constraint` grades `contains_all: ["tide"]`; a model that answers
  `The tide is always there.` passes both of its asserts (measured live today).

Verdict: FIX the example leak (change the example to a different instant than the graded answer);
KEEP-WITH-NOTE the rest, where the assert is checking the copy itself. The empirical face of this
is the 21 ceiling tasks in `audit_v0.4/AUDIT.md` (≥95 % pass).

### F6 — the rubric barely exists

```
tasks=77  single_assert=58  all_asserts_must_pass=41  zero_weight=0
```

75 % of tasks are binary by construction and another 20 % are gated to 0 or 1. Any claim that the
suite grades partial credit applies to ~18 tasks at most. Verdict KEEP-WITH-NOTE — the fix is more
multi-constraint tasks (phase 2), not re-weighting the ones we have.

### F7 — `pass^k` compares different instances

`gauntlet/runner.py:27`: `enrich_task(task, seed=seed * 1000 + rep)` sits **inside** the repeat
loop, so `{FLIGHT_CATALOG}` is regenerated per rep and `pass^k` aggregates across different
catalogs. Verdict FIX (applied: enrich once per task, before the loop).

### F8 — gates diluted by the 50/50 average

`gauntlet/runner.py:48-49`: `rubric = (score.score + state["score"]) / 2`. A `must_pass` gate in
either half that zeroed that half still yielded 0.5 when the other half was clean — the gate
affected `passed` but not the rubric. All 23 tasks with state asserts also carry text asserts, so
this path was live on every one of them; `tool_file_write_read` (a `must_pass` `file_content`
assert) is the concrete case, and an existing integration test had encoded the diluted 0.5 as
expected behaviour. Verdict FIX (applied: a failed gate zeroes the combined rubric; the test now
asserts 0.0).

### F9 — `flaky` is decorative

`gauntlet/task.py:109-112` names a validator that returns its input unchanged. 4 tasks set
`flaky: true`. Verdict FIX (applied: `repeats` is raised to 3 when `flaky` is true). This changes
future runs of those 4 tasks only; no published log changes.

### F10 — text-embedded call with `finish_reason: stop`

`gauntlet/agent_loop.py:112` requires `result.finish_reason != "stop"` before executing a
text-embedded call, and the parser only matches when the answer *starts* with the call
(`sandbox.py:303`). Corpus check with the real parser: **0** completed attempts carried a
text-embedded call to a real tool and executed nothing. Latent. Verdict KEEP-WITH-NOTE.

### F11 — watchdog kills legitimate repeats

`gauntlet/agent_loop.py:41` returns `True` when the same `name+args` is seen `max_repeats` times,
and the caller returns before executing that third call; `looped` also carries no `final_text`, so
the rubric is 0. A cancel-then-verify or poll loop is indistinguishable from a stuck model.
163 `looped` terminations on `tool_hard_malformed_then_repair` in the corpus. Verdict
KEEP-WITH-NOTE (a loop must fail somewhere; the note is that "3 identical calls" is a policy, not
a fact).

### F12 — number normalization is assert-type dependent

`gauntlet/scorer.py:257,283,286` strip commas for `exact_match`/`contains_*`; `regex`, `predicate`
and `json_schema` see the raw text. Same answer, different verdict depending on the assert type.
Verdict KEEP-WITH-NOTE (documented; a model that writes `1,284.50` fails a `regex` task and passes
a `contains_all` task).

### F13/F14 — metadata and preflight

`contamination_risk` and `canary` are set by the generator (`taskgen/needle_haystack.py:131,150`)
and read nowhere outside a schema test. `validate_tasks` (`gauntlet/cli.py:28-60`) checks regex
compilation, empty asserts and missing `values`, but not `json_schema` shape, non-positive weights,
or a `state_path` that no tool could ever write. Both KEEP-WITH-NOTE.

### F15 — the repo's own gates were red, so "clean" wasn't true

Measured on a clean checkout of `cbf748e` (before this audit changed a byte):

```
$ bash scripts/hygiene-check.sh          -> exit 1, 9 tracked files HIT
$ uvx ruff@0.6.9 check .                 -> 87 errors
```

The hygiene hits were the operator's first name in attribution prose and the English word
"redacted" (the OCR suite's own field name). The lint hits were 52 in `extra-suites/`, 31 in
top-level one-off helper scripts, 4 in `classifier-bench/`, plus the vendored `llama.cpp` tree
(a submodule pointer, so `ruff check .` walked someone else's repo). CI runs both steps, so the
badge was red for reasons that had nothing to do with the benchmark.

Verdict FIX (applied): the gate now strips the two non-PII words before matching (addresses,
paths, emails, handles and the GPU-box host name are still screened); ruff lints the shipped package and its
tooling (`gauntlet scripts tests`) with `llama.cpp` excluded; the whole shipped tree is lint-clean.
`--history` mode still reports pre-existing author-email lines — CI runs the tree scan only, and
rewriting history to satisfy a lint of the past is not worth it.

Also fixed while verifying F15: `results/_published/leaderboard.json` disagreed with the corpus
(the benchmark string omitted the new `realworld` suite), so `leaderboard_check.py` exited 1 on a
clean tree. Regenerated with `--write`: **no score changed**, one metadata string did.

### F16 — a dead endpoint published as a model score

`results/spark-x2.6-4b-q4ks-xhtoken-kvq4_20261029T040626Z.json` holds 71 task results and
79 attempts. Every attempt is `terminated: "error"` with `prompt_tokens: 0` and
`completion_tokens: 0`, i.e. the request was never processed — the endpoint refused or
died, three runs in a row (19/23, 19/19 and then 71/71 tasks affected across that day).
The corpus card published **0.0%**, which reads as "this configuration is broken" when in
fact **that configuration was never measured**.

Detection is now one definition, `gauntlet/run_health.py`: a run is a transport failure
when more than 50% of its attempts are `error` with zero prompt AND zero completion
tokens. The runner stamps `transport_failure` / `zero_token_errors` / `attempts` into
`meta`, prints a loud warning, and `scripts/leaderboard_check.py` refuses to rank a card
whose source log fails the test — so the exclusion is visible in the published table
("transport failure: 79 of 79 attempts returned no tokens") instead of hiding as a
deleted row.

Receipt (read-only):

```
$ python3 scripts/audit_corpus_transport.py
scanned 524 scored run logs; 5 are transport failures (share > 50% zero-token attempts)
  FAIL results/spark-x2.6-4b-q4ks-xhtoken-kvq4_20261029T040626Z.json  n=71 attempts=79 zero=79 (100%)
  ... (4 more: 2 Bonsai n=8 legacy logs, and the two aborted 19-task runs of the same config)
published cards sourced from a transport-failed run:
  results/cards/card_spark-x2.6-4b-q4ks-xhtoken-kvq4.json  published=0.0  <- ...20261029T040626Z.json
all transport-failed cards are excluded from the ranking (classify() refuses them)
```

Only one published card is affected, so no ranking moved. It stays in the corpus,
labelled, and the configuration is re-run under 0.5.0.

### The epoch is frozen where it is claimed

Adding tasks to `tasks/` silently changed what the **0.4.0** epoch claimed to be: its
`tasks` field was computed live (`_count_current_tasks()`), so a later suite expansion
retroactively redefined an old epoch's denominator. 0.4.0 is now pinned at the 84 tasks
it actually had, and 0.5.0 carries the live count (94: 87 YAML + 7 generated retrieval).
No 0.4.0 row exists in the corpus, so nothing had to be re-scored.

---

## Phase 2 — the suite expansion (real work, not more keyword tasks)

The audit's F6 said the partial-credit rubric barely exists because 58 of 77 tasks are
single-assert. The fix is **more multi-constraint real-life tasks**, not re-weighting, so
`tasks/realworld.yaml` gains ten:

| task | what a person actually asks for | the mistake it exists to catch |
|---|---|---|
| `rw_payroll_net` | weekly pay: overtime, a different tax rate on the OT portion, flat deduction | taxing overtime at the regular rate |
| `rw_med_dose` | mcg→mg conversion under a daily ceiling partially used by a second drug | ignoring the second drug's share of the ceiling |
| `rw_connection_legality` | which flight connections satisfy minimum-time rules with a terminal penalty | treating a short connection as legal |
| `rw_lease_proration` | prorated rent by billable days, greater-of late fee, statutory deposit cap | excluding the move-in day / ignoring the cap |
| `rw_ledger_recon` | reconcile two ledgers and **write** the discrepancy file, including a missing row | reporting only changed amounts |
| `rw_recipe_scale` | pan-size rescale: area ratio for ingredients, square-root bake time, whole eggs | scaling bake time linearly with area |
| `rw_retry_schedule` | retry plan obeying Retry-After, exponential backoff, a wait cap and a retry limit | ignoring the server's Retry-After |
| `rw_allergy_swap` | pick the cheapest substitution that is safe under an allergy | choosing the cheapest, ignoring "may contain traces" |
| `rw_room_conflicts` | every conflicting booking under overlap-OR-buffer policy | checking overlaps only |
| `rw_invoice_deadline` | 2/10 net 30 deadline that falls on a Saturday, plus a wire fee | keeping the weekend date |

Validity is **proved, not asserted**: `tests/test_realworld_validity.py` runs an
independently written GOLD answer (must score 1.0) and a NEAR_MISS answer carrying the
exact mistake above (must score 0.0 through a `must_pass` gate) through the real scorer
and the real sandbox. `44 passed` on that file, `129 passed` on the suite. Every new task
is multi-assert and gated, and `rw_ledger_recon` grades a written file, not prose.

---

## What this commit changes

* `docs/AUDIT-LOGIC-v0.5.md` — this file.
* `gauntlet/thermal.py`, `gauntlet/cli.py` — 89 C preflight, `--thermal-limit`.
* `gauntlet/state_check.py` — no more `False`-passes-on-missing-key.
* `gauntlet/runner.py` — enrich once per task; gate zeroes the combined rubric.
* `gauntlet/task.py` — `flaky` actually raises repeats to 3.
* `gauntlet/report.py` — the summary reports coverage and flags partial runs.
* `scripts/leaderboard_check.py` — docstring corrected to say binary pass@1.
* `extra-suites/longhorizon-v2/sweep_driver.sh` — 84 → 89 C.
* `tasks/realworld.yaml` — `rw_timezone_meeting`'s worked example is no longer the graded answer.
* `scripts/hygiene-check.sh`, `.github/workflows/ci.yml`, `pyproject.toml` — F15: the gates now pass
  on the shipped tree, and lint scope is stated.
* `results/_published/leaderboard.json` — regenerated (metadata only, no score changed).
* `scripts/probe_logic_audit.py`, `scripts/audit_corpus_rubric_delta.py` — the probes that produce
  the evidence above.
* `tests/test_thermal_and_audit.py` — 11 regressions pinning the 89 C boundary, the `state_path`
  false-pass, the gate, `flaky` and the coverage stamp.

Methodology version stays `0.4.0`: the only semantic change that could move a score is the
`flaky`/gate/state fixes, and bumping the epoch now would empty the headline table (every existing
card is pre-bump). The epoch bump belongs with the phase-6 re-run, when 0.5.0 rows exist.

## Needs Tyler (published claim, one line)

> Correction: the published gauntlet table is binary pass@1, not partial credit (the pipeline
> docstring said partial credit). Re-scoring the same logs on the rubric raises rows by up to
> 25 pp. Publish binary (status quo) or rubric (numbers change)?

## Reproduction

```
cd ~/TysAIs/slm-gauntlet
.venv/bin/python scripts/probe_logic_audit.py                 # F3, F4, F9 + F5 scan
.venv/bin/python scripts/audit_corpus_rubric_delta.py         # F1 corpus delta (522 logs)
.venv/bin/python -m pytest tests -q                            # baseline
# live probe, test box only, provider grunt-pve (tailnet address, port 8891):
GRUNT=http://<test-box>:8891
.venv/bin/python -m gauntlet.cli run --endpoint $GRUNT/v1 \
    --model "$(curl -s $GRUNT/props | jq -r .model_path)" \
    --tasks-dir <dir with a single task yaml> --suite all --concurrency 1
```
