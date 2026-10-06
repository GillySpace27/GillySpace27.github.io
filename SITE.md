# SITE.md: runbooks for gilly.space

One section per topic; an initiative edits only its own section. Commands run
from the repo root. Every push, merge to `master`, tag push and Worker change
waits on Gilly's yes for that one action.

## Deploy

- GitHub Pages serves branch `master` of `GillySpace27/GillySpace27.github.io`
  as committed (no build step). A push or merge to `master` is a deploy.
- Work on a branch `claude/<id>-<slug>`, run "Before you push" in `CLAUDE.md`,
  then ask Gilly; he approves the push or the merge.
- Verify after Pages finishes by content, not status code:
  `curl -s "https://gilly.space/<path>?cb=$(date +%s)" | grep -c '<a string you added>'`
  prints 1 or more.
- Undo: `git revert <sha>` on a branch, then the same yes-gated push. Never
  force-push and never reset `master`. WS-9 adds the rehearsed `## Rollback`.

## Jekyll and the .md spec documents

Decision (2026-10-02, branch `claude/wave1-website`): the repo root carries an
empty `.nojekyll`, so the branch source serves files as committed.

- Why: `heliosoftware/spec/index.html` links raw `.md` files (`attic.md`,
  `agent-preamble.md`, `rhef/conventions.md`, `release-feed.md`), and other
  repos' `CLAUDE.md` files and `heliosoftware/spec/SHA256SUMS` point at
  `https://gilly.space/heliosoftware/spec/agent-preamble.md`. With no
  `.nojekyll`, Pages' default Jekyll pass (jekyll-optional-front-matter) renders
  a `.md` file that has no front matter as `.html`, so the `.md` URL would
  probably 404 (inferred from how Pages works, never probed).
- Evidence that nothing needs Jekyll: no `_config.yml`, `Gemfile`, `_layouts`,
  `_includes` or `_posts`; no tracked `.html`, `.md` or `.scss` file starts with
  `---` front matter; no Liquid tag (`{%`, `{{ name }}`) in any tracked page;
  the only underscore files are `assets/sass/libs/_*.scss` partials that no page
  links (the compiled CSS is committed); `enso/CLAUDE.md` already said "nothing
  here uses Jekyll features".
- Which URL form is live under which source:
  - Branch source with `.nojekyll` (this branch): `/heliosoftware/spec/agent-preamble.md`
    is served as the file; `.html` twins of the `.md` files do not exist.
  - Branch source without `.nojekyll` (master before this branch): the `.md` URLs
    probably 404 and `/heliosoftware/spec/agent-preamble.html` would be live.
  - Actions artifact (`pages.yml`, `tools/make_artifact.py`): Jekyll never runs, so
    the `.md` files are served as committed; `.nojekyll` is not copied (the
    artifact skips every path with a dot component) and is not needed.
- Side effect to know: with `.nojekyll`, Pages also publishes tracked paths that
  start with a dot or underscore (`.mailmap`, `.editorconfig`, `.gitattributes`,
  `.gitignore`, `.github/`, `assets/sass/libs/_*.scss`). The repo is public, so
  nothing new is disclosed, but those URLs become reachable on the branch
  source. The Actions artifact never publishes them.
- Static check: the `nojekyll` rule of `tools/check_site.py` fails when a page
  links a tracked `.md` file and `.nojekyll` is not tracked; the `link` rule
  already fails a `.md` link whose file is missing.

Post-merge checklist (Gilly, after the merge to `master` and Pages finishing):

- [ ] After the merge, request `/heliosoftware/spec/agent-preamble.md` once and
      confirm it is served (status 200 and the preamble text, not a 404 or an
      HTML page). If it is not, remove `.nojekyll` in a branch and tell Claude.

## Stamping

- After editing `assets/site.css`, `assets/product.css`, `assets/site.js`,
  `assets/product.js` or a file in `partials/`, run `python3 bump-assets.py`. It
  rewrites the `?v=<12 digits>` stamp on links to those files in tracked pages
  (`git ls-files`) and `CACHE_VERSION` in `sw.js`. Commit the stamped pages and
  `sw.js` with the change.
