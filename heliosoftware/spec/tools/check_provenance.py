#!/usr/bin/env python3
"""Check that exported files carry HelioSoftware provenance (suite SU-18).

  python3 check_provenance.py FILE...

Reads PNG, FITS, MP4 and `<name>.provenance.json` files (format: ../provenance.md). Prints
`OK <file>` or `DRIFT <file>: <reason>` per file. Exit 0 all files pass, 1 any file fails,
2 a file cannot be read or is not one of those formats (or no file was given).

Standard library only; Python 3.9 and later.
"""
from __future__ import annotations

import json
import pathlib
import re
import struct
import sys

STAMP = re.compile(
    r"^RHEF (\S+) via (\S+) (\S+); upsilon=(none|[0-9.eE+-]+,[0-9.eE+-]+); "
    r"deviations=(none|[A-Z0-9-]+(?:,[A-Z0-9-]+)*)(; ref=doi:\S+)?$")
REQUIRED = ("product", "version", "instrument", "observed", "credit")
OBSERVED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ATTRIBUTION = pathlib.Path(__file__).resolve().parents[1] / "attribution.json"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MP4_READ = 8 * 1024 * 1024


class Unreadable(Exception):
    pass


def attribution() -> dict:
    try:
        return json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def check_object(obj) -> list:
    """Problems with a provenance object (PNG chunk or sidecar)."""
    if not isinstance(obj, dict):
        return ["provenance is not a JSON object"]
    out = []
    for key in REQUIRED:
        if not isinstance(obj.get(key), str) or not obj[key]:
            out.append(f"missing {key}")
    for key, value in obj.items():
        if value is not None and not isinstance(value, str):
            out.append(f"{key} is not a string or null")
    if isinstance(obj.get("observed"), str) and obj["observed"] and not OBSERVED.match(obj["observed"]):
        out.append("observed is not YYYY-MM-DDTHH:MM:SSZ")
    if obj.get("rhef") is not None and isinstance(obj.get("rhef"), str) and not STAMP.match(obj["rhef"]):
        out.append("rhef is not a stamp line")
    credit = attribution().get("credit")
    if credit and isinstance(obj.get("credit"), str) and obj["credit"] and obj["credit"] != credit:
        out.append("credit differs from attribution.json")
    return out


def png_text(data: bytes) -> dict:
    if data[:8] != PNG_MAGIC:
        raise Unreadable("not a PNG")
    out, pos = {}, 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        if kind == b"tEXt" and b"\0" in body:
            key, _, text = body.partition(b"\0")
            out[key.decode("latin-1")] = text.decode("utf-8", "replace")
        elif kind == b"iTXt" and b"\0" in body:
            key, _, rest = body.partition(b"\0")
            if len(rest) >= 2 and rest[0] == 0:                      # uncompressed only
                _lang, _, rest = rest[2:].partition(b"\0")
                _trans, _, text = rest.partition(b"\0")
                out[key.decode("utf-8", "replace")] = text.decode("utf-8", "replace")
        elif kind == b"IEND":
            break
        pos += 12 + length
    return out


def check_png(data: bytes) -> list:
    text = png_text(data)
    if "HelioSoftware-Provenance" not in text:
        return ["no HelioSoftware-Provenance chunk"]
    try:
        obj = json.loads(text["HelioSoftware-Provenance"])
    except ValueError:
        return ["HelioSoftware-Provenance is not JSON"]
    out = check_object(obj)
    if isinstance(obj, dict) and obj.get("rhef"):
        if text.get("RHEF") != obj["rhef"]:
            out.append("RHEF chunk missing or different from rhef")
        if not text.get("Disclaimer"):
            out.append("missing Disclaimer chunk beside the stamp")
    elif "RHEF" in text:
        out.append("RHEF chunk without rhef in the provenance object")
    return out


def fits_cards(data: bytes) -> list:
    cards = []
    for off in range(0, len(data), 80):
        card = data[off:off + 80].decode("ascii", "replace")
        if card.startswith("END") and not card[3:].strip():
            return cards
        cards.append(card)
        if off > 2880 * 40:
            break
    raise Unreadable("no END card in the first 40 header blocks")


