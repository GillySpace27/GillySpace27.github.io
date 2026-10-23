# Processing record of exported images, movies and data

Format 1.0. The detailed record of how an export was made: every file each layer read, named by
SHA-256, every step applied to it in order with its parameters, and the producer's own scene so
the export can be rebuilt. It is the companion of the [provenance stamp](provenance.md), not a
replacement: the stamp says in a few fields which product, instrument and moment, and whether RHEF
was applied; the record says everything else. Every export writes both.

This page is the format. The schema is [hfrecord-1.schema.json](hfrecord-1.schema.json) (JSON Schema,
draft 2020-12), and [examples/example-studio-connect-still.hfrec.json](examples/example-studio-connect-still.hfrec.json)
is one worked record that validates against it. Where this page and the schema differ, the schema wins.

## Versioning

`"hfrecord": "1.0"` is the format version, MAJOR.MINOR, and `reader_compat` is an integer: the oldest
reader version that reads the record correctly. It is the same rule as `reader_compat` in Heliad's
library index.

- Within a major version, keys are only added, never renamed or removed. A minor bump adds optional keys.
- A reader ignores keys it does not know and shows an `op` it does not know verbatim.
- A major bump is for a change of meaning. A reader refuses a record whose `reader_compat` is above its own.
- The format 1 schema accepts `hfrecord` values matching `1.<minor>` only, so a record that claims `2.0`
  fails validation against it.

Products keep a byte-for-byte copy of the schema. [SHA256SUMS](SHA256SUMS) lists the canonical hash.

## Two parts: normalized and native

Each record carries:

- **A normalized part**: `layers[].sources`, `layers[].steps`, `scene` and `output`. One ordered
  vocabulary for every producer, with parameter names as the producer writes them. This is what Heliad
  displays, what an agent compares, and what a reader can understand without the producer's code.
- **A native part**: `native.studio_session` or `native.python_session`, plus `layers[].native`. The
  producer's own scene, verbatim, with home written as `~`. This is what a rebuild loads. When the same
  file already carries the scene, `native_ref` names where (`png:tEXt:hfstudio`, `exr:attr:hfstudio` or
  `mp4:comment`) instead of writing it twice.

Keeping both lets the normalized vocabulary stay small and readable while a rebuild never depends on it
being complete. `summary` is a generated plain-text account (program, time, one line per layer, citations)
that readers show first; `provenance` repeats the provenance stamp's object so one file holds both.

## Sources: identity by SHA-256, no local paths

