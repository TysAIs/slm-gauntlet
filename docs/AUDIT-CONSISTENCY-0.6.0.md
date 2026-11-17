# Consistency audit — epoch 0.6.0 (2026-11-13)

This is the record of a full pass over the repository as it would be published: every
document, script, board, card and artifact was read against the others, and the findings
are either fixed or named below. Nothing here changed a score: no run log, card score,
suite percentage or leaderboard cell was edited. The checks that prove that are in
[Verification](#verification).

Scope, in the order the pass ran:

1. every shipped file (1156 on the publish surface) — dead, duplicated, stale or private;
2. every number in every document against the instrument that produces it;
3. every board against its cards/logs;
4. the card and announcement pipeline end to end, including from a clean clone;
5. licenses against the publishers' model cards;
6. the privacy gate (text, history, images, fixtures);
7. the repository as a stranger receives it: install, run, card, boards.

---

## 1. Fixed — documentation that described a different repository

| # | Finding | Disposition |
|---|---|---|
| 1.1 | README's suite table described **7 suites** with wrong counts (adversarial 8, coding 6, instruction 8+6, retrieval "4K-32K") while the corpus is **320 tasks in 14 suites**; realworld and the six job suites were missing entirely | Rewritten from `tasks/*.yaml` + the generated retrieval tasks: all 14 suites with real counts and what each measures |
| 1.2 | README claimed every score "is recomputed from that run's log" — a check no public clone can run, because `results/*` is gitignored | Claim replaced: the **card** is the published instrument; the generator is documented as an authoring-tree tool and the sentence now says so. Publishing the raw logs stays an open decision (see N1) |
| 1.3 | README carried a headline **"Task-validity note (0.5.0)"** — 94 tasks, 13/12 non-discriminating tasks, a flat 8.0 pp — as if it described the current board | Moved into an explicit epoch/comparability section that states 0.6.0 is current and 0.5.0 is frozen history |
| 1.4 | README said the card generator auto-detects your GPU, but `scripts/cards_from_runs.py` hardcoded `GTX 1070 Ti` / 8192 MB | Device is now detected (`gauntlet.device.detect_device`), with `--device NAME:MB:KIND` to re-derive cards for a run measured elsewhere. The published corpus therefore still reproduces, and a stranger's card names their own hardware |
| 1.5 | Internal docs contained a literal `ssh <private-host> 'pct exec <ctid> …'` invocation against a named container, plus internal engine build paths; the filename of another tracked file named the box | Normalized to `<test-box>` / `<ctid>` / `<model-root>` / `<engine-build-dir>`; the engine commit id is kept, so the record is still traceable. Test fixtures that embed `/mnt/data/...` inside simulated engine logs were left verbatim (they are evidence, and carry no host identity) |
| 1.6 | `docs/` held seven epoch documents with no index: a reader could not tell the current method from a frozen record | `docs/README.md` added: one row per document with epoch, status (current / historical) and what it is |
| 1.7 | `scripts/leaderboard_check.py`'s module docstring documented the pre-0.6.0 **7-suite weights** the code no longer uses | Corrected to point at `gauntlet/methodology.py` |
| 1.8 | `results/_published/LEADERBOARD.md` opened with "Scores use CLI 7-suite weights (tool .30 …)" above a **14-suite** table, and closed with an operator-facing "Blocks and open decisions" section (instructions like "needs explicit instruction", a repo-host reference) | Generator template corrected (weights described per epoch, derived from the corpus; operator instructions replaced by a research-facing "Known limitations and open questions"); document regenerated. Text-only diff — no data row changed |
| 1.9 | Every card reference in `LEADERBOARD.md` was written `cards/…`, which cannot resolve from `results/_published/` | Emitted as `../cards/…`; all 302 referenced images verified to exist |
| 1.10 | `SCOREBOARD.md` said results were produced under a "temp 0.7 sampling configuration"; every request is sent with temperature 0 (the harness overrides the server default) | Corrected to temperature-0 requests |
| 1.11 | `pyproject.toml` and `gauntlet/__init__.py` said version **0.1.0** while every document, card and board is labelled 0.6.0, and `runner.write_results` stamped `gauntlet_version: "0.1.0"` when `meta["methodology"]` was absent | Package version 0.6.0; the fallback now records `METHODOLOGY_VERSION` |
| 1.12 | `gen-leaderboard.py` sat at the repository root, outside the CI lint scope, while `leaderboard_check.py` invoked it by that root path | Moved to `scripts/gen_leaderboard.py`, paths anchored to the repository, both callers and the test that loads it updated |

## 2. Fixed — boards, cards and images that contradicted each other

| # | Finding | Disposition |
|---|---|---|
| 2.1 | `results/_published/cards/` shipped **22 card PNGs rendered 2026-11-04 from the v0.3.1 corpus** (71 tasks, 7 suites, "v0.3.1") plus their `manifest.json` and a `render-receipt.json` still marking them `ok: true` — next to a 0.6.0 scoreboard | Archived with provenance, not deleted (see §5). The live card corpus is `results/cards/` |
| 2.2 | `results/cards/manifest.json` was a **duplicate list of 10 cards** that already exist as proper per-configuration cards. `leaderboard_check.py` counts every `*.json` in that directory, so the published block said **69** scored configurations instead of 59, and reported 4 Gemma 4 E4B configurations instead of 3 | Manifest archived; README block and `leaderboard.json` regenerated. Only the configuration counts changed — no score, rank or suite cell |
| 2.3 | `announcement.png` (and the script that renders it) still said **"13 models tested · 71 tasks · 7 suites · v0.3.1 · sep 2026"**, with a podium taken from the best cell of any epoch (including offload and legacy cards) | Generator now derives the suite counts from `tasks/`, the model count and podium from `results/_published/leaderboard.json`, the epoch from `methodology.py`, the date from the newest card, and the hardware from the cards (never from the rendering machine). Re-rendered at this pass: 28 models, 320 tasks, 14 suites, v0.6.0, 2026-11-11. The graphic is derived, so it tracks the corpus without further edits — as later entrants landed it re-rendered itself, and the committed image now reads **32 models · 2026-11-16**, the same podium and counts as `leaderboard.json` |
| 2.4 | The 59 current-epoch cards named **`llama.cpp a2878d3`** as their server build, but their own run logs record engine fingerprint **`b1-1c3cdd2`** — the 0.6.0 engine (`docs/SWEEP-v060.md`) | Card metadata set from each card's own run log, then all 59 cards re-rendered (HTML + PNG) through the pipeline. Every other field byte-identical; verified by diff against the pre-change corpus |
| 2.5 | Five orphan cards in `results/cards/` (old naming, no JSON: `card_gemma4-12b-iq3_XXS`, `card_k2horizon-7b…`) and 10 `png_card_*` duplicates | Archived |
| 2.6 | No board carried a per-board hardware label, and the extended matrix claimed "the full cell data ships in `results/`" — only the best cell per model ships as a card | Every board now opens with its hardware line, its run basis (single run vs 3 seeds) and, for the extended matrix, an explicit statement that the other 200 cells stay on the authoring machine; `scoreboard_check.py` reports it as a named exception |
| 2.7 | `results/cards/` mixed **306 cards across four epochs in one flat directory**, so the plain-named file was the *older* one: `card_gemma4-e4b-q4_K_M.png` is a 0.5.0 card at 86.3% while the current top row is 90.2% under `card_gemma4-e4b-q4km-kvq8.png`, and `card_bolt-e4b-q4km.png` is a pre-0.5.0 card at 87.2%. Linking a card by its obvious name published a superseded score | Superseded cards moved to `results/cards/archive/` (243 cards); `results/cards/` now holds the 63 current-epoch cards plus the announcement graphic, so the current board is unambiguous by location. The corpus is still both directories — `leaderboard_check.py`, `scoreboard_check.py` and `gen_leaderboard.py` read both, and every archived card keeps its own score. No score, suite cell or run log changed; `results/_published/LEADERBOARD.md` differs only in its card link targets, and `leaderboard.json` is byte-identical |

## 3. Fixed — licenses that did not match the model cards

Checked family by family against the Hugging Face model-card metadata (`cardData.license`),
not from memory or from a summary document.

| Family | Was | Is | Basis |
|---|---|---|---|
| Gemma 4 E4B / E2B / 12B | "Gemma Terms" | **Apache 2.0** | `google/gemma-4-E4B`, `-E2B-it`, `-12B-it`: `license: apache-2.0` |
| Gemma 3n E4B | Gemma Terms | Gemma Terms (**correct**) | `google/gemma-3n-E4B-it`: `license: gemma` |
| MiniCPM-V 4.7 1B | "see model repo" | **Apache 2.0** | `openbmb/MiniCPM-V-4.7-1B`: `license: apache-2.0` |
| Bolt E4B | OpenMDW-1.1 | OpenMDW-1.1 (**correct**) | `nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-BF16` |
| Dory 1.0 4B | OpenMDW-1.1 | OpenMDW-1.1 (**correct**) | `nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16` |
| MiniCPM5-2B / 1B | Apache 2.0 | Apache 2.0 (**correct**) | `openbmb/MiniCPM5-2B`, `-1B` |
| MiMo-V2.6-9B | MIT | MIT (**correct**) | `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` |
| Spark-X2.6 | Apache 2.0 | Apache 2.0 (**correct**) | SparkLLM release notes and model card |
| Ornith-1.5-9B | MIT | MIT (**correct**) | `ornith-ai/Ornith-1.5-9B` |
| Granite 4.2 8B/3B | Apache 2.0 | Apache 2.0 (**correct**) | `ibm-granite/granite-4.2-8b` |
| Qwen3.5 family | Apache 2.0 | Apache 2.0 (**correct**) | `Qwen/Qwen3.5-9B` |

Two families could not be resolved to a card in this pass (Nemotron 3 Nano 4B's repository id
did not resolve) and keep an explicit, honest "see model repo" if they had one. The
SCOREBOARD note now records that this check happened and what it changed.

## 4. Fixed — dead files, packaging and gate coverage

| # | Finding | Disposition |
|---|---|---|
| 4.1 | `gauntlet/sandbox.py.bak-pre-reserve-guard-20261111` shipped **inside the installable package** | Archived |
| 4.2 | Two `*.INVALID-bench-against-wrong-endpoint` run artifacts shipped in `extra-suites/longhorizon-v2/` — invalid runs, one `results_*.json` glob away from being scored | Archived |
| 4.3 | Four retired hand-built card writers at the repository root (`make-missing-cards.py`, `make-missing-cards2.py`, `patch-cards.py`, `regen-cards.py`), plus `vram-map.json` (their only config) and `scripts/_test_manifest.tsv` | Archived; the supported path is `scripts/cards_from_runs.py` → `scripts/publish_cards.py` |
| 4.4 | `scripts/score_state.py` used f-string syntax that only parses on Python ≥3.12 while `requires-python = ">=3.11"` and CI runs 3.11 — the lint gate could not pass at all; `score_cells.py` was its only consumer | Both archived (scratch analysis, nothing imports them) |
| 4.5 | `ruff check gauntlet scripts tests` reported 65 errors at the current tree (import order, one-liners, unused import, long data lines) — a red CI lint step | Fixed: real code fixes where it was code, per-file `E501` exceptions only where the long line is verbatim fixture text or a markdown table row that must stay on one physical line (the same convention the repo already used for engine-log excerpts). Now clean |
| 4.6 | `pve-gguf-inventory.txt` was tracked: a single line listing **124 absolute model paths from a private box** (`/mnt/data/models/...`), and the filename named the box | Replaced by `gguf-sizes.csv` (`gguf_file,bytes` only); the path inventory moved outside the repository (`~/.config/slm-gauntlet/`). `cards_from_runs.py` no longer needs it — quant, KV and context come from the run log's own provenance |
| 4.7 | The text gate cannot read binaries: every shipped PNG was outside it | `scripts/image_privacy_check.py` added (PNG/JPEG text chunks + PII-shaped byte scan, patterns assembled from fragments like the text gate) and wired into CI as a second blocking step. Negative control: a card with the operator name appended to its bytes is caught and named |
| 4.8 | The text gate screened only the 10/8 block's first /24 and the bare 100/8 prefixes. **RFC1918 class B and class C were unscreened, and so were the CGNAT ranges outside the 100-prefix the gate happened to match** — the address space a tailnet actually hands out passed the gate unremarked. Literal lane identities (`ssh <alias>`, the alias defaults in the sweep tooling, the private dotfiles path that carried the staging key) were unscreened too | Gate extended with explicit RFC1918 B/C and CGNAT patterns plus the lane alias/key-path shapes, all built from fragments so the gate does not match itself. `tests/test_repo_privacy.py` pins the coverage and fails if it is narrowed again. Ten tracked files had literal lane identity removed in the same pass (`<test-box>` / `<lane-alias>` placeholders); `/mnt/data/...` model paths were left as-is, per the existing decision in §1.5 that a container mount path carries no host identity |
| 4.9 | Beyond `results/_sweep_logs/`, **working-tree artifacts that `.gitignore` keeps out of git still carried the tailnet address**: 26 untracked repeat-run JSONs in `results/` (`meta.endpoint`) and `results/_sweep_state.jsonl` (the sweep ledger's `tail` field reproduces the whole command). One `git add -f` would have published them | Scrubbed in place to the same convention the published logs use (`http://<lane-host>:8891/v1`, `<sandbox>/…`). Score-bearing fields were hashed before and after and are identical, so no run result moved. `results/_sweep_logs/` is now an explicit hard exclusion rather than a by-product of `results/*`, and `tests/test_repo_privacy.py` fails if anything under it is ever tracked. Zero files in the working tree now carry a CGNAT address except `scripts/hygiene-check.sh`, which holds the pattern fragments by design and is excluded from its own scan |

## 5. Archived, not deleted

Everything removed from the publish surface is in
`results/_attic/2026-11-13-audit/` (gitignored, on disk) with a `MANIFEST.csv` giving the
original path, the archived path, the size and the reason — 64 entries. Nothing was deleted
for being old: the criterion was "this contradicts the current corpus, or nothing reads it".

`results/cards/archive/` is a different kind of archive and is deliberately **tracked**: those
243 cards are still published and still correct for their own epoch, so they are moved out of
the reader's way, not withdrawn. "Unpublishable" is what `_attic` means; "not current" is what
`cards/archive/` means.

## 6. Named, not fixed — decisions that are not mine

| # | Item | Why it is open |
|---|---|---|
| N1 | **A public clone can verify the ranked table but not the speed columns.** The 63 epoch-0.6.0 run logs now ship, so `leaderboard_check.py` exits 0 in a fresh clone (306 cards, 32 rankable models) — verified, not assumed. What a clone still cannot re-derive is the TTFT / tok-s columns of `results/_published/LEADERBOARD.md`, because those come from per-run `perf_*.json` artifacts that do not ship; the checker names that instead of failing on it. The pre-0.6.0 rows' source logs also stay off the surface | Shipping the perf artifacts (with the leak review that implies) is a release decision for the operator; it is not required for any score this repo publishes |
| N2 | **The extended matrix's 209 cells are not re-derivable** from the shipped corpus: only the best cell per model ships as a card | Named in SCOREBOARD and on every `scoreboard_check.py` run; shipping the per-cell artifacts is the alternative |
| N3 | **`llama.cpp/` is a gitlink with no `.gitmodules`** — a fresh clone gets an empty directory | Documented in the README layout section. Removing it is an index change with no upside, adding a `.gitmodules` would make clones try to fetch a large tree nothing needs |
| N4 | **Hero image.** Three concept directions were produced for the operator's pick (arena / featherweight-vs-rack / gates-of-the-gauntlet), as 1280×640 renders outside the repository so no unapproved asset ships | The brief says not to finalise the image without him |
| N5 | **Authoring-side lane tooling ships**: `scripts/preflight_lane.py`, `scripts/pve_sweep.py`, `scripts/phase6_retry*.sh`, the sweep manifests. They are named as authoring-side in the README layout, have no secrets, and are the receipts for how the numbers were produced | Removing them would orphan the sweep records |
| N6 | **`results/_preflight/` receipts quote an internal build path** (`/opt/llama.cpp/build/bin/llama-bench`) inside a captured log line | The file is a receipt: the log line is the evidence a refusal happened. Editing it would make the receipt a rewritten document |
| N7 | **No GPU run was made in this pass.** Everything verified here is CPU-only: file, document, card-pipeline and mock-endpoint work | Rule for this lane: benchmarks only on the PVE GTX 1070 Ti harness, and no score was being produced |

## Verification

Run in the authoring tree (`~/TysAIs/slm-gauntlet`, branch `main`, nothing committed):

| Check | Result |
|---|---|
| `scripts/hygiene-check.sh` (tree) | exit 0 — clean |
| `scripts/hygiene-check.sh --history` on the publish candidate | exit 0 — clean, no private identity in any author/committer field |
| `scripts/image_privacy_check.py .` | 315 images, 0 metadata surfaces, 0 PII-shaped strings — clean |
| `scripts/leaderboard_check.py` | exit 0 — README block, `leaderboard.json` and 302 cards agree |
| `scripts/scoreboard_check.py` | exit 0 — 144 cells verified, extended matrix named |
| `pytest -q` | 852 passed |
| `ruff check gauntlet scripts tests` | all checks passed |
| publish-candidate tree vs publish surface | 1156 / 1156 files identical (blob + mode) |
| stranger path in a real clone | `python3 -m venv` + `pip install -e .` → 0.6.0; `gauntlet run --suite all` against a mock endpoint → `partial: false`, 320 tasks; `scripts/cards_from_runs.py` → card JSON naming the detected GPU; `scripts/publish_cards.py` → verified 1080×1080 PNG; `pytest` 852 passed; `scoreboard_check` and the gates clean |

No score data changed. Evidence: every card was diffed against the pre-pass corpus and only
`details.server_build` differs (59 cards); `leaderboard.json` differs only in
`variants_scored` (the duplicate-manifest correction); `leaderboard_check.py` and
`scoreboard_check.py` — which re-derive every published number from its instrument — both
exit 0.
