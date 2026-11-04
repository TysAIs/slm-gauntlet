# Long-horizon suite v2r — file guide

- `longhorizon_doc_v2.txt` — the ledger document (519 entries). Shared by v2 and v2r.
- `longhorizon_tasks_v2.json` — v2 task file (21 tasks). Kept for provenance;
  the weak-model pilot validation ran against this file.
- `longhorizon_tasks_v2r.json` — REFORMATTED task file (25 tasks, 9 families).
  The 21 v2 tasks are carried over byte-identical; 4 balancing tasks added.
  THIS is the file the sweep runs.
- `lh-bench-v2.py` — v2 bench (strict scoring, no family breakdown).
- `lh-bench-v2r.py` — REFORMATTED bench (identical scoring + per-family
  subscores + `forbidden`-value leak checks + `--only-ids`). THIS is the
  bench the sweep runs.
- `gen_v2.py` — regenerates the v2 doc + 21 tasks from the v1 doc.
- `gen_v2r.py` — regenerates the v2r task file from the v2 doc + v2 tasks.
- `CRITERIA.md` — canonical reformatted criteria document.
- `LEADERBOARD_FORMAT.md` — the long-horizon leaderboard section format.
- `FIT_LIST.md` — 102400 fit / does-not-fit list (212 measured keys).
- `RUNBOOK_v2.md` — sweep runbook (serve commands, order, gates, aborts).
- `results_<model>-v2.json` — v2 pilot validation results (weak model).
- `results_<model>-v2r.json` — v2r validation + sweep results.
- v1 suite (untouched): `../longhorizon/` (doc, tasks, bench, results).
