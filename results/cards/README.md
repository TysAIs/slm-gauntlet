# Card corpus layout

**`results/cards/` holds the current epoch only.** Everything here is epoch 0.6.0
(320-task corpus, 14-suite weights): 63 configurations, each as `.json` (the
instrument the score is computed from), `.html` (the template) and `.png` (the
rendered card), plus `announcement.png` / `.html`.

**`results/cards/archive/` holds everything superseded.** 243 cards from epochs
0.5.0, 0.5.1 and v0.3.1. They are still published and still correct for their own
epoch — the leaderboard's legacy table and the reproducibility claim both need
them — but they are not comparable with the current board, and they are not in
the way of it.

## Why the split

Both directories used to be one flat directory of 306 cards. That made the
filename ambiguous: `card_gemma4-e4b-q4_K_M.png` (a 0.5.0 card, 86.3%) sat next
to `card_gemma4-e4b-q4km-kvq8.png` (the current top row, 90.2%), and the
plain-named file was the *older* one. Anyone linking a card by its obvious name
published a superseded score. Splitting by epoch makes the current board
unambiguous by location rather than by convention.

No score, suite cell or run log was changed by the move — only file locations.

## Reading the corpus

Both directories are the corpus; the checkers read both:

- `scripts/leaderboard_check.py` — one row per model, best configuration of each.
- `scripts/scoreboard_check.py` — per-board verification, canonical seed-1 cells.
- `scripts/gen_leaderboard.py` — the long-form `results/_published/LEADERBOARD.md`.

Each card names its own epoch in `details.methodology`, so a card is never
compared across methodologies: a card without that field is pre-0.5.0.