- `python3 bump-assets.py --dry-run` lists what it would change and writes
  nothing; `--check` exits 1 and prints `STAMP <path>: <reason>` per offender.
- `heliograph/index.html` and `heliogram/index.html` come from the Heliogram
  publish step; `--check` only warns on them.
- A comment-only edit in a partial changes nothing visible and needs no stamp.

## CI

- `.github/workflows/check.yml` runs on every push and pull request: the unit
  tests (`python3 -m unittest discover -s tools/tests -p 'test_*.py'`),
  `python3 tools/check_site.py`, and `node --check` on the site's scripts.
- Red means one of: a link or asset that does not resolve with exact case; a
  short-link stub whose target is not a page; a malformed `manifest.json`,
  `version.json`, `appcast.xml` or `sitemap.xml`; a frozen update-feed file or
  an enclosure it names missing from the tree; stamps out of step; a tracked
  file over 10 MB not listed in `tools/size_allowlist.txt`. Lines read
  `<LEVEL> <rule> <path>:<line> <target> :: <message>`.
- `tools/known_failures.txt` lists breakage already reported to Gilly; matching
  findings print as `KNOWN` and do not fail the run. Add a line only for a
  finding Gilly has seen, never to silence a new failure.
- A red check does not stop Pages from publishing until WS-9 lands and Gilly
  switches the Pages source.
- Job `em-dash` (`heliosoftware/spec/tools/no_em_dash.py`) fails when a change adds a
  line containing U+2014; older lines are never flagged, but a line you edit counts
  as added. It skips `heliogram/` and `heliograph/` (the publish step writes them).
  Locally: `python3 heliosoftware/spec/tools/no_em_dash.py --base origin/master`.
  `pages.yml` reuses `check.yml`, so this job also gates the Pages deploy.
  Every `uses:` in `.github/workflows/` is pinned to a commit SHA with the tag in a
  comment (`test_workflows_su10.py`).

## Worker

- `worker/worker.js` and `worker/wrangler.toml` are the `enso-impressions`
  Worker (Workers AI, KV binding `IMPRESSIONS`). Cloudflare Workers Builds
  deploys it on any push to `master` that touches `worker/`, a README-only
  change included. There is no CLI deploy.
- Health: `curl -s https://enso-impressions.gilly-22d.workers.dev` prints
  `enso-impressions worker is alive (Workers AI / Llama 4 Scout / one-line evocation)`
  (`worker/worker.js:115`).
- Caching is on (`CACHE_ENABLED = true`, `worker/worker.js:43`); keys are
  `impression-v2:<date>` (`worker/worker.js:149`). KV rows and dashboard
  settings are Gilly's; agents never delete them. Manual: `enso/CLAUDE.md` and
  `worker/README.md`.

## Enso

- `enso/index.html` (the calendar) and `enso/enso-engine.js` (the engine the home page hero loads) are both
  GENERATED by `node enso/build_calendar.js` from `enso/pixelated-enso.html` (the editor, the source of truth
  for the engine) and the page template inside `enso/build_calendar.js`. Do not edit either generated file by hand.
- The calendar does not inline the engine: it loads `<script src="/enso/enso-engine.js?v=<hash>">`, where
  `<hash>` is the first 12 hex digits of the engine file's sha256, written by the build (WS-12 phase 2). A new
  engine therefore gets a new URL, so no browser or service-worker cache pairs a new page with an old engine.
- Change the calendar page (markup, CSS, calendar JavaScript, the live Worker URL, the analytics tag): edit the
  template literal in `enso/build_calendar.js`. Inside it write `<\/script>` for a closing script tag, never a
  backtick or `${`, and two backslashes before `n` for a newline escape inside a JavaScript string (the template
  literal consumes one).
- Change the engine: edit `enso/pixelated-enso.html`. Never reorder or insert a PRNG draw without updating editor
  and calendar together, and keep the 52-control assertion (`enso/CLAUDE.md`).
- After any change, in this order:
  1. `node enso/build_calendar.js` (writes both generated files)
  2. `node enso/build_calendar.js --check` (expect `enso build --check: ok`)
  3. `node --test tools/tests/test_enso_golden.mjs` (expect `fail 0`)
  4. commit all of `enso/` together.
