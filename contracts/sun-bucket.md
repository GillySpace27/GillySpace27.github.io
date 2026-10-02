# Contract: the Sun bucket (Sunback to gilly.space)

Drafted 2026-10-01 for WS-4 from `sun.html` and from Sunback
`aws_lambda/video_builder/manifest.py` (sunback@a429bc1). Producer: Sunback
(the reducer writes `1k/` and `thumb/`; the Lambda `sun-video-builder` writes
`video/` and `manifest/`). Consumer: this site. Offered to Sunback as input to
its `CONTRACT.md` (SB-6). Where the two differ, read the live objects and
correct whichever file is wrong.

Append-only, like every data contract in the suite: add keys beside the old
ones; never rename or remove one. `tools/check_site.py` rule `contract` reads
the fenced blocks below; edit them, not the prose, when the contract changes.

## Bucket

`https://the-sun-now.s3.us-east-2.amazonaws.com/` (AWS S3, us-east-2, public
read; `sun.html:140`). Imagery is in S3, not R2.

## Product ids

The 12 ids in `sun.html` `PRODUCTS` order. The check fails when this block and
`PRODUCTS` disagree. Nobody edits `PRODUCTS` (HG-4 and SB-6 parse it).

```ids
rainbow
171
193
211
304
335
94
131
1600
1700
composite_uv
dem
```

## manifest/<id>.json

One JSON object per id. Fields the site reads (`m.<field>` in `sun.html`);
each must be a non-empty string:

```fields
updated
img1k
thumb
video
```

| Field | Value | Read at |
|---|---|---|
| `updated` | ISO 8601 UTC with `Z`, for example `2026-10-01T15:23:15Z`: time of the newest still; also the `?v=` cache-buster | `sun.html:232` |
| `img1k` | key `1k/rhef_<id>_1k.png` | `sun.html:234`, `:241` |
| `thumb` | key `thumb/rhef_<id>_thumb.png` | `sun.html:236` |
| `video` | key `video/rhef_<id>_1k.mp4`, the 48-hour timelapse | `sun.html:234` |

Optional fields. The producer may write them; a reader must not require them:

```optional
id
label
frame_count
integration
video_v
still_v
through
strip
times
hdr_img
hdr_video
```

| Field | Value | Source |
|---|---|---|
| `id`, `label` | the product id and its label (same text as `PRODUCTS`) | `manifest.py:55-67` |
| `frame_count` | integer, distinct frames in the timelapse | `manifest.py:65` |
| `integration` | `{"frames": int, "method": str}` or `null` | `handler.py` (median of 5 by default) |
| `video_v`, `still_v` | immutable keys `v/<id>/<stamp>.mp4` and `v/<id>/<stamp>.png` | SB-1 (sunback `claude/versioned-keys`); present in the live bucket on 2026-10-01 (plan writer's GET of `manifest/171.json`, not re-read by the implementer) |
| `through` | ISO 8601 UTC time of the newest frame in the video | SB-1 |
| `strip`, `times` | proposed by SB-14 (per-slot strip and times); not written yet | SB-14 |
| `hdr_img`, `hdr_video` | proposed by SB-23; not written yet | SB-23 |

## image_times.txt

One line, UTC, no zone suffix, for example `2026-10-01T15:03:02.081`
(computed: GET on 2026-10-01). `sun.html:204-206` appends `Z` when it is absent.

## Fixed keys read elsewhere on the site

- `thumb/rhef_171_thumb.png`: homepage Sun card (`index.html:140`).
- `1k/rhef_rainbow_1k.png`: `og:image` of `sun.html` (`sun.html:22`).
- `video/rhef_tscan.mp4`: the DEM temperature scan (`sun.html:150`, `TSCAN_KEY`).
- `sun-wall.html:30` has its own `BUCKET` and reads `m.id`, `m.label`,
  `m.updated`, `m.video` (and `m.base` from a wall app's local manifest).

## Fixtures

`fixtures/sun/` holds the 12 manifests and `image_times.txt`, and one 8x8 grey
PNG at every `thumb` and `img1k` key the manifests name. No videos: previews
fail softly offline. **These files are synthesized from this contract, not
captured** (the session that wrote them had no permission to call the bucket):
they carry only `id`, `label`, `updated`, `img1k`, `thumb` and `video`. Replace
them with the real objects by a read-only GET:
`python3 fixtures/sun/capture.py --refresh`, then commit the result and append
any new field to the `optional` block. `sun.html` reads them only on localhost
with `?fixtures` (`python3 -m http.server 8000`, then
`http://localhost:8000/sun.html?fixtures`). `robots.txt` disallows `/fixtures/`.
