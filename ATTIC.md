# Attic

Items retired from use and left in place (delete nothing). A row says what the
item was, why it is retired and what replaced it. Moving an item under `attic/`
is a later, separate step; removing one is never an agent's step.

| Path | What it was | Why retired | Replacement | Date |
|---|---|---|---|---|
| `bkk/` | `main.css` and an extracted academicons 1.8.6 tree (10 files) | referenced by no tracked file | `assets/css/academicons.min.css`, `assets/site.css` | 2026-10-02 |
| `assets/sass/` | HTML5 UP Strata SCSS sources (6 files) | IE8-era template sources; nothing compiles or loads them | `assets/site.css` | 2026-10-02 |
| `assets/js/s3_PhotoViewer.js` | browser gallery for the `the-sun-now` bucket through the AWS SDK and a Cognito identity pool | referenced by no tracked page | `sun.html` | 2026-10-02 |
| `images/thumbs/spectrometer.bmp` | 1960x1260 BMP copy of the spectrometer thumbnail | referenced by nothing; the PNG is the one used | `images/thumbs/spectrometer.png` | 2026-10-02 |
| `navbar.shtml` | server-side include for the old nav | GitHub Pages never processed SSI; named only as history in `archive/index.html:84` | `partials/header.html` | 2026-10-02 |
| `headerScript.ssi` | server-side include for the old head script | as `navbar.shtml` (`archive/index.html:84`) | `partials/head.html`, `assets/site.js` | 2026-10-02 |
| `files/quad.mp4` | video (content not reviewed) | referenced by no tracked page | none | 2026-10-02 |
| `files/windowPlot3.mp4` | video (content not reviewed) | referenced by no tracked page | none | 2026-10-02 |
| `README.txt` | HTML5 UP template readme | template history; named in `archive/index.html:85` | `README.md` | 2026-10-02 |
| `assets/css/font-awesome.min.css` | Font Awesome 4.6.3 stylesheet (webfont files in `assets/fonts/`) | no live page links it since the icon sprite; `assets/fonts/fontawesome-webfont.svg` stays because `tools/build_icons.py` reads it | `assets/icons.svg` | 2026-10-02 |
| `assets/css/academicons.min.css` | Academicons 1.8.6 stylesheet (webfont files in `assets/fonts/`) | linked only by the archived `shineVideo.html` since the icon sprite; `assets/fonts/academicons.svg` stays because `tools/build_icons.py` reads it | `assets/icons.svg` | 2026-10-02 |

## Branches and worktrees

| Ref | What it was | Why retired | Archive tag | Date |
|---|---|---|---|---|
| `claude/heliofits-sibling-link` (`f7c42b8`) | one commit, 2026-09-23 | superseded by `a73968f` on `master` (same subject with "(#1)"); merging it would revert later head changes | `archive/heliofits-sibling-link` | 2026-10-02 |
| worktree `.claude/worktrees/whichclaude-site-integration-4adfaf`, detached at `ff91b7f` | whichclaude site integration, 2026-08-05 | its branch is fully merged; its 17 dirty files are stamp-only rewrites by the old stamper | `archive/whichclaude-worktree-ff91b7f` | 2026-10-02 |

The branch and the worktree stay in place; only Gilly retires them further.

## Canonical rows

The same retirements in the suite's row format (https://gilly.space/heliosoftware/spec/attic.md). The tables above keep their own columns and are not rewritten. Rows are appended.

| What | Where it is now | Why | Restore command | Date |
|---|---|---|---|---|
| branch `claude/heliofits-sibling-link` | branch `claude/heliofits-sibling-link` left in place; tag `archive/heliofits-sibling-link` at tip f7c42b8 | Superseded by a73968f on master (same subject); merging it would revert later head changes | `git switch --detach archive/heliofits-sibling-link` | 2026-10-02 |
| worktree `.claude/worktrees/whichclaude-site-integration-4adfaf` | same path, detached; tag `archive/whichclaude-worktree-ff91b7f` at tip ff91b7f | Its branch is fully merged; its 17 dirty files are stamp-only rewrites by the old stamper | `git switch --detach archive/whichclaude-worktree-ff91b7f` | 2026-10-02 |