- `--check` writes nothing and exits 1 with the first differing line. `--out PATH` writes a calendar to PATH and an
  engine beside it (a safe preview). `python3 tools/check_site.py` and CI both run `--check`.
- `enso/golden.json` holds, for the first of each month of 2026, the engine's settings, shape seed and a hash of
  its 2D-context calls. A mismatch means a day's ensō changed. If that is intended, run
  `UPDATE_GOLDEN=1 node tools/tests/test_enso_golden.mjs`, say in the commit that pictures change, and tell Gilly:
  the Worker caches one impression per date (`impression-v2:<date>`) and the cached text was written for the old picture.

## Pages manifest

- `site.json` is the one list of public pages: nav, page titles, palette
  entries, sitemap entries and redirect stubs. `python3 tools/bake.py` copies it
  into the places that cannot read JSON at run time: `HEADER_FALLBACK` and the
  palette `ITEMS` in `assets/site.js`, the `<noscript>` nav of each page that
  carries `<!-- bake:noscript -->`, the nav in `partials/header.html` between
  `<!-- bake:header-nav -->` markers, `sitemap.xml`, and the redirect pages
  listed under `stubs` (templates in `tools/templates/`).
- Edit `site.json`, run `python3 tools/bake.py`, commit both. Never edit between
  `bake:` markers by hand: `python3 tools/bake.py --check` (also run by
  `tools/check_site.py` as rule `bake`) prints `DRIFT <path> <target>` and exits 1.
- After `bake.py` changes `assets/site.js`, run `python3 bump-assets.py`.
- `site.json` is written with `json.dumps(indent=2, ensure_ascii=True)`, so
  non-ASCII text appears as `\uXXXX`. `title`, `palette` and `keywords` are HTML or
  JS source text and are inserted as written.
- Sitemap `lastmod` comes from `git log -1 --format=%cs -- <page>`; a shallow CI
  clone cannot reproduce it, so `--check` ignores `lastmod`. Pages in
  `tools/archived_pages.txt` and `heliograph/`, `heliogram/` are not in the
  sitemap (the publish step owns the last two).

## The Sun page

- `sun.html` is driven by `assets/sun.js` (`window.SunData`, `window.SunStage`). The
  manifest fields it reads are pinned in `contracts/sun-bucket.md`; `check_site.py`
  rule `contract` scans `sun.html` and `assets/sun.js` for any other `m.<field>`.
  `PRODUCTS` in `sun.html` is never edited (other repos parse it).
- Freshness pills use 60 and 180 minutes (`FRESH_OK_MIN`, `FRESH_STALE_MIN`; Gilly's
  decision A5). The internal alarm in Sunback is tighter and is not this.
- The Stage (the large clip with the scrubber and channel strip) keeps the same moment
  when you change channel by aligning the clips' newest-frame times on a 20 minute grid.
  Per-slot times from the producer (SB-14) are not written yet, so the time label says
  "about". Channel temperatures come from `instruments/AIA.md` in the vault (section 4,
  lines 65-73); change them there first, then in `CHANNELS` and in
  `tools/tests/js/sun_stage_check.mjs`.
- Checks: `python3 -m unittest discover -s tools/tests -p 'test_*.py'` runs the Node
  checks in `tools/tests/js/` (node as a bare runtime, no npm). Motion and touch need a
  real browser; see the PR notes for what was run.

## Share links

- `/s/<id>/` is one redirect per Sun channel (`/s/171/`, `/s/rainbow/`, ...). Each page
  carries `og:title`, `og:image` and a Twitter card for that channel, then sends the
  visitor to `/sun.html#<id>`, where the card scrolls into view and is outlined for a few
  seconds. Lowercase ids only (Pages is case-sensitive).
- The stubs are generated: `python3 tools/bake.py --only share` writes `s/<id>/index.html`
  from `tools/templates/share.html` and fills `site.json` `share` from the `PRODUCTS` labels
  and the `img1k` key of each manifest in `fixtures/sun/manifest/`. After
  `python3 fixtures/sun/capture.py --refresh`, bake again. `bake.py --check` (rule `bake`)
  fails on a hand edit. The stubs are not in `sitemap.xml` and carry `noindex`.
