# gilly.space

Personal + academic website of **Dr. Gilly**, heliophysicist
at [NorthWest Research Associates (NWRA)](https://www.nwra.com) — solar wind,
coronal heating, forward models, and observation validation. Plus a creative
wing (music, theater, public talks) and a few interactive web toys.

Live at **[gilly.space](https://gilly.space)**.

[![check](https://github.com/GillySpace27/GillySpace27.github.io/actions/workflows/check.yml/badge.svg)](https://github.com/GillySpace27/GillySpace27.github.io/actions/workflows/check.yml) [![site-checks](https://github.com/GillySpace27/GillySpace27.github.io/actions/workflows/site-checks.yml/badge.svg)](https://github.com/GillySpace27/GillySpace27.github.io/actions/workflows/site-checks.yml)

## How it's built

Fully static, deployed via **GitHub Pages** (push to the default branch → live).
One **Cloudflare Worker** powers the enso AI impressions (`worker/`). No npm, no
bundler — vanilla HTML/CSS/JS by design.

## Stamping shared assets

After editing `assets/site.css`, `assets/product.css`, `assets/site.js`,
`assets/product.js` or anything in `partials/`, run `python3 bump-assets.py`.
It rewrites the `?v=` stamp on every link to those files in the HTML pages git
tracks in this checkout (never `.claude/worktrees/`), and sets `sw.js`
`CACHE_VERSION` to `gilly-<stamp>` so returning visitors drop the old
service-worker cache. `python3 bump-assets.py --dry-run` lists what would
change and writes nothing. `python3 bump-assets.py --check` writes nothing and
exits 1 naming each page whose stamp is missing or differs, and `sw.js` when its
`CACHE_VERSION` does not match.

## Layout

| Path | What it is |
|---|---|
| `index.html` | Homepage |
| `Research.html`, `PastResearch.html` | Research overviews |
| `sun.html` | Live "Sun right now" RHE/RHEF viewer (S3-backed) |
| `resources.html` | Solar-physics link directory |
| `RecordedPublicTalks.html`, `Space-Is-Full.html`, `Kelvin.html` | Outreach & science writing |
| `Music-and-Theater.html`, `skitPage.html` | Creative work |
| `shop.html` | My Heliograph print store landing (links to myheliograph.com) |
| `enso/` | Daily AI-narrated enso calendar + editor |
| `sudoku/` | Spectrum Sudoku |
| `worker/` | Cloudflare Worker (Workers AI one-line evocation + KV cache) |
| `assets/site.css`, `assets/site.js`, `partials/` | New unified design system ("Heliostatic") |
| `REDESIGN.md` | Full redesign proposal & roadmap |

## Redesign in progress

The site is being modernized off its decade-old HTML5 UP "Strata" template onto
one hand-authored design system that shares the enso toys' tokens and dark mode.
See **[REDESIGN.md](REDESIGN.md)** for the plan and phased roadmap. The enso
project's deeper docs live in **[enso/CLAUDE.md](enso/CLAUDE.md)**. Agents start at
**[CLAUDE.md](CLAUDE.md)**; runbooks are in **[SITE.md](SITE.md)**.
