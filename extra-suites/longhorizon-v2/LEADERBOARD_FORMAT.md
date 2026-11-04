# Long-horizon leaderboard — section format (v2r)

This section is SEPARATE from the 32K 71-task headline. It never overwrites
32K scores. Version string for every row: `longhorizon-v2r`.

## Variant row columns (in order)

| Column | Meaning |
|---|---|
| Variant | Model + quant + source tag (e.g. Spark-X2.6-4B bartowski IQ3_M) |
| KV | FP16 / q8_0 / q4_0 (never FP8/FP4 labels) |
| VRAM@102400 | MiB used at the sweep serve (re-verified at serve, not copied from FIT_LIST.md) |
| Spare | 8192 - VRAM (must be >= 1024 or the row is does-not-fit, not a score) |
| Prompt tok | Mean prompt tokens across the variant's tasks (tokenizer-dependent; record the number, not a claim) |
| Overall | Passed/25 + percent, e.g. `19/25 (76.0%)` |
| RET / INT / MHT / AGG / LOW / AGN / FAI / MEM / REF | Per-family passed/n, e.g. `RET 2/3, INT 1/2, MHT 2/3, AGG 3/4, LOW 1/2, AGN 2/3, FAI 1/3, MEM 3/3, REF 2/2` |
| Failure modes | Counts by mode, e.g. `empty 3, wrong_value 2, echoed 1` (omit zero modes) |
| Notes | Build (llama-server path/version), context flags, anything anomalous |

Family keys: RET = retrieval, INT = interference, MHT = multihop-tracking,
AGG = aggregation, LOW = low-overlap, AGN = agentic, FAI = faithfulness,
MEM = memory, REF = refusal.

## Ordering and winner rules

- Sort by overall percent descending. Ties: alphabetical by variant.
- A one-task gap (4 points on 25 tasks) is NEVER a win — report ties as ties
  and name per-family strengths separately (e.g. "best aggregation" vs
  "best refusal"), not a single overall winner, unless the gap exceeds one
  task AND the per-family pattern supports it.
- A variant that scores 0 on a whole family is reported as such (family
  collapse is a finding, not a footnote to hide).

## Does-not-fit table (same section, after the scored rows)

| Variant | KV | Reason | Evidence |
|---|---|---|---|
| e.g. Bolt E4B Q4_K_M | any | Model context cap 65536 | Server log caps context; v1 prompt 93,154 tokens -> HTTP 400 |
| e.g. Spark-X2.6-4B Q8_0 | FP16 | OOM at 102400 serve | KV alloc failure, 486 MiB short |
| e.g. Dory 1.0 4B Q5_K_M | q4_0 | Prompt over cap (v1) / GATE (v2r) | v1 prompt 103,328-103,346 tokens; v2r prompt measured at task 1 |

Reasons use exactly one of: `VRAM OOM`, `spare <1024 (flagged)`,
`model context cap`, `prompt over cap (tokenizer)`, `not proven (no 102400
record — fit-test first)`. "Not proven" rows are listed separately from
proven does-not-fit rows — absence of a record is not a failure.

## Validation rows (filled from the v2r validation runs)

Validation rows use the same columns. They are the first rows of the section
and are labeled `validation` in Notes until the sweep replaces them with
sweep rows (same numbers — validation runs ARE sweep-format runs, so their
rows stand unless the sweep re-runs the variant, in which case the sweep
row supersedes and the validation row is removed, not duplicated).

| Variant | KV | VRAM@102400 | Spare | Prompt tok | Overall | Families | Failure modes | Notes |
|---|---|---|---|---|---|---|---|---|
| Qwen3.5-9B Q4_K_M | q4_0 | 6847 | 1345 | 92769-92852 | 10/25 (40.0%) | RET 1/3, INT 1/2, MHT 2/3, AGG 0/4, LOW 1/2, AGN 0/3, FAI 1/3, MEM 2/3, REF 2/2 | empty 14, wrong_value 1 | validation; llama-dory-merge build; empties are reasoning exhaustion (probe-proven: full 4096-token budget, content "") |
| LFM2.5-1.2B Q8_0 | FP16 | 2673 | 5519 | 99846-100087 | 0/25 (0.0%) | RET 0/3, INT 0/2, MHT 0/3, AGG 0/4, LOW 0/2, AGN 0/3, FAI 0/3, MEM 0/3, REF 0/2 | empty 14, echoed 10, wrong_value 1 | validation; llama-dory-merge build |