- `og:image` is the bucket URL of the channel's newest 1k still. This session could not
  HEAD those URLs (no live calls), so confirm each returns 200 after a deploy, and send
  one `/s/` link to yourself to see it unfurl.
- The Share button on each card calls `SunData.share` (native sheet, else clipboard, else
  `execCommand`) and shows a toast with the link.

## Page head and icons

- The shared part of a shell page's `<head>` (title, description, canonical,
  the theme pre-paint script, Open Graph and Twitter tags, favicons, theme
  colours, the Search Console meta) is `partials/head.html` between its
  `<!-- bake:template -->` markers. `python3 tools/bake.py` writes it into each
  page between `<!-- bake:head -->` markers, with the values from `site.json`
  (`title`, `description`; optional `head_title`, `canonical`, `og_image`,
  `og_url` to make og:url say what the canonical says, and `no_canonical: true`
  for a page served at many URLs such as `404.html`, which then carries neither).
  Anything page-specific (preconnect, JSON-LD, extra CSS) stays after the closing
  marker. A new shell page: add it to `site.json`, put the two marker lines right
  after `<head>`, run `python3 tools/bake.py`.
- Icons are the sprite `assets/icons.svg`, generated by
  `python3 tools/build_icons.py` from the SVG fonts in `assets/fonts/`. Markup:
  `<svg class="icon" aria-hidden="true"><use href="/assets/icons.svg#github"></use></svg>`.
  `tools/check_site.py` rule `icons` fails on `fa fa-` or `ai ai-` in a live page.
- Images: `python3 tools/make_webp.py <png>` writes a `.webp` beside the PNG and
  never overwrites. Wrap the `<img>` in `<picture>` with the WebP `<source>`; the
  PNG stays as the fallback.
- After changing `assets/site.css`, `assets/site.js` or a partial, run
  `python3 bump-assets.py`.

## Short links

- Each short link is a static `index.html` that redirects with a meta refresh
  and `location.replace`: `hfs/`, `hfstudio/`, `punchstudio/` and `jhv/` go to
  `/heliofits-studio/`; `shop/` goes to `/shop`.
- Pages is case-sensitive: hand out lowercase only. `404.html` sends a cased
  address to its lowercase twin (`404.html:9-11`); add a cased duplicate folder
  only on Gilly's yes.
- New short link: add an entry to `stubs` in `site.json` (`path`, `title`,
  `target`, `template` `stub.html`), run `python3 tools/bake.py`, then
  `python3 tools/check_site.py --only stub bake`. Lowercase only; a cased
  duplicate needs Gilly's yes. Follow the redirect after deploy (below).
- After deploy, follow the redirect and check the destination page's content.
  A 200 alone proves nothing (GitHub served 200 for an empty tag page in the
  2026-08-24 `/jhv` incident).
- `heliosoftware/spec/shortlinks.json` lists every tracked redirect stub and where it must end. `python3 tools/check_site.py` fails when a stub drifts from it and warns about an unlisted stub (`--write-shortlinks` regenerates the file; new stubs must be `git add`ed first).
- `python3 tools/check_site.py --online` follows each stub on the live site to its destination (read-only GETs), and checks that the live 404 page still lowercases the address. The `site-checks` workflow runs it daily at 06:23 UTC.

## RHEF spec decisions

- 2026-10-02 (decision B5 and question 9, Gilly): the RHEF tie rule is "average"
  (equal pixel values get the average of their ranks; `heliosoftware/spec/rhef/conventions.md`
  section 2, status adopted). A conformance runner may run in enforce mode for a
  port once that port passes the golden vectors; no port is recorded as passing yet
  (section 7 still reads "No results recorded yet."). After editing a spec file run
  `python3 heliosoftware/spec/spec_sums.py --write`.

## Heliogram publish

- The Heliogram app (named Heliograph through 0.7) publishes into this repo
  from `/Users/gilly/vscode/heliogram/publish.sh`: it pulls, copies the DMG,
  `version.json`, `appcast.xml`, `index.html` and `privacy.html`, commits
  `Heliogram <ver>` and pushes, which deploys.
