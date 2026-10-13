# Publish handshake

Which files each HelioSoftware product may write into this repository
(`GillySpace27.github.io`, the site behind gilly.space) when it releases. The rule:
products write data; this repository owns pages.

Decisions (Gilly, 2026-10-12 and 2026-10-13): this repository owns `heliogram/index.html`
and `heliogram/privacy.html`; Heliogram's `publish.sh` writes release data only; alpha-phase
Heliogram DMGs may go to GitHub Releases on this repository, behind a switch that is off by default.

| Product | Writes (paths under the Website repo) | Never writes |
|---|---|---|
| Heliogram | `heliogram/Heliogram.dmg`, `heliogram/Heliogram-<ver>.dmg`, `heliogram/version.json`, `heliogram/appcast.xml`, `heliograph/index.html`, `heliosoftware/feed/heliogram.json`, `heliosoftware/feed.xml`, `heliosoftware/whats-new/index.html` | `heliogram/index.html`, `heliogram/privacy.html`, any other page, `assets/`, `sitemap.xml`, `heliograph/appcast.xml`, `heliograph/version.json`, `heliograph/Heliograph.dmg`, `heliograph/Heliograph-0.7.dmg`, a deletion of anything but an old `heliogram/Heliogram-*.dmg` |
| HelioFITS | `heliosoftware/feed/heliofits.json`, `heliosoftware/feed.xml`, `heliosoftware/whats-new/index.html` | everything else; the Mac App Store is the release channel and no file is published here |
| HelioFITS Studio | `heliosoftware/feed/heliofits-studio.json`, `heliosoftware/feed.xml`, `heliosoftware/whats-new/index.html` | everything else; releases are GitHub assets on its own repository and the download page asks GitHub |
| sunback and My Heliogram | nothing | everything; they publish to S3, R2 and Fly, not to this repository |

Notes:

1. `<ver>` is the `version` in `build/version.json` of the Heliogram release being published.
2. `heliograph/index.html` is the redirect page written from `heliogram: site/heliograph-redirect.html`
   (suite SU-1). The rest of `heliograph/` is frozen: its feed and `version.json` serve 0.6 and 0.7
   installs, and its DMG URLs stay. See [the Heliogram publish contract](../../contracts/heliogram-publish.md).
3. The `heliosoftware/feed/*.json` records are written by `heliosoftware/feed/append_record.py`, and
   `heliosoftware/feed.xml` and `heliosoftware/whats-new/index.html` are regenerated from them by
   `heliosoftware/feed/build_feed.py` (suite SU-11, [release-feed.md](release-feed.md)). A product
   stages only those generated files and its own record.
4. Pages are owned here. `heliogram/index.html` and `heliogram/privacy.html` are edited in this
   repository. `heliogram: site/index.html` is a reference copy that stays in the app repository
   because `ship.sh` reads the release-notes block from it and writes that block into the signed
   `appcast.xml`; the download page shows the notes from that appcast. Write the notes once, there.
   Until heliogram SU-14 Task 2 lands, its `publish.sh` still copies `site/index.html` and
   `site/privacy.html` here; that copy is the one line this table retires.
5. The privacy page is a promise. Change its words here, on purpose, with a new effective date, and
   copy the new text back to `heliogram: site/privacy.html` so the app repository and the page agree.
6. DMG hosting. By default a DMG is a file in this repository (`DMG_HOST=pages`). During the alpha
   phase only, a DMG may instead be a release asset of a GitHub release on this repository,
   `GillySpace27/GillySpace27.github.io` (`DMG_HOST=github` in `heliogram: dmg-host.sh`, off by
   default, suite-decisions Q10). The appcast enclosure is signed at ship time, so `ship.sh` and
   `publish.sh` read the same switch. Either way no existing DMG URL is removed, no release asset is
   replaced (`--clobber` is never used) and no appcast item is deleted.
7. `heliogram: tools/test-publish-handshake.sh` reads the Heliogram row above and fails when
   `publish.sh` stages a path outside it or changes a page this repository owns. A product that starts
   publishing into this repository adds its row here first.
