# RHEF conventions

Version 1. Written 2026-10-01 for test-vector bundle 1.0.0. RHEF output is a visualization, not a calibrated radiance.

RHEF, the Radial Histogram Equalizing Filter (Gilly and Cranmer 2025, Solar Physics), has been implemented several times. This page states what each implementation computes, step by step, so two of them can be compared number by number. It describes code and test data and adds no claim about the method. The test vectors are in `golden/` and `vectors.json` beside this file.

## 1. Two steps

RHEF is two separable steps. An implementation may do one or both.

- Geometry. From an image and its coordinates, give every pixel a radius in solar radii and a radial bin. Bin i holds the pixels with lower[i] <= r < upper[i]. A pixel in no bin has `bin_index` -1 in the vectors; what an implementation writes there is not part of a convention.
- Kernel. Within each bin, replace each value by its rank among the bin's values, scaled into (0, 1], then apply the Upsilon curve.

## 2. Conventions

A convention is a complete answer to every row of the table. `sunkit-0.7` is the default behavior of sunkit-image 0.7.0 `rhef`; the expected outputs named `expected_sunkit-0.7` in the vectors were produced by that release. `oRHEF-2.0` names the convention of the RHEF 2.0 reference implementation. It is defined on this page when that work is published; until then an implementation that declares it is declaring a target, and the vectors that carry its expectations are not public.

| Question | `sunkit-0.7` |
|---|---|
| Bin edges | `find_radial_bin_edges` of sunkit-image. Edges whose outer edge falls short of the largest radius are rebuilt with half the bin count (BIN-HALF). |
| Ranked pixels | Pixels in a bin, at or beyond `application_radius`, that are not NaN. |
| Rank | The average rank of equal values (`scipy.stats.rankdata`, method `average`) divided by n, n the number of values in the bin. |
| Ties | Equal values share their average rank. `method="numpy"` instead breaks ties in array order (TIES-ORD). |
| Upsilon split | The mean rank of the bin (UPS-MEAN). |
| Upsilon default | 0.35 for both halves; a (low, high) pair is accepted. |
| NaN | Becomes 0.0 under Upsilon (NAN-ZERO). |
| Output type | Follows the input type (DTYPE-IN). |

Status: the tie rule "average" is proposed, not yet confirmed by the author; the conformance runners report differences and do not fail on them until it is confirmed.

## 3. The Upsilon curve

For a rank p in (0, 1], a split s and exponents a (below the split) and b (at or above it):

- p < s: `(2p)^a / 2`
- p >= s: `1 - (2 - 2p)^b / 2`

In `sunkit-0.7` the split s is the mean of the ranks in the bin. With a = b = 1 the curve is the identity. `upsilon=none` skips this step and returns the ranks.

## 4. Deviation ids

A registered implementation names the convention it targets and lists, in a fixed order, how its code still differs from it. An id is never renamed once used; new ids are appended. A different filter that shares the name carries exactly `NOT-RHEF`.

| Id | Meaning |
|---|---|
| `RANK-N1` | rank normalized `(r - 1) / (n - 1)`, range [0, 1] |
| `TIES-ORD` | ordinal ties in enumeration order |
| `TIES-TOL` | ties merged within a tolerance |
| `TIES-INTERP` | ties undefined: interpolation over repeated values |
| `KEY-QUANT` | sort key drops the two lowest float32 bits |
| `UPS-MEAN` | Upsilon split at the bin's mean rank |
| `UPS-EXT` | the kernel returns pre-Upsilon ranks; Upsilon is applied elsewhere |
| `RANK-EXT` | applies only Upsilon, to ranks computed elsewhere |
| `UPS-CLAMP` | Upsilon on the value clamped to [0, 1], excess added back |
| `UPS-DEFAULT` | default Upsilon differs from 0.35 symmetric |
| `POS-ONLY` | only strictly positive pixels are ranked |
| `FP16` | input quantized to half precision |
| `MIN-BIN` | bins under a minimum count pass through unranked |
| `NAN-ZERO` | NaN becomes 0.0 |
| `BIN-HALF` | a short hand-supplied edge list is rebuilt with half the bins |
| `GEOM-PX` | about 1-pixel-wide annuli in pixel units |
| `GEOM-GRID` | equal-width bins to the largest radius on a decimated grid, nbins = grid height / 2 |
| `GEOM-CRPIX` | radius in pixels from CRPIX |
| `EDGES-ARITH` | bin index by arithmetic on the first edge and one width |
| `NO-NAN-GUARD` | no NaN handling; a one-pixel bin divides by zero |
| `DTYPE-IN` | output precision follows the input |
| `DENOISE-POST` | smoothing after ranking |
| `API-SUBSET` | a subset of the reference implementation's parameters |
| `NOT-RHEF` | a different filter |

## 5. Stamp line

One line names the convention, the implementation and the settings of an RHEF image:

```text
RHEF <convention> via <implementation> <version>; upsilon=<lo>,<hi>; deviations=<ID>,<ID>
```

`upsilon=none` when Upsilon is off; a single value u is written `u,u`; `deviations=none` when the list is empty; `<version>` is `unknown` when unreadable. Example: `RHEF sunkit-0.7 via sunkit 0.7.0; upsilon=0.35,0.35; deviations=none`. A validation pattern: `^RHEF (\S+) via (\S+) (\S+); upsilon=(none|[0-9.eE+-]+,[0-9.eE+-]+); deviations=(none|[A-Z0-9-]+(?:,[A-Z0-9-]+)*)(; ref=doi:\S+)?$`. Carriers: a PNG `tEXt` chunk with keyword `RHEF`; one FITS `HISTORY` card; the ffmpeg `comment` metadata of a movie. Photometric exports carry no stamp.

## 6. Test vectors

`vectors.json` is the manifest of the full vector bundle: every file with its sha256. `golden/` holds the public cases. Each case folder has `input.f64`, `input.f32`, `radii.f64`, `radii.f32`, `edges.f64` (2 x nbins: row 0 the lower edges, row 1 the upper edges), `bin_index.i32` (-1 = in no bin), `expected_sunkit-0.7.f64` and `.f32`, `case.properties` and `header.json`. Arrays are raw little-endian, C order, no header. `case.properties` gives the shape (`ny,nx`), the Upsilon pair, `tol_f64` and `tol_f32`. `golden/read_golden.py` reads a case with the standard library. `golden/SOURCE.txt` names the bundle and lists what is withheld. The case `geometry_hpc_32` is different: it holds `header.json` (a solar WCS header) and `expected_radii.f64` (the radius in solar radii of every pixel of a 32 x 32 grid whose reference pixel is off centre), for checking the geometry step alone. Files listed in `vectors.json` but absent from `golden/` are not published.

To check an implementation: rank each bin of `input.f64` as `bin_index.i32` says, apply the Upsilon pair, and compare with `expected_sunkit-0.7.f64` over the pixels whose `bin_index` is not -1. A pixel whose rank equals the bin mean to within rounding sits exactly on the split; compare it separately, because the result there depends on how the library rounds its mean.

## 7. Conformance status

Runner results, by case and implementation. Report mode never fails a build; enforce mode does.

<!-- conformance-table begin -->
No results recorded yet.
<!-- conformance-table end -->
