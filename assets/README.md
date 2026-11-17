# Hero image provenance

`hero.webp` is the README banner: a SLM Gauntlet arena duel, drawn in a bold-outline,
flat cel-shaded cartoon style — two models brawling in the sand pit while a rowdy crowd of other
models watches from the balcony tiers.

## Source

Derived from the selected concept render (2736×912, WebP, sha256
`81e0e2ac349d8c9e1da2dc85f548c9d2338fc7351e053d299c7ec5974409d031`). The composition, characters,
title lockup and palette are that render unchanged.

## Edits applied to the concept before shipping

The concept carried invented benchmark numbers in its crowd signage and a repository URL that does
not exist. Art for a leaderboard may not assert figures the board does not publish, so three signs
were blanked in place — each sign keeps its silhouette, outline and shading; only its lettering is
gone:

| Sign in the concept | Removed | Replaced with |
|---|---|---|
| White cloth banner, upper left | `SCORE: 98.7!` | blank banner |
| Pink hanging banner, right | `RESPONSE: 0.23s!` | blank banner |
| Purple hanging banner, lower right | `RESPONSE: 3!` | blank banner |

The bottom plaque reading `REPO: github.com/slm-gauntlet · BUILD · TEST · CHALLENGE` was cropped
away (the last 46 px of the concept). That path is not this project's URL, and the publication
destination is still undecided, so no URL is baked into the artwork.

Then the image was resized to 1920×608 and re-encoded with no metadata — no EXIF, XMP or text
chunks ride along (verified by `scripts/image_privacy_check.py`).

The counts and the score live in the README as text, next to the image, not inside it:
**320 tasks · 14 suites · 32 models ranked**, best 90.2% on 8 GB.

Two small robot nameplates inside the arena (`TOKEN: 128k`, `MODEL: GPT-LITE`) are left as drawn.
They label the two fictional fighters, not board entrants, and they are below 8 px tall at README
width.
