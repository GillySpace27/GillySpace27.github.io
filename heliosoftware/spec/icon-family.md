# HelioSoftware icon family

Version 2, 2026-10-28. Describes the icons that ship; nothing here is redrawn.
Each icon stays where its product keeps it. Colour tokens for pages are in
[tokens.json](tokens.json), checked by [tools/tokens.py](tools/tokens.py).

The three app icons share one ground: a violet gradient from #2F2263 at the top to #15102A at
the bottom, lifted family-wide on 2026-10-28, with a white line drawing over real solar imagery
or a drawn Sun.

| Product | What the icon shows | Where it lives | On gilly.space |
|---|---|---|---|
| HelioFITS Peek | an AIA 171 image of the Sun inside a white file outline | `HelioFITS/Assets.xcassets/AppIcon.appiconset/` in HelioFITS-Peek | `assets/sw/heliofits.png` (nav, hub, page, Research), `heliofits/icon.png` (link preview) |
| HelioFITS Studio | an iris of six solar images in white lines, a drawn Sun at its centre, inset on the violet ground | `release/HFStudio_icon_1024.png` and `release/AppIcon.appiconset/` in HelioFITS-Studio | `assets/sw/heliofits-studio.png` |
| Heliogram | a drawn Sun on a white monitor outline | `icons/appicon.png` in heliogram, drawn by `icons/make_app_icon.py` | `assets/sw/heliogram.png` |
| RHEF, The Sun right now, My Heliogram | CSS marks, no app icon | `assets/product.css` (`.sw-mark--rhef`, `.sw-mark--live`, `.sw-mark--print`) | the same |

The gilly.space files are 160 px exports of the shipped 1024 px icons: Studio and Heliogram
cropped to their shape, Peek given the same corner shape, since its app icon ships full-bleed.
Re-export all three whenever one changes.

## Rules

- No Apple trademarks in a product name or icon (suite preamble).
- A new icon gets a row here before it ships on a page.
