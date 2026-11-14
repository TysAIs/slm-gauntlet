# Sweep — 0.6.0 epoch (task set + serving conditions)

The 0.5.0 sweep procedure and its receipts live in `docs/SWEEP-v050.md` and still apply:
preflight the lane, swap one config at a time with a systemd drop-in, wait for
`/props.model_path` AND `/v1/models[0].id` to match, run the full suite, append a state
line, restore the shipped unit. This file records only what differs for 0.6.0 and why.

## What differs

| | 0.5.1 | 0.6.0 |
|---|---|---|
| task set | 140 tasks (core 8 suites; realworld scored as sub-answer units) | 320 scored units across 14 suites: the core 8 plus six job suites (email / support / classify / docintake / summarize / calendar) |
| methodology | 0.5.1 (0.5.0 weights, frozen) | 0.6.0 weights in `gauntlet/methodology.py`: core block scaled to 0.55, agent block 0.45 |
| scoring | deterministic | deterministic, unchanged as a standard; no LLM judge in any scored path |
| engine | llama.cpp `a2878d3` (2026-09-11 build) | llama.cpp 0.8.0-dev commit `1c3cdd2` (`<engine-build-dir>`, PR #30306 lineage) — the single primary; the old build stays on disk as rollback |
| configuration rows | 48 | Phase S screen: 19 canonical rows (Q4_K_M-class quant, KV q8_0, T1 32,768); Phase M: finalist quant x KV matrix (see below) |
| serve flags | `-fa on --reasoning-budget 0 -cram 0` | the same |
| state files | `results/_sweep_state_v051.jsonl` | per phase: `results/_sweep_state_screen_v060.jsonl` (Phase S), `results/_sweep_state_phase_m_v060.jsonl` (Phase M) |

## Ratification (operator, 2026-11-09)

Epoch 0.6.0 was **ratified by the operator on 2026-11-09**, after the Phase S screen completed
19/19 configs on the new engine. Basis for the epoch break:

* a new engine build (above) — the first build that loads the `dory` and `lfm3`
  architectures, so two roster families are measurable at all;
* a new task set and new weights (above) — six real-world job suites added by design
  (P2 design section 2.6 weights: core 0.55 / agent 0.45);
* measured anchor drift on the two 0.5.0 anchor configs re-run on the new build
  (core battery, KV f16/f16, ctx 32768):

| Anchor (exact 0.5.0 config) | Published 0.5.0 | New build, 0.5.0 weights | Drift |
|---|---|---|---|
| Spark-X2.6-4B IQ3_M (bartowski) | 81.0 | 85.1 | +4.1 pp |
| Gemma 4 E4B Q4_K_M | 86.3 | 89.1 | +2.8 pp |

  The scorer was proven sound before any drift claim: re-scoring the original 0.5.0
  result files under the frozen `_WEIGHTS_0_5` reproduces the published 81.0 / 86.3
  exactly. The drift is decomposed to new-engine retrieval fixes plus realworld
  sub-assertion re-scoring — not scorer drift and not noise.

**Comparability, stated plainly: 0.5.0 and 0.6.0 scores are NOT comparable.** They were
measured with different engines, different task sets, and different weights. Rows from
the two epochs are never ranked against each other; the publisher already enforces
one ranked table per epoch (`gauntlet/methodology.py` EPOCHS, frozen entries for
0.4.0–0.5.1). 0.6.0 rows are comparable with each other and with nothing else.

## Phases in this epoch

* **Phase S — screen (done 2026-11-09):** 19 configs x canonical config x full T1
  battery, manifest `scripts/sweep_manifest_screen_v060.tsv`, all 19 completed with
  complete 320-unit results; no OOMs, no thermal aborts (peak 80 C vs the 89 C ceiling).
* **Phase M — matrix:** the top-8 finalist cut from the screen, crossed with the
  quant x KV cells that exist on the box (design section 4.1: quants {IQ3-class low,
  Q4_K_M canonical, Q6_K/Q8_0-class high} x KV {f16, q8_0, q4_0}, as files exist),
  manifest `scripts/sweep_manifest_phase_m_v060.tsv`, state
  `results/_sweep_state_phase_m_v060.jsonl`, T1 serve (ctx 32768, np 1) throughout.
  FIT rule unchanged: a config is eligible at a cell only if it serves with
  VRAM spare >= 1024 MiB, re-verified at serve time; a cell that cannot serve is
  recorded does-not-fit with its cause, never scored 0.

* **Roster note — Granite Switch:** IBM's Granite Switch is a classifier-story model, excluded from this generative roster by role; its GGUFs on the box stay untested by the generative battery (its lane is the classifier board, whose expansion is blocked on a proprietary scoring endpoint the local harness cannot substitute).
