# HelioSoftware icon family

Version 1, 2026-10-15 (suite SU-20). Describes the icons that exist; nothing here is redrawn.
Each icon stays where its product keeps it. Colour tokens for pages are in
[tokens.json](tokens.json), checked by [tools/tokens.py](tools/tokens.py).

| Product | What the icon shows | Where it lives | Source for the description |
|---|---|---|---|
| HelioFITS Peek | an AIA 171 image of the Sun | the HelioFITS repository's app icon; on gilly.space the CSS mark `.sw-mark--fits` | suite preamble, "Settled names": "it keeps the AIA 171 icon" |
| HelioFITS Studio | the Studio app icon | `release/AppIcon.appiconset/` in HelioFITS-Studio; on gilly.space `assets/sw/heliofits-studio.png` | see "Open question" below |
| Heliogram | the photographic Sun, with a large white glyph naming the product | `icons/make_app_icon.py` in heliogram draws it; on gilly.space `assets/sw/heliogram.png` | heliogram `icons/README.md` ("Heliogram products wear the photographic Sun") |
| RHEF, The Sun right now, My Heliogram | CSS marks, no app icon | `assets/product.css` (`.sw-mark--rhef`, `.sw-mark--live`, `.sw-mark--print`) | this site |

## Open question for Gilly

Two sources describe the Studio icon differently, and this page does not pick one:

- the SU-20 register entry says "Studio icon is the iris";
- heliogram `icons/README.md` says HelioFITS products wear "the hexagon-wedge HF mark" with a
  white badge disc, and that "Studio's badge is stacked layers".

The same README puts the HelioFITS Peek icon in the HF-mark family, while the suite preamble says
HelioFITS "keeps the AIA 171 icon". Until Gilly settles both, the files above are the reference.

## Rules

- No Apple trademarks in a product name or icon (suite preamble).
- A new icon gets a row here before it ships on a page.