A source is named by the SHA-256 of the file. Readers resolve a source by its hash (Heliad joins it
against its library's `files.sha256`), never by a path. The normalized part never holds a path on the
person's computer, a user name or a machine id: `source_url` is an archive address only, and is `null`
when the file was not downloaded. Each source can also carry `heliad_obs_key`, `file_version`,
`original_name`, `size`, `date_obs` and `in_library`.

- `source_spec` keeps the re-runnable query (`FitsRequest.toJson()` or `APIRequest.toJson()` verbatim),
  so a missing source can be fetched again.
- Helioviewer (JPIP or API) layers have no file and so no hash. They record the request in
  `source_spec.request` and per frame the `helioviewer` object (server, sourceId, image id). Such a layer
  cannot promise the same pixels later, and the record says so.
- `source_set_sha256` is the SHA-256 of the layer's source hashes, sorted and joined by newline. It lets a
  shortened embedded copy (with `source_count` in place of `sources`) be matched to its full sidecar.
- Movies and series add `frame_map`: the output frame times and, per layer, an index into its sources
  for each frame (`null` when the layer showed nothing).

## Where each format keeps it

The sidecar is canonical and always complete. The embedded copy is there so a file that travels alone
still says what it is.

### Sidecar

A JSON file (UTF-8, indented) beside every export: the export's file name followed by `.hfrec.json`, for
example `connect_20250921T2032_aia-aspiics-punch.png.hfrec.json`. Name the file only, never a directory.
The sidecar carries `output.file_name` and `output.sha256`, the hash of the export file.

The Send to Python data export writes one `hfrecord.json` beside its `manifest.json` (which stays as it
is), with `output.kind` `fits_data`, `display_referred` false and the layer's sources by SHA-256.

### PNG

A text chunk (`tEXt`) with keyword `hfrecord`, holding the record as ASCII-escaped JSON. It sits beside
the provenance chunks and Studio's existing `hfstudio` chunk, which stays unchanged; the record then sets
`native_ref` to `png:tEXt:hfstudio` instead of repeating the scene. `output.sha256` is `null` in an
embedded copy.

### EXR

A string header attribute `hfrecord`, by the same rule as PNG (`native_ref` `exr:attr:hfstudio`).

### MP4 and MOV (ffmpeg)

A shortened record (each layer's `sources` replaced by `source_count` and `source_set_sha256`, no
`frame_map`) in its own metadata tag, `hfrecord`. The mp4 muxer writes only a fixed set of tags, so the
custom tag needs `-movflags use_metadata_tags`; some players then show no metadata at all. `comment` and
`description` keep the meaning [provenance.md](provenance.md) gives them.

```text
ffmpeg ... -metadata comment="$STAMP" -metadata description="$CREDIT" \
  -metadata hfrecord="$HFRECORD" -movflags use_metadata_tags out.mp4
```

The size limit of a tag is not verified; the full record always lives in the sidecar.

### FITS

An extra HDU named `HFRECORD` holding the record JSON, plus one `HISTORY` card per step in a fixed form,
for example `HFREC 1.0 step 3 clip Percentile05 ...`, and cards for the `record_id` and the source
`sha256`. The provenance cards and the source file's own `HISTORY` stay as they are. A card that runs
past 72 characters continues by the [provenance.md](provenance.md) FITS rule; keep step cards short and
leave the full values to the sidecar.

The Send to Python export lists only the decode steps it applies (physical scaling, instrument
corrections). Display steps (colour table, filter, clip, RHEF) are not applied by that export, so the
record lists none of them rather than listing them as done.

### Embedded copies get stripped

Preview, Photoshop and most web pipelines drop `tEXt` chunks and other metadata when they save a
file. An embedded copy describes the file as it was written, not as it is now,
and is never a guarantee. Only a sidecar's `output.sha256`, compared with the hash of the file in hand,
ties the pixels to the record.

## Steps

`layers[].steps` is the ordered list of operations from the decoded file to the layer's contribution
to the frame, user-set and automatic alike (`automatic: true`, for example LASCO `EXPTIME` division).
`resolved` holds values derived from the data at export time, such as the clip bounds a percentile mode
actually used. `varies` marks a parameter that changed during a movie and points into the native
automation tracks; `params` then holds the value at the first frame. `reference` names the frame a
`difference` step subtracted. Layers are in drawing order: index 0 is drawn first, at the bottom.

HelioFITS Studio's steps, in the order Studio runs them, with the `imageParams` keys each one carries:

| # | `op` | `stage` | Studio keys |
|---|---|---|---|
| 1 | `instrument_correction` (automatic) | decode | LASCO: `OFFSET` subtracted, `EXPTIME` division, NRL monthly background |
| 2 | `pointing` (automatic) | decode | `lascoPointing`, `lascoPointingComplete` |
| 3 | `select_plane` | decode | `plane`, `planes` |
| 4 | `clip` | decode | `clippingMode` (`Percentile001`, `Percentile05`, `Range`), `clippingMin`, `clippingMax`; `resolved.low`, `resolved.high` are the bounds used |
| 5 | `stretch` | decode | `scalingMode` (`Gamma`, `Beta`, `Alpha`), `gamma`, `beta`, `alpha` |
| 6 | `image_filter` | cpu | `filter` (`None`, `MGN`, `WOW`, `RHEF`); RHEF adds the stamp line and the caveat |
| 7 | `sequence_filter` | cpu | `sequence`: `type`, `kind`, `mode`, `lo`, `hi`, `direction`, `gain`, `nR`, `nPhi` |
| 8 | `levels`, `radial_gain` | gpu | `brightOffset`, `brightScale`, `enhanced` |
| 9 | `difference` | gpu | `differenceMode` (`None`, `Running`, `Base`) |
| 10 | `sharpen` | gpu | `sharpen` |
| 11 | `rhef_upsilon` | gpu | `upsilonLow`, `upsilonHigh` |
| 12 | `colormap` | gpu | `lut`, `invert` |
| 13 | `channel_mask` | gpu | `color.red`, `color.green`, `color.blue` |
| 14 | `geometric_mask` | gpu | `innerMask`, `outerMask`, `slitLeft`, `slitRight`, `sectorCenter`, `sectorWidth` |
| 15 | `opacity_blend` | gpu | `opacity`, `blend` |

Steps 8 to 12 follow the order of Studio's shader. The order of steps 3 to 7 is read from the code
structure and is not yet checked against the decoder. Scene-wide settings (projection, viewpoint,
camera width) go in `scene`, not in a layer's steps. RHEF output is a visualization, not a calibrated
radiance.

## Rebuilding

A rebuild loads `native`, resolves the sources by hash and exports again. Expect the same scene, not
identical bytes: GPU and driver differences, dithering and Helioviewer re-serving reprocessed JP2 images
all move pixels, so a comparison is a tolerance, not an equality. A record from a `dirty` build or with a
Helioviewer layer is not guaranteed to rebuild.

## Field reference

Generated from [hfrecord-1.schema.json](hfrecord-1.schema.json). Required means required by the schema;
every other field is optional.

### Top level

| Field | Type | Required | Meaning |
|---|---|---|---|
| `hfrecord` | string (pattern `^1\.[0-9]+$`) | yes | Format version, MAJOR.MINOR. A minor bump adds optional keys only. A major bump changes meaning; a reader refuses a record whose reader_compat is above its own. |
| `reader_compat` | integer (minimum 1) | yes | The oldest reader version that can read this record correctly. Same rule as Heliad's index reader_compat. |
| `record_id` | string (uuid) | yes |  |
| `created` | string (date-time) | yes | UTC, seconds precision. |
| `producer` | object | yes |  |
| `output` | object | yes |  |
| `scene` | object | no | Scene-wide geometry and timing, shared by every layer. Producer vocabulary kept as written; see the design note for the mapping. |
| `layers` | array of [layer](#layer) | yes | Image layers in drawing order: index 0 is drawn first (bottom). |
| `frame_map` | object | no | Movies and series only: which source each layer showed in each output frame. Columnar to stay small. |
| `caveats` | array of string | no |  |
| `citations` | array of string | no |  |
| `native_ref` | string | no | Set instead of native when the same file already carries the producer's scene: 'png:tEXt:hfstudio', 'exr:attr:hfstudio' or 'mp4:comment'. Avoids writing the scene twice. |
| `native` | object | no | The producer's own scene, verbatim and portable (home written as ~). This is what a rebuild loads; the normalized fields above are for people, agents and Heliad. |
| `summary` | string | no | Generated plain text for people: program, time, one line per layer (dataset, frame count, filter, colour table, caveat), citations. Readers show it first. |
| `provenance` | object | no | The suite provenance object (provenance.md fields: product, version, instrument, observed, credit, rhef, citation), repeated so one file holds both. |
| `heliad_view` | object or null | no | The Heliad view or event the sources came from, when there was one. |
| `snapshot` | object | no | When the scene was read. |

### `producer`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `producer.program` | string | yes | Examples: `HelioFITS Studio`, `punch-composite-studio`. |
| `producer.version` | string | yes |  |
| `producer.build_id` | string | no |  |
| `producer.commit` | string | no |  |
| `producer.dirty` | boolean | no | True when the build had uncommitted changes; such a record cannot promise a rebuild. |
| `producer.stamp` | string | no | Studio's AppInfo.stamp() line, verbatim. |

### `output`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `output.kind` | one of `still`, `movie`, `frame_series`, `exr_series`, `fits_data` | yes |  |
| `output.media_type` | string | yes | Examples: `image/png`, `video/mp4`, `image/x-exr`, `application/fits`. |
| `output.file_name` | string | no | Base name of the export as written. Sidecars only. |
| `output.sha256` | string or null (pattern `^[0-9a-f]{64}$`) | no | Of the export file. Present in a sidecar, null when the record is embedded in the file it describes. |
| `output.width` | integer | no |  |
| `output.height` | integer | no |  |
| `output.frames` | integer | no |  |
| `output.fps` | number | no |  |
| `output.codec` | string | no |  |
| `output.bit_depth` | integer | no |  |
| `output.colorspace` | string | no |  |
| `output.display_referred` | boolean | no | True when pixel values are rendered colours, not measured quantities. |

### `scene`

Scene-wide geometry and timing, shared by every layer. Producer vocabulary kept as written; see the design note for the mapping.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `scene.time` | string (date-time) | no |  |
| `scene.time_range` | array of string | no |  |
| `scene.cadence` | any | no |  |
| `scene.projection` | string | no |  |
| `scene.viewpoint` | object | no |  |
| `scene.camera_width` | any | no |  |
| `scene.radial_transform` | object | no |  |
| `scene.overlays` | array of string | no |  |
| `scene.compare` | object or null | no | Studio's Compare (HS-11) state when on: which layers, divider, palette. |

### `frame_map`

Movies and series only: which source each layer showed in each output frame. Columnar to stay small.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `frame_map.times` | array of string | no |  |
| `frame_map.by_layer` | object | no | layer id -> per output frame, an index into that layer's sources, or null when the layer showed nothing. |

### `native`

The producer's own scene, verbatim and portable (home written as ~). This is what a rebuild loads; the normalized fields above are for people, agents and Heliad.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `native.studio_session` | object | no | Provenance.session() 'scene': the .jhv JSON. |
| `native.python_session` | object | no | The .studio session file's JSON plus the render params dict. |

### `heliad_view`

The Heliad view or event the sources came from, when there was one.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `heliad_view.view_uid` | string | no |  |
| `heliad_view.name` | string | no |  |

### `snapshot`

When the scene was read.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `snapshot.taken` | one of `export_start` | no |  |
| `snapshot.changed_during_export` | boolean | no |  |

### layer

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Studio AbstractLayer id, or the Python layer name. |
| `name` | string | yes |  |
| `enabled` | boolean | no |  |
| `dataset` | object | no | Heliad's dataset identity when the layer's files are in the library. |
| `source_spec` | object | no | How the layer asked for data: re-runnable when the sources themselves are missing. |
| `sources` | array of [source](#source) | yes | Every file the layer read, in time order. sha256 is the identity; Heliad resolves it through files.sha256. |
| `source_count` | integer | no | Set when sources was shortened to fit an embedded container. |
| `source_set_sha256` | string (pattern `^[0-9a-f]{64}$`) | no | SHA-256 of the layer's source sha256 values, sorted, joined by newline. Lets a shortened record still be matched to a full one. |
| `steps` | array of [step](#step) | yes | Ordered operations from decoded file to the layer's contribution to the frame, user-set and automatic alike. |
| `native` | object | no | This layer's entry from the producer's scene, verbatim. |
| `acknowledgement` | string or null | no | The instrument team's required acknowledgement line for this dataset, when known. |

### `dataset`

Heliad's dataset identity when the layer's files are in the library.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset.dataset_key` | string | no | Examples: `sdo/aia/-/-/1/193`. |
| `dataset.label` | string | no |  |
| `dataset.observatory` | string or null | no |  |
| `dataset.instrument` | string or null | no |  |
| `dataset.detector` | string or null | no |  |
| `dataset.product` | string or null | no |  |
| `dataset.level` | string or null | no |  |
| `dataset.wavelength` | number or null | no |  |
| `dataset.dataset_uid` | string | no | Heliad's permanent dataset id (survives reindex); absent for files outside the library. |

### `source_spec`

How the layer asked for data: re-runnable when the sources themselves are missing.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source_spec.kind` | one of `heliad_library`, `fits_request`, `helioviewer_api`, `uri_list`, `local_files` | yes |  |
| `source_spec.request` | object | no | FitsRequest.toJson() or APIRequest.toJson() verbatim. |

### source

| Field | Type | Required | Meaning |
|---|---|---|---|
| `sha256` | string (pattern `^[0-9a-f]{64}$`) | no |  |
| `date_obs` | string | no |  |
| `heliad_obs_key` | string | no |  |
| `file_version` | string or null | no |  |
| `original_name` | string | no |  |
| `size` | integer | no |  |
| `source_url` | string or null | no | Archive address, never a local path. |
| `helioviewer` | object | no | For JPIP or API layers: server, sourceId, image id. No file hash exists for these. |
| `in_library` | boolean | no | Whether the writer found this hash in its Heliad library. |

### step

| Field | Type | Required | Meaning |
|---|---|---|---|
| `op` | one of `instrument_correction`, `select_plane`, `clip`, `stretch`, `image_filter`, `sequence_filter`, `levels`, `radial_gain`, `difference`, `sharpen`, `rhef_upsilon`, `colormap`, `channel_mask`, `geometric_mask`, `pointing`, `opacity_blend`, `radial_transform`, `reproject`, `feather` | yes | Shared vocabulary. Unknown ops are shown verbatim by readers. |
| `stage` | one of `decode`, `cpu`, `gpu`, `render` | no | Where it runs, so a reader knows which steps share a buffer. |
| `algorithm` | string | no | Examples: `RHEF`, `MGN`, `WOW`, `Gamma`. |
| `implementation` | string | no | Examples: `hfstudio-java`, `hfstudio-glsl`, `sunkit-image`. |
| `automatic` | boolean | no | True when the program applied it without a user setting (for example LASCO EXPTIME division). |
| `params` | object | yes | Parameter names as the producer writes them (Studio: imageParams keys). |
| `resolved` | object | no | Values the step derived from the data at export time, e.g. the percentile clip bounds actually used. |
| `units` | object | no |  |
| `citation` | string | no |  |
| `caveat` | string | no |  |
| `stamp` | string | no | An algorithm's own provenance line, e.g. RHEFStamp.line(). |
| `varies` | object or null | no | Set when a parameter changed during a movie: names the parameters and points into native automation tracks. params then holds the value at the first frame. |
| `reference` | object or null | no | For difference steps: the frame subtracted. kind running = previous frame, base = a fixed source index. |

### `varies`

Set when a parameter changed during a movie: names the parameters and points into native automation tracks. params then holds the value at the first frame.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `varies.params` | array of string | no |  |
| `varies.automation` | array of string | no | Automation track ids in the native scene. |
| `varies.changed_by_user` | boolean | no |  |

### `reference`

For difference steps: the frame subtracted. kind running = previous frame, base = a fixed source index.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `reference.kind` | one of `running`, `base`, `compare` | no |  |
| `reference.source_index` | integer or null | no |  |
| `reference.layer_id` | string or null | no |  |


## Worked example

[examples/example-studio-connect-still.hfrec.json](examples/example-studio-connect-still.hfrec.json) is a
Studio still at 2025-09-21T20:32 UTC from the CONNECT event: PUNCH WFI+NFI CAM L3 at the bottom with RHEF,
Proba-3 ASPIICS 5508 Å L3 in the middle, SDO AIA 193 Å L1 on top. The sources' hashes, sizes, keys and
names were read from a Heliad library; the step keys, enum values and colour table names are Studio's.
It is not from a real export: the layer settings are Studio's defaults, the producer version, commit,
projection and layer ids are placeholders, the clip bounds are left `null`, and the native scene is
abbreviated. It shows the shape; it is not a record of a real export.

## Status

Format 1.0 is the format and the schema. No product writes it yet; HelioFITS Studio's writer and
Heliad's reader adopt it in their own changes. Adding to it is additive: nothing here is removed or
renamed once a product reads it.
