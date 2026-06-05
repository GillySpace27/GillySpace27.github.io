# gilly.space

Personal + academic website of **Dr. Chris Gilbert ("Gilly")**, heliophysicist
at [NorthWest Research Associates (NWRA)](https://www.nwra.com) — solar wind,
coronal heating, forward models, and observation validation. Plus a creative
wing (music, theater, public talks) and a few interactive web toys.

Live at **[gilly.space](https://gilly.space)** (also `chrisgilbert.space`).

## How it's built

Fully static, deployed via **GitHub Pages** (push to the default branch → live).
One **Cloudflare Worker** powers the enso AI impressions (`worker/`). No npm, no
bundler — vanilla HTML/CSS/JS by design.

## Layout

| Path | What it is |
|---|---|
| `index.html` | Homepage |
| `Research.html`, `PastResearch.html` | Research overviews |
| `sun.html` | Live "Sun right now" RHE/RHEF viewer (S3-backed) |
| `resources.html` | Solar-physics link directory |
| `RecordedPublicTalks.html`, `Space-Is-Full.html`, `Kelvin.html` | Outreach & science writing |
| `Music-and-Theater.html`, `skitPage.html` | Creative work |
| `shop.html` | Solar Archive print store (links to solar-archive.onrender.com) |
| `enso/` | Daily AI-narrated enso calendar + editor |
| `sudoku/` | Spectrum Sudoku |
| `worker/` | Cloudflare Worker (Workers AI haiku + KV cache) |
| `assets/site.css`, `assets/site.js`, `partials/` | New unified design system ("Heliostatic") |
| `REDESIGN.md` | Full redesign proposal & roadmap |

## Redesign in progress

The site is being modernized off its decade-old HTML5 UP "Strata" template onto
one hand-authored design system that shares the enso toys' tokens and dark mode.
See **[REDESIGN.md](REDESIGN.md)** for the plan and phased roadmap. The enso
project's deeper docs live in **[CLAUDE.md](CLAUDE.md)**.
