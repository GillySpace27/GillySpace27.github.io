# Provenance of exported images, movies and sidecars

Version 1. What every HelioSoftware product writes into an image, a movie or a sidecar file it
exports, so the file explains itself after it has left the app: which product made it, from
which instrument and moment, whether RHEF was applied and with what settings, who is credited,
and that RHEF output is a visualization.

This page is the format. It adds nothing to the RHEF stamp line, which stays exactly as
[rhef/conventions.md](rhef/conventions.md) section 5 defines it, and it never replaces a product's
own export code: each product writes these fields, and
[tools/check_provenance.py](tools/check_provenance.py) reads them back.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `product` | yes | Product id: `heliogram`, `heliofits`, `heliofits-studio`, `sunback`, `my-heliogram`, `gilly.space`. |
| `version` | yes | The product's own version string. |
| `instrument` | yes | Observatory, instrument and channel, e.g. `SDO/AIA 171`. `unknown` when not known. |
| `observed` | yes | Observation time, UTC, `YYYY-MM-DDTHH:MM:SSZ`. For a movie, the time of its last frame. |
| `credit` | yes | The credit line, built from [attribution.json](attribution.json) by its `credits_rule`: each enabled layer's instrument credit from `credits`, in layer order, each once, joined with one space; `credit_fallback` when none applies. `credit` alone remains valid (the AIA wall line). |
| `rhef` | when RHEF was applied | The RHEF stamp line, byte for byte. `null` for a photometric export. |
| `citation` | no | Text from [attribution.json](attribution.json) `rhef_citation` once Gilly sets it; `null` until then. |

Every value is a string or `null`. A field never holds a user name, a path on the person's computer,
a display name or an identifier of the person or the machine: these are facts about the picture.
RHEF output is a visualization, not a calibrated radiance; an export that carries `rhef` also
carries the disclaimer text in [attribution.json](attribution.json) `disclaimer`.

## Where each format keeps them

### PNG

Text chunks (`tEXt`; `iTXt` without compression is read as well):

| Keyword | Value |
|---|---|
| `HelioSoftware-Provenance` | One JSON object with the fields above (UTF-8). Required. |
| `RHEF` | The stamp line. Present exactly when `rhef` is not null (the chunk RHEF conventions already define). |
| `Disclaimer` | The disclaimer text. Present exactly when `RHEF` is. |
| `Software` | `<product> <version>`. Optional, for tools that only read the standard keywords. |
| `Source` | The `instrument` field. Optional. |
| `Creation Time` | The `observed` field. Optional. |

### FITS

| Card | Value |
|---|---|
| `ORIGIN` | `'<product> <version>'`. Required. |
| `HISTORY` | The credit line, as its own card. Required. |
| `HISTORY` | The stamp line, as its own card, when RHEF was applied (RHEF conventions section 5). |
| `HISTORY` | The disclaimer, as its own card, when the stamp is present. |

A card is 80 characters, which leaves 72 for the text after `HISTORY `. A line of 72 or more characters
continues on the next `HISTORY` card (the first card is filled to column 80); a shorter line ends its card.
A reader joins a filled card with the one after it before it looks for a line.

### MP4 (ffmpeg)

| Tag | Value |
|---|---|
| `comment` | The stamp line, when RHEF was applied (RHEF conventions section 5). Absent otherwise. |
| `description` | The credit line. Required. |

```text
ffmpeg ... -metadata comment="$STAMP" -metadata description="$CREDIT" out.mp4
```

### Sidecar

A file named `<basename>.provenance.json` beside the export holds the same object as the PNG
`HelioSoftware-Provenance` chunk. Name the basename only, never a directory. Use a sidecar where the
format has no place for text (a JPEG a service strips, a still inside a PDF).

```json
{
  "product": "heliogram",
  "version": "0.8",
  "instrument": "SDO/AIA 171",
  "observed": "2026-10-02T18:30:00Z",
  "credit": "Imagery courtesy of NASA/SDO and the AIA science team.",
  "rhef": "RHEF sunkit-0.7 via sunkit 0.7.0; upsilon=0.35,0.35; deviations=none",
  "citation": null
}
```

The values above show the shape; they are not a record of a real export.

## The check

```text
python3 tools/check_provenance.py FILE...
```

Prints `OK <file>` or `DRIFT <file>: <what is missing or wrong>` per file. Exit 0 when every file passes,
1 when any file is missing a field or carries a wrong one, 2 when a file cannot be read or is not
a PNG, FITS, MP4 or `.provenance.json` file. The checker confirms the credit line follows
[attribution.json](attribution.json) `credits_rule` when it can find that file beside itself; in FITS
`HISTORY` it looks for at least one of the lines that file lists.

## Instrument credits

[attribution.json](attribution.json) `credits` maps an instrument (`SDO/AIA`, `SOHO/LASCO`,
`STEREO/SECCHI`, `PUNCH`, ...) to `credit`, the line an export writes (ASCII, so it fits a FITS
card), and `acknowledgement`, the team's publication statement verbatim, which a processing record
puts in the layer's `acknowledgement`. `kind` says whether the source requires the statement or only
asks for it; `source` is the page it was read from on `credits_read`. An instrument whose team gives no
statement (GOES/SUVI today) has `credit` null and adds nothing. Which header values map to which key is
the producer's job; the keys only name the instrument.

## Status

Version 1 is the format and the checker. No product writes it yet; each product adopts it in its own
change (sunback manifest keys `rhef` and `credit`, the store's creator string and JSON-LD, Heliogram's
Wall caption, HelioFITS and Studio exports). Adding a product is additive: nothing here is removed or
renamed once a product reads it.

The detailed companion, written beside this stamp by every export: [processing-record.md](processing-record.md).
