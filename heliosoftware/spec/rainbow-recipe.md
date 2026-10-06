# Rainbow recipe

The "rainbow Sun": one RGB picture built from three AIA channels, each equalised with RHEF and used as one
colour channel. This page records what the two implementations do, as read from their code on 2026-10-05.
It is a description for people who want the two to agree, not a specification of the science. RHEF output is a
visualization, not a calibrated radiance.

| Step | sunback `RainbowRGBImageProcessor` (rgb1) | My Heliograph store |
|---|---|---|
| Channels | 171, 193 and 211 as red, green, blue (`rgb1 = ("0171", "0193", "0211")`, `CompositeRainbowImageProcessor.py:33`) | `RAINBOW_RGB = [171, 193, 211]` (`web3d/src/data/wavelengths.ts:50`) |
| Input to each channel | the RHEF frame, default `rhef(lev1p5)` (`:130`), as an array | the greyscale RHEF product of each channel (`preview_gray_url`, `useRainbowLoader.ts:13-18,33`), not the colour-mapped picture |
| Window | none: float input is multiplied by 255 and cast, with no clipping (`:202-212`, with `to_int8` at `:212`) | the percentile window of the colour version, 1st to 99.7th percentile of the RHEF array (`api/main.py:1830-1831`), then clipped to 0 to 1 (`:1858`) |
| 8-bit conversion | `(image * 255).astype(np.uint8)` (`:212`) | `(_g * 255).astype(np.uint8)` (`api/main.py:1863`) |
| Row order | each channel flipped with `np.flipud` before stacking (`:146-148`) | flipped with `np.flipud` after replacing NaN with 0 (`api/main.py:1860`) |
| Stack | `np.stack((R, G, B), axis=-1)` (`:224`); output file names say `BGR_` (`:175`) but the array order is R, G, B | three textures mapped to the three colour channels in the web3d viewer |
| Extras | `label_plot` annotations on each channel before stacking (`:162-164`) | none on the channels |

Where they differ today: the window (none against a percentile clip) and the NaN handling. This page does not say
which is right. Decide in the product that owns the picture, and change this table when it does.

Colour tables are not part of the recipe: the channels are un-colour-mapped on purpose. The store's comment
(`useRainbowLoader.ts:13-18`) records that compositing the colour-mapped pictures by luminance came out pastel.
For the per-channel colour tables themselves see [colormaps/](colormaps/README.md) and `tools/diff_luts.py`.
