# Versioning and release identity

One declared version source per product, one tag convention, one changelog convention
(decision B11b, Gilly, 2026-10-02: SemVer plus a separate build number). This page names
sources that already exist; it renames none, moves no tag and edits no changelog. Facts were
read from each repository's default branch on 2026-10-05.

## One declared source per product

| Product | Declared version source | Build number | Tag | Long changelog | Short "What's new" |
|---|---|---|---|---|---|
| HelioFITS | `Config/Version.xcconfig`, `MARKETING_VERSION` (HF-10); set only with `scripts/bump-version.sh <VER> <BUILD>` | `CURRENT_PROJECT_VERSION` in the same file | `v<version>-build.<n>`, annotated, made by hand at RELEASING.md step 5 (existing: `v1.3.2-build.9`, `v1.4.0-build.10`) | `CHANGELOG.md`: `## [Unreleased]` on top, then `## [x.y.z] - YYYY-MM-DD` | The App Store What's New box: one headline sentence per fix |
| HelioFITS Studio | `VERSION` at the repository root, all whitespace removed (`release/deploy_release.sh:50`) | none | `v<VERSION>` (`deploy_release.sh:57`); one new tag and one new release per build | `changelog.md` (lowercase): `## HelioFITS Studio <version> (...)`; the newest heading may read `(unreleased)` | The changelog section whose heading contains ` <VERSION> `, which `deploy_release.sh:133` lifts into the release page |
| Heliogram | `release.env`, `VERSION` (HG-5); set only with `./bump.sh <version>` | `BUILD` in `release.env` | `v<version>-build.<n>`, made locally by `ship.sh` at the built commit (HG-8) | `CHANGELOG.md` (`## <version> (build <n>), published YYYY-MM-DD`) | The notes block of `site/index.html`, which `ship.sh` writes into the signed appcast |
| sunback | `pyproject.toml`, `version` (SB-12; `setup.py` is a shim) | none | the bare version, never a `v` prefix (existing: `0.6.17.1`, `0.6.17.2`, `0.6.17.3`) | none yet | none yet |
| My Heliograph (store) | planned: the build stamp `YYYY.MM.DD-<sha7>` (UTC date, 7-character git sha) in `.deploy-run.json` (`build_stamp`) and `GET /api/build-info`; not built yet (SU-15 Task 2) | none | none from this page | none yet | none |
| Website | none: a push to `master` publishes | none | none | none | the release feed (`release-feed.md`) |

## Rules

1. New tags are `v<version>`, with `-build.<n>` where the product has a build number (HelioFITS,
   Heliogram). sunback keeps bare tags. Existing tags are never moved, renamed or removed, and a tag is
   never reused: a corrected build gets a new build number and a new tag.
2. Version and build are identical across a product's channels (for HelioFITS, the Mac App Store build
   and the Developer ID zip).
3. The changelog has two tiers. The long form lives in the repository file named above, with an
   Unreleased section on top. The short "What's new" block is one headline sentence per fix; the same
   words feed the store listing, the Sparkle appcast and the release feed. No U+2014 in either.
4. The release check reads the declared source: the shared `release-gates.sh` (canonical in HelioFITS)
   refuses in its `versions` gate when a value it is given differs from the version being released
   (override: `ALLOW_VERSION_MISMATCH=yes-gilly`). Reading the declared source itself
   (`release-gates.sh --declared <product>`) is SU-15 Task 3.
5. Do not rename `changelog.md` (Studio's release script and its Help menu link read it by name) or
   `VERSION`.

## Open question

HelioFITS ships as a universal purchase that shares the bundle id `com.gillyspace27.HelioFITS`
(decision B1: universal purchase, shared version numbers). Whether the Mac and iOS apps share one build
sequence in App Store Connect is not verified, so no build-number rule is written for it
(suite-decisions Q16). Until it is answered, `CURRENT_PROJECT_VERSION` and the `-build.<n>` tag
describe the Mac app.
