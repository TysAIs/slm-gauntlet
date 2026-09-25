# Pagoda Build — creative construction benchmark

A staged architectural prompt inspired by showcase builds (à la Spark Bench):
tests long-form instruction adherence, structural planning, and coherent
multi-step creative output in ONE response. Scored on required structural
elements appearing in order, plus a detail floor.

The canonical prompt lives in `pagoda_prompt.txt`. Reference scorer:
`gauntlet/taskgen/pagoda.py` — used by `gauntlet.cli pagoda` to run any
endpoint through it and emit an element-by-element scorecard.

Elements checked (weighted, in build order):
1. foundation / base platform (w:1)
2. stone stairway or path ascending (w:1)
3. torii gate or entrance marker (w:1.5)
4. main pagoda body — 3+ stacked tiers with visible roof flares (w:2, must_pass)
5. roof curvature / eave description (w:1.5)
6. lanterns or lighting elements (w:1)
7. garden / sakura / landscaping (w:1)
8. mountain or water backdrop setting (w:1)
9. atmospheric finish (mist, dusk, bells, incense) (w:1)

Tier scoring: each element = pass/fail on presence of its key nouns.
Percentage = weighted passes / total weight. Models that think aloud or
wrap the build in commentary still score — only the constructed text is
judged, after stripping fenced code and reasoning blocks.
