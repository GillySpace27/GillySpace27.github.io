#!/usr/bin/env python3
"""Append one release record to heliosoftware/feed/<product>.json (suite SU-11).

    python3 append_record.py --product heliogram --version 0.8 --build 8 --date 2026-10-02 \
        --channel direct --tag v0.8-build.8 --url https://gilly.space/heliogram/ \
        --notes-file notes.txt \
        --asset name=Heliogram-0.8.dmg,url=https://gilly.space/heliogram/Heliogram-0.8.dmg,sha256=<64 hex>,bytes=12226044,platform=macos-universal,confirmed=true

Append-only: an existing record is never edited or removed, and a record whose
(version, build) is already present is refused. Exit 0 appended, 1 invalid (nothing
written), 2 usage, 3 duplicate (nothing written). Standard library only, no network;
it writes only the one product file, atomically.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DASH = "\u2014"
PRODUCTS = {
    "heliofits": ("HelioFITS", "https://gilly.space/heliofits/"),
    "heliofits-studio": ("HelioFITS Studio", "https://gilly.space/heliofits-studio/"),
    "heliogram": ("Heliogram", "https://gilly.space/heliogram/"),
    "sunback": ("sunback", "https://pypi.org/project/sunback/"),
}
CHANNELS = ("mac-app-store", "github-prerelease", "github-release", "direct", "pypi")
NEEDS_ASSET = ("github-prerelease", "github-release", "direct", "pypi")
HEX64 = re.compile(r"[0-9a-f]{64}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_asset(text: str) -> dict:
    kv = {}
    for part in text.split(","):
        key, sep, val = part.partition("=")
        if not sep:
            raise ValueError(f"asset field without '=': {part!r}")
        kv[key.strip()] = val.strip()
    conf = kv.get("confirmed", "false").lower()
    if conf not in ("true", "false"):
        raise ValueError(f"asset confirmed must be true or false, not {conf!r}")
    try:
        size = int(kv["bytes"])
    except (KeyError, ValueError):
        raise ValueError("asset needs an integer bytes=") from None
    return {"name": kv.get("name", ""), "url": kv.get("url", ""), "sha256": kv.get("sha256", ""),
            "bytes": size, "platform": kv.get("platform", ""), "confirmed": conf == "true"}


def url_errors(label: str, url: str) -> list[str]:
    out = []
    if not url.startswith("https://"):
        out.append(f"{label} must start with https://")
    if "/releases/latest" in url:
        out.append(f"{label} must not use /releases/latest (hand out the /releases index or a tag page)")
    return out


def validate_record(rec: dict) -> list[str]:
    errs: list[str] = []
    if not str(rec.get("version", "")).strip():
        errs.append("version is empty")
    if "build" in rec and (not isinstance(rec["build"], int) or isinstance(rec["build"], bool) or rec["build"] < 0):
        errs.append("build must be a non-negative integer")
    date = str(rec.get("date", ""))
    try:
        if not DATE.fullmatch(date):
            raise ValueError(date)
        datetime.date.fromisoformat(date)
    except ValueError:
        errs.append(f"date {date!r} is not a calendar date YYYY-MM-DD")
    channel = rec.get("channel")
    if channel not in CHANNELS:
        errs.append(f"channel {channel!r} is not one of {', '.join(CHANNELS)}")
    errs += url_errors("url", str(rec.get("url", "")))
    notes = rec.get("notes", "")
    if not isinstance(notes, str) or not notes.strip():
        errs.append("notes are empty")
    elif DASH in notes:
        errs.append("notes contain U+2014; use a colon, semicolon, comma or parentheses")
    assets = rec.get("assets", [])
    if channel in NEEDS_ASSET and not assets:
        errs.append(f"channel {channel} needs at least one asset with a sha256")
    for i, a in enumerate(assets):
        where = f"asset {a.get('name') or i}"
        if not a.get("name"):
            errs.append(f"{where}: name is empty")
        errs += [f"{where}: {e}" for e in url_errors("url", str(a.get("url", "")))]
        if not HEX64.fullmatch(str(a.get("sha256", ""))):
            errs.append(f"{where}: sha256 is missing or not 64 lowercase hex")
        size = a.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errs.append(f"{where}: bytes must be a non-negative integer")
        if not a.get("platform"):
            errs.append(f"{where}: platform is empty")
        if not isinstance(a.get("confirmed"), bool):
            errs.append(f"{where}: confirmed must be true or false")
    return errs


def append(feed_dir: pathlib.Path, product: str, rec: dict) -> int:
    feed_dir.mkdir(parents=True, exist_ok=True)
    path = feed_dir / f"{product}.json"
    name, page = PRODUCTS[product]
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("product") != product or not isinstance(data.get("records"), list):
            raise ValueError(f"{path.name} does not look like the {product} feed; nothing written")
    else:
        data = {"product": product, "name": name, "page": page, "records": []}
    for old in data["records"]:
        if old.get("version") == rec["version"] and old.get("build") == rec.get("build"):
            print(f"append_record: {product} {rec['version']} build {rec.get('build')} is already recorded; nothing written",
                  file=sys.stderr)
            return 3
    data["records"].append(rec)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--product", required=True, choices=sorted(PRODUCTS))
    ap.add_argument("--version", required=True)
    ap.add_argument("--build", type=int)
    ap.add_argument("--name", help="the product's name at this version, when it differs from the feed's")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD, UTC")
    ap.add_argument("--channel", required=True, choices=CHANNELS)
    ap.add_argument("--tag")
    ap.add_argument("--url", required=True)
    ap.add_argument("--notes-file", required=True, type=pathlib.Path)
    ap.add_argument("--asset", action="append", default=[], help="name=,url=,sha256=,bytes=,platform=,confirmed=")
    ap.add_argument("--feed-dir", type=pathlib.Path, default=HERE)
    args = ap.parse_args(argv)
    try:
        notes = args.notes_file.read_text(encoding="utf-8").strip()
        assets = [parse_asset(a) for a in args.asset]
    except (OSError, ValueError) as exc:
        print(f"append_record: {exc}", file=sys.stderr)
        return 1
    rec: dict = {"version": args.version}
    if args.build is not None:
        rec["build"] = args.build
    if args.name:
        rec["name"] = args.name
    rec["date"] = args.date
    rec["channel"] = args.channel
    if args.tag:
        rec["tag"] = args.tag
    rec.update({"url": args.url, "notes": notes, "assets": assets})
    errs = validate_record(rec)
    if errs:
        for e in errs:
            print(f"append_record: {e}", file=sys.stderr)
        return 1
    try:
        return append(args.feed_dir.resolve(), args.product, rec)
    except (OSError, ValueError) as exc:
        print(f"append_record: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
