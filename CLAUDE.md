# gilly.space: guide for agents

> **Site-wide:** after editing `assets/site.css`, `assets/product.css`, `assets/site.js` or
> anything in `partials/`, run `python3 bump-assets.py` so every page requests the new files.

<!-- heliosoftware-preamble v1 -->
<!-- /heliosoftware-preamble -->

## What this repo is

Gilly's personal and professional site: static HTML, CSS and JS served by GitHub
Pages from `master` of `GillySpace27/GillySpace27.github.io`. A push to `master`
is a deploy. No build step, no npm. One Cloudflare Worker under `worker/` (enso
impressions) redeploys through Workers Builds on any push that touches `worker/`.
Runbooks: `SITE.md`. Enso calendar, editor and Worker manual: `enso/CLAUDE.md`.
Retired items: `ATTIC.md`. History: `CHANGELOG.md`. `LICENSE.txt` is the HTML5 UP
template licence only; a licence for Gilly's own content is his decision (open).

## Frozen: never rename, move or remove

- `heliograph/appcast.xml`, `heliograph/version.json` and the DMGs they name:
  installed Heliograph builds poll them. Never hand-edit an `appcast.xml` (Sparkle
  signature; warning at its line 1). Contract: `contracts/heliogram-publish.md` (WS-4).
- Short links handed out in mail, posters and talks: `/hfs/`, `/hfstudio/`,
  `/punchstudio/`, `/jhv/`, `/heliofits/`, `/heliograph/`, `/shop/`. Pages is
  case-sensitive: hand out lowercase only, or add the cased duplicate at the same time.
- `CNAME`, `google690400622efc7ebc.html`, the favicons, `manifest.json`,
  `browserconfig.xml`. Every existing URL keeps working.

## Must-nots

- Delete nothing: no `rm` or `git rm` of a tracked file, no force-push, no history
  rewrite, no branch or tag deletion. Retire a file with an `ATTIC.md` row (left in
  place); retire a branch with an `archive/<branch>` tag.
- No push, merge to `master`, tag push or Worker change without Gilly's yes for that
  one action.
- No em dashes in anything you write: copy, comments, commit messages.
- No npm, no bundler; `node` only as a bare runtime.
- Do not run `node enso/build_calendar.js` until its `--check` exists and reports
  zero diff (WS-12): today it blanks the live Worker URL in `enso/index.html`.
- Never run the Heliogram repo's `publish.sh` or `ship.sh`; never GUI-launch any
  Heliograph or Heliogram copy.
- Keep the HTML5 UP CC BY 3.0 credit (`partials/footer.html`) while any page uses
  Strata CSS. `files/CV.docx` stays untracked; `evan/` stays.
- Never touch `.claude/worktrees/` or another session's branch. Call him Gilly.

## Commands

| Task | Command |
|---|---|
| Serve locally | `python3 -m http.server 8000`, then `http://localhost:8000/` |
| Stamp shared assets | `python3 bump-assets.py` (`--dry-run` lists, `--check` verifies) |
| Check the site | `python3 tools/check_site.py` |
| Run the tests | `python3 -m unittest discover -s tools/tests -p 'test_*.py'` |
| Worker health | `curl -s https://enso-impressions.gilly-22d.workers.dev` |

## Before you push

1. `python3 tools/check_site.py` exits 0 (KNOWN lines are listed breakage, not new).
2. `python3 bump-assets.py --check` exits 0.
3. The unit tests pass.
4. `git status --short` shows only what you meant to change.
5. Ask Gilly for this push. A push to `master` goes live; a push that touches
   `worker/` also redeploys the Worker.