- As of heliogram a73b04a (2026-09-29) it writes to `heliogram/` and runs
  `git rm -r --ignore-unmatch heliograph` (`publish.sh:13`): the next publish
  would remove the frozen `heliograph/` feed that installed 0.7 builds poll.
  Open conflict for Gilly; `publish.sh` belongs to HG-7, HG-8 and SU-1; the
  written contract is `contracts/heliogram-publish.md` (WS-4).
- Agents never run `publish.sh` or `ship.sh`, never hand-edit either
  `appcast.xml`, and never edit files the publish step writes.

## Studio fallback pin

`heliofits-studio/index.html` asks GitHub for the newest release when a visitor
opens it (`releases?per_page=1`, never `/releases/latest`). The links written into
the page are the fallback for a visitor whose request to GitHub fails, so they
must name the newest release too.

- After each HelioFITS Studio release, once CI has attached the Windows and Linux
  packages: `python3 tools/pin_studio_fallback.py --from-github --dry-run`, then
  without `--dry-run`. It refuses unless every asset in
  `contracts/studio-release-assets.md` exists, and unless the new version occurs
  exactly as often as the old one did. Commit, then a push needs Gilly's yes.
- The live-site watch (`tools/watch.py`, probe `studio`) fails while the pin is
  behind the newest release.
- The script never touches `PLATFORMS` or a `confirmed` flag. To light a tile:
  someone installs and runs that platform's build on a real machine of that
  kind; then Gilly sets `confirmed: true` for it by hand in `PLATFORMS`, in its
  own commit.
- Proposal for the Studio release flow (HS-21; the Studio session decides):
  `release/deploy_release.sh publish` could print this command, or run the
  dry run, after `gh release create`.

## Rollback

Applies once Pages is published by `.github/workflows/pages.yml` (WS-9). Until
Gilly sets the repository variable and switches the source, `## Deploy` is
still the live path.

- What is live: `curl -s "https://gilly.space/build.json?cb=$(date +%s)"` prints
  `{"commit": ..., "ref": ..., "stamp": ..., "built_utc": ...}`. `commit` is the
  published commit; compare with `git log --oneline -10 master`.
- Normal publish: a push to `master` runs `check.yml`; only if it is green does
  `pages.yml` build the artifact from that commit, deploy it, wait until
  `build.json` names the commit and run the watch probes once. A red check means
  no deploy and the previous site stays up. A push to `master` still needs
  Gilly's yes.
- Roll back (a deploy; needs Gilly's yes): choose the last good commit `<sha>`
  (it must already be on `master`; the run refuses anything else), then
  `gh workflow run pages.yml -R GillySpace27/GillySpace27.github.io -f ref=<sha>`.
  Add `-f skip_checks=true` only when `master` itself is red. Confirm with
  `python3 tools/verify_deploy.py --expect-sha <sha>`: it must print `PASS`.
- Return to the tip: the same command without `-f ref=...`.
- Rehearse without deploying: add `-f dry_run=true`; the run stages the artifact
  and stops before the deploy job.
- History is never touched: no force-push, no reset of `master`, no tag
  removal. The workflow publishes an earlier commit; `git revert` on a branch is
  still the way to fix `master` itself.
- Heliogram update feeds: a rollback across a Heliogram publish serves the older
  `heliograph/` and `heliogram/` feed files. After any rollback run
  `python3 tools/watch.py --probe feeds`. Never hand-edit `appcast.xml`.
- Heliogram publish: `publish.sh` pushes to `master`, which now waits for the
  gate (minutes, not seconds). Afterwards run
  `python3 tools/verify_deploy.py --expect-sha "$(git -C ~/vscode/Website rev-parse HEAD)"`.
- Back to the branch source (Gilly does it): Settings > Pages > Build and
  deployment > Source > "Deploy from a branch" > `master` / `(root)`, then
  `gh variable set PAGES_VIA_ACTIONS --body false -R GillySpace27/GillySpace27.github.io`.
  Nothing else changes; `CNAME` stays tracked.
- `watch.yml`'s `page_build` trigger does not fire for deploys made by Actions;
  the `verify` job of `pages.yml` runs the same wait and probes instead.
