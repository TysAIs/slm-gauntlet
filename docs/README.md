# Docs index

Method records, one per epoch. **Only the newest sweep and the two audits it depends on
describe how the current numbers were produced**; the rest are frozen history, kept because a
published score must stay traceable to the procedure it was measured under.

| Document | Epoch | Status | What it is |
|---|---|---|---|
| [`SWEEP-v060.md`](SWEEP-v060.md) | 0.6.0 | **current** | What differs in this epoch: 320-task corpus, 14-suite weights, engine build, phases, ratification basis, and why 0.5.0/0.6.0 scores are not comparable |
| [`AUDIT-LOGIC-v0.5.md`](AUDIT-LOGIC-v0.5.md) | 0.5.0 | current method, historical numbers | Audit of the *engine*: how a task is run, graded and aggregated (rubric vs pass@1, transport failures, weighting). The findings still govern the code; the counts it quotes are 0.5.0's |
| [`AUDIT-TASK-VALIDITY-v0.5.1.md`](AUDIT-TASK-VALIDITY-v0.5.1.md) | 0.5.1 | historical | Repair of the 25 non-discriminating 0.5.0 tasks, measured in its own epoch |
| [`AUDIT-TASK-VALIDITY-v0.5.md`](AUDIT-TASK-VALIDITY-v0.5.md) | 0.5.0 | historical | The task-validity audit itself: 13 tasks passed by nobody, 12 by everybody, a flat 8.0 pp on every 0.5.0 row |
| [`SWEEP-v051.md`](SWEEP-v051.md) | 0.5.1 | historical | 0.5.1 sweep record |
| [`SWEEP-v050.md`](SWEEP-v050.md) | 0.5.0 | historical | The lane procedure both later sweeps inherit (preflight, swap one config at a time, restore the shipped unit) |
| [`ROADMAP-v0.3.md`](ROADMAP-v0.3.md) | v0.3.1 | historical | The original research notes and suite plan; several ideas here were later rejected (prose "pagoda" scoring) and the document says so |

Where the numbers live: [`../SCOREBOARD.md`](../SCOREBOARD.md) is the summary of every board;
[`../results/_published/LEADERBOARD.md`](../results/_published/LEADERBOARD.md) is the long form
generated from the card corpus; [`../results/_published/leaderboard.json`](../results/_published/leaderboard.json)
is the machine-readable ranking.

The consistency audit for this pass (what was checked, what was fixed, what is a named
limitation) is [`AUDIT-CONSISTENCY-0.6.0.md`](AUDIT-CONSISTENCY-0.6.0.md).
