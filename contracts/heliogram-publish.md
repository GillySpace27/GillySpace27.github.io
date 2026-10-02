# Contract: the Heliogram publish step (heliogram repo to gilly.space)

Drafted 2026-10-01 for WS-4 from heliogram `publish.sh` as last changed in
a73b04a (2026-09-29; read at heliogram@45ac1fc) and heliogram `build.sh:35`.
`publish.sh` is owned by HG-7 and HG-8 (Heliogram register) and edited by SU-1,
SU-3, SU-11 and SU-14 (Suite register). This file changes nothing in the
heliogram repo; `tools/check_site.py` rule `contract` reads the fenced blocks.

## Old and new names

The app was Heliograph through 0.7 and is Heliogram from 0.8 (heliogram
a73b04a; this site's b3806ba). Builds through 0.7 have
`https://gilly.space/heliograph/appcast.xml` compiled in as their Sparkle feed,
and builds 0.6 and earlier read `https://gilly.space/heliograph/version.json`
with the shape `{"version", "build", "page"}`. Builds from 0.8 poll
`https://gilly.space/heliogram/appcast.xml` (heliogram `build.sh:35`). The old
path name is `heliograph/`; the new one is `heliogram/`.

## Must stay tracked

Every path below stays in the tree. The appcast is signed by Sparkle: never
hand-edit it (the warning is at its line 1); a changed appcast comes only from
the signed Heliogram flow. `heliograph/index.html` may become a redirect page
to `/heliogram/` (SU-1); it stays tracked.

```frozen
heliograph/appcast.xml
heliograph/version.json
heliograph/Heliograph-0.7.dmg
heliograph/Heliograph.dmg
heliograph/index.html
```

## What publish.sh writes (a73b04a)

Into `$SITE/heliogram/`, `SITE` defaulting to `$HOME/vscode/Website`
(`publish.sh:6`), after `git pull --ff-only` (`:11`) and
`sign_update --account heliogram --verify build/appcast.xml` (`:15`):

```writes
heliogram/Heliogram.dmg
heliogram/Heliogram-*.dmg
heliogram/version.json
heliogram/appcast.xml
heliogram/index.html
heliogram/privacy.html
```

- `:17` stable name `Heliogram.dmg`; `:21` versioned `Heliogram-<ver>.dmg`
  (the one Sparkle fetches); `:22` `version.json`, `appcast.xml`, and the
  heliogram repo's `site/index.html` and `site/privacy.html`.
- `:23-25` `git add`, commit `Heliogram <ver>`, push. The push is the deploy.

## What publish.sh removes (a73b04a)

- `:13` `git -C "$SITE" rm -r -q --ignore-unmatch heliograph`: every path in
  the frozen block above.
- `:20` `git -C "$SITE" rm -q --ignore-unmatch 'heliogram/Heliogram-*.dmg'`:
  older versioned DMGs (each stays in git history).

## Open conflict: an owner decision

`publish.sh:13` contradicts the frozen block: the next `./publish.sh` would
remove the 0.7 feed, `version.json`, both DMGs and the page from gilly.space, and
installed 0.7 clients would lose their update path. CI turns red afterwards
(`check_site.py` rules `contract` and `feed`) but cannot stop a push made from
the heliogram repo. Routed to Gilly and to the owners of `publish.sh` (HG-7,
HG-8, SU-1). Options recorded here, none chosen:

1. Keep `heliograph/` in place: `publish.sh:13` becomes a comment (HG-7 step 6)
   or a redirect page for `index.html` plus a guard that refuses any other
   staged deletion (SU-1).
2. As 1, plus a final item in `heliograph/appcast.xml` that moves 0.7 installs
   to Heliogram, signed in the Heliogram flow, never hand-edited.
3. Retire `/heliograph/` (Gilly only, Heliogram DECISIONS q13). Even then the
   files stay and every URL keeps working.

The a73b04a commit message says nobody has an older install; the SU-14 and
SU-20 verifiers keep `/heliograph/` live for 0.6 and 0.7 installs. Decision (Gilly,
2026-10-02, decision sheet B3): keep everything; `heliograph/` stays. This
contract keeps the frozen block, and the owners of `publish.sh` (HG-7, HG-8,
SU-1) still have to change `publish.sh:13`. Not re-read by the writer of this
file: `publish.sh` is in the heliogram repo, which was not available.

## Checks

- Rule `contract`: every frozen path is tracked; `FROZEN_FEED` is listed in the
  frozen block; each `version.json` keeps the keys in `VERSION_JSON_KEYS`; once
  any `heliogram/` file is tracked, every `writes` pattern matches a tracked file.
- Rule `feed` (WS-2): both appcasts parse and every gilly.space enclosure they
  name is tracked.
