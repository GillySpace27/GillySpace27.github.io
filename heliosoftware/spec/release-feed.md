# Release feed

One file per product under `heliosoftware/feed/`: `heliofits.json`, `heliofits-studio.json`,
`heliogram.json`, `sunback.json`. Each release script appends one record after its own gated
publish has succeeded. Records are append-only; nothing edits or removes one.

```json
{"product": "heliogram", "name": "Heliogram", "page": "https://gilly.space/heliogram/",
 "records": [
  {"version": "0.8", "build": 8, "date": "2026-10-02", "channel": "direct", "tag": "v0.8-build.8",
   "url": "https://gilly.space/heliogram/", "notes": "Short text.",
   "assets": [{"name": "Heliogram-0.8.dmg", "url": "https://gilly.space/heliogram/Heliogram-0.8.dmg",
               "sha256": "<64 lowercase hex>", "bytes": 12226044, "platform": "macos-universal", "confirmed": true}]}]}
```

The values above are illustrative, not a real release.

## Rules

- `channel`: `mac-app-store`, `github-prerelease`, `github-release`, `direct` or `pypi`. Every channel except
  `mac-app-store` needs at least one asset, and every asset needs a 64-hex `sha256` and a byte count.
- `confirmed` is true only after a person has run that build on real hardware. A page links an asset
  only when it is confirmed.
- A HelioFITS record is written only when App Store Connect reports READY_FOR_SALE. No HelioFITS
  version is claimed live before Apple says so. The date is the day the record was written (UTC).
- `url` is a release page or tag page. It is never `/releases/latest`.
- `notes` is one plain sentence or two, with no U+2014.
- The newest record is the one with the highest version number; a later record wins a tie.
- Sparkle's `appcast.xml` and `version.json` are separate files and are never read or written here.

## Tools

- Write: `python3 heliosoftware/feed/append_record.py --product ... --version ... --date ... --channel ...
  --url ... --notes-file ... [--asset name=...,url=...,sha256=...,bytes=...,platform=...,confirmed=...]`.
  Exit 0 appended, 1 invalid, 3 duplicate (version, build).
- Render: `python3 heliosoftware/feed/build_feed.py` writes `heliosoftware/feed.xml` and
  `heliosoftware/whats-new/index.html`; `--check` exits 1 when either would change.
- Read in pages: `assets/product.js` fills elements marked `data-release="<product>"`; static text in the
  page is the fallback, and `python3 tools/check_site.py --feed` fails when it is older than the feed.
