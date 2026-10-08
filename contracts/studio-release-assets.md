# Contract: HelioFITS Studio release assets (GitHub releases to gilly.space)

Drafted 2026-10-01 for WS-4 from `heliofits-studio/index.html` (fallback links
at `:38-82`, `PLATFORMS` at `:100-106`, the runtime fetch at `:149-164`).
Producer: `GillySpace27/HelioFITS-Studio` GitHub releases, made by
`release/deploy_release.sh` (`:56-58`) and `.github/workflows/package.yml`
(`:308`, Windows and Linux), read at HelioFITS-Studio@7671c40.
Consumers: `heliofits-studio/index.html` and `tools/pin_studio_fallback.py`
(WS-8). `tools/check_site.py` rule `contract` reads the fenced block.

## Asset names

One template per line; `{v}` is the version without the leading `v`, and the
release tag is `v{v}`. `HFStudio` stays the technical name on every asset.
Append-only: a new platform adds a line; no line is renamed or removed.

```assets
HFStudio-{v}.dmg
HFStudio-{v}-intel.dmg
HFStudio-{v}-windows.zip
HFStudio-{v}-linux.tar.gz
HFStudio-{v}.zip
HFStudio-Guide.pdf
```

A release may ship without an asset listed here (2026-10-07: v0.8.5 has no
Intel dmg). Its fallback link then stays on the newest release that has it.

```optional-assets
HFStudio-{v}-intel.dmg
```

| Template | Page element | Fallback line | Matched at runtime by |
|---|---|---|---|
| `HFStudio-{v}.dmg` | `#mac` | `:38` | `PLATFORMS.mac` `/^HFStudio-[\d.]+\.dmg$/` |
| `HFStudio-{v}-intel.dmg` | `#try-intel` | `:69` | `PLATFORMS.intel` |
| `HFStudio-{v}-windows.zip` | `#try-windows` | `:70` | `PLATFORMS.windows` |
| `HFStudio-{v}-linux.tar.gz` | `#try-linux` | `:73` | `PLATFORMS.linux` |
| `HFStudio-{v}.zip` | `#zip` | `:77` | `/^HFStudio-[\d.]+\.zip$/` (`:156`) |
| `HFStudio-Guide.pdf` | `#guide` | `:56` | `/Guide\.pdf$/` (`:156`) |

## Rules

- Hand out the `/releases` index, never `/releases/latest`; the page asks for
  `releases?per_page=1` because every release so far is a pre-release (`:147-149`).
- Every platform tile is a live download (2026-10-08: a disabled Windows tile
  read as "not available"). `confirmed: true`, set by a human after running that
  build on real hardware, only drops the "early build" wording; nothing here or
  in WS-8 sets it.
- Checks: every template, with `{v}` set to the version pinned on the page,
  appears as a fallback link `/releases/download/v{v}/<name>`; every
  `PLATFORMS` pattern matches exactly one of those names.