def check_fits(data: bytes) -> list:
    if data[:6] != b"SIMPLE":
        raise Unreadable("not a FITS file")
    cards = fits_cards(data)
    out = []
    if not any(c.startswith("ORIGIN  =") and re.search(r"'[^']+'", c) for c in cards):
        out.append("missing ORIGIN")
    lines, current = [], ""
    for c in cards:                       # a HISTORY card filled to column 80 continues on the next
        if c.startswith("HISTORY"):
            body = c[8:80].rstrip()
            current += body
            if len(body) < 72:
                lines.append(current); current = ""
        elif current:
            lines.append(current); current = ""
    if current:
        lines.append(current)
    text = "\n".join(lines)
    credit = attribution().get("credit")
    if credit and credit not in text.replace("\n", ""):
        out.append("missing the credit line in HISTORY")
    stamps = [ln.strip() for ln in lines if re.match(r"RHEF \S+ via ", ln.strip())]   # the disclaimer also starts with RHEF
    for s in stamps:
        if not STAMP.match(s):
            out.append("a HISTORY RHEF line is not a stamp line")
    disclaimer = attribution().get("disclaimer")
    if stamps and disclaimer and disclaimer not in text.replace("\n", ""):
        out.append("missing the disclaimer beside the stamp")
    return out


def mp4_tag(data: bytes, tag: bytes):
    """Text of an iTunes-style metadata item (`(c)cmt`, `desc`) as ffmpeg writes it."""
    i = data.find(tag)
    while i != -1:
        if i >= 4 and data[i + 8:i + 12] == b"data":
            (dsize,) = struct.unpack(">I", data[i + 4:i + 8])
            return data[i + 20:i + 4 + dsize].decode("utf-8", "replace")
        i = data.find(tag, i + 1)
    return None


def mp4_mdta(data: bytes) -> dict:
    """Tags ffmpeg writes as mdta keys (with `-movflags use_metadata_tags`): a `keys` atom
    names them in order, and each `ilst` item's type is its 1-based index into that list."""
    k = data.find(b"keys")
    if k < 4:
        return {}
    (count,) = struct.unpack(">I", data[k + 8:k + 12])
    names, pos = [], k + 12
    for _ in range(count):
        (size,) = struct.unpack(">I", data[pos:pos + 4])
        if size < 8:
            return {}
        names.append(data[pos + 8:pos + size].decode("utf-8", "replace"))
        pos += size
    i = data.find(b"ilst", pos)
    if i < 4:
        return {}
    (ilst_size,) = struct.unpack(">I", data[i - 4:i])
    end, pos, tags = i - 4 + ilst_size, i + 4, {}
    while pos + 8 <= end:
        size, index = struct.unpack(">II", data[pos:pos + 8])
        if size < 8:
            break
        if data[pos + 12:pos + 16] == b"data" and 1 <= index <= len(names):
            (dsize,) = struct.unpack(">I", data[pos + 8:pos + 12])
            tags[names[index - 1]] = data[pos + 24:pos + 8 + dsize].decode("utf-8", "replace")
        pos += size
    return tags


def check_mp4(data: bytes) -> list:
    if data[4:8] != b"ftyp":
        raise Unreadable("not an MP4")
    out = []
    desc, comment = mp4_tag(data, b"desc"), mp4_tag(data, b"\xa9cmt")
    if desc is None and comment is None:
        keyed = mp4_mdta(data)
        desc, comment = keyed.get("description"), keyed.get("comment")
    credit = attribution().get("credit")
    if not desc:
        out.append("missing description (the credit line)")
    elif credit and desc != credit:
        out.append("description differs from the credit line in attribution.json")
    if comment is not None and comment.startswith("RHEF ") and not STAMP.match(comment):
        out.append("comment is not a stamp line")
    return out


def check_file(path: pathlib.Path) -> list:
    name = path.name.lower()
    try:
        if name.endswith(".provenance.json"):
            return check_object(json.loads(path.read_text(encoding="utf-8")))
        if name.endswith(".png"):
            return check_png(path.read_bytes())
        if name.endswith((".fits", ".fit", ".fts")):
            with open(path, "rb") as fh:
                return check_fits(fh.read(2880 * 41))
        if name.endswith((".mp4", ".m4v", ".mov")):
            with open(path, "rb") as fh:
                head = fh.read(MP4_READ)
                size = fh.seek(0, 2)
                tail = b""
                if size > MP4_READ:                       # moov may sit at the end
                    fh.seek(max(MP4_READ, size - MP4_READ)); tail = fh.read()
            return check_mp4(head + tail)
    except (OSError, ValueError) as e:
        raise Unreadable(str(e))
    raise Unreadable("not a PNG, FITS, MP4 or .provenance.json file")


def main(argv: list) -> int:
    if not argv:
        print("usage: check_provenance.py FILE...", file=sys.stderr)
        return 2
    code = 0
    for arg in argv:
        path = pathlib.Path(arg)
        try:
            problems = check_file(path)
        except Unreadable as e:
            print(f"UNREADABLE {arg}: {e}", file=sys.stderr)
            code = max(code, 2)
            continue
        if problems:
            print(f"DRIFT {arg}: " + "; ".join(problems))
            code = max(code, 1)
        else:
            print(f"OK {arg}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
