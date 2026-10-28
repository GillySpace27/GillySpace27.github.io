#!/usr/bin/env python3
"""Add one HelioFITS Studio release to the family feed, and so to What's new (WS-21).

python3 tools/feed_studio_release.py [VERSION] [--confirm PLATFORM ...] [--dry-run]
python3 tools/feed_studio_release.py --check     (exit 1 when the newest release is not in the feed)

Reads the release v<VERSION> (default: the newest, releases?per_page=1) from the
GitHub releases API, GET only, and appends one record to
heliosoftware/feed/heliofits-studio.json through append_record.py. The record takes
the tag page, the publish date (UTC), every asset named in
contracts/studio-release-assets.md with GitHub's own sha256 digest and size, and as
notes the first bullet under the release body's "### New in" heading. Every asset is
confirmed: false unless its platform is named with --confirm (a person ran that build
on real hardware). Then run python3 heliosoftware/feed/build_feed.py.
Exit 0 appended (or --check: in the feed), 1 refused or stale, 3 already recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.request

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "heliosoftware" / "feed"))
import check_site  # noqa: E402  (contract_block, CONTRACT_STUDIO)
import append_record as ar  # noqa: E402

API = "https://api.github.com/repos/GillySpace27/HelioFITS-Studio/releases"
PRODUCT = "heliofits-studio"
PLATFORM_OF = {  # asset template -> feed platform, as in the records written by hand before WS-21
    "HFStudio-{v}.dmg": "macos-arm64",
    "HFStudio-{v}-intel.dmg": "macos-x64",
    "HFStudio-{v}-windows.zip": "windows",
    "HFStudio-{v}-linux.tar.gz": "linux",
    "HFStudio-{v}.zip": "any-java25",
    "HFStudio-Guide.pdf": "guide",
}


class FeedError(Exception):
    pass


def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "gilly.space-feed-studio-release"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return json.load(r)
    except OSError as e:
        raise FeedError(f"cannot read {url}: {e}") from e


def fetch_release(version=None):
    if version:
        return get_json(f"{API}/tags/v{version}")
    rels = get_json(f"{API}?per_page=1")
    if not rels:
        raise FeedError("GitHub lists no releases")
    return rels[0]


def first_bullet(body):
    """The first '- ' line under the '### New in' heading, with markdown emphasis and code marks dropped."""
    inside = False
    for line in (body or "").splitlines():
        s = line.strip()
        if s.startswith("### "):
            inside = s.lower().startswith("### new in")
        elif inside and s.startswith("- "):
            text = re.sub(r"[*`]", "", s[2:]).strip()
            return text if text.endswith((".", "!", "?")) else text + "."
    raise FeedError("release body has no bullet under a '### New in' heading; write the notes by hand")


def record_from(rel, templates, confirm):
    tag = rel.get("tag_name", "")
    if not tag.startswith("v"):
        raise FeedError(f"tag {tag!r} does not start with v")
    if rel.get("draft"):
        raise FeedError(f"{tag} is a draft; only a published release goes in the feed")
    version = tag[1:]
    by_name = {a["name"]: a for a in rel.get("assets", [])}
    assets = []
    for t in templates:
        name = t.replace("{v}", version)
        a = by_name.get(name)
        if a is None:
            continue  # an absent asset (v0.8.5 had no Intel dmg) is left out, as before
        digest = str(a.get("digest") or "")
        if not digest.startswith("sha256:"):
            raise FeedError(f"{name}: GitHub gives no sha256 digest; compute it from the file and write the record by hand")
        platform = PLATFORM_OF[t]
        assets.append({"name": name, "url": a["browser_download_url"], "sha256": digest[7:], "bytes": a["size"],
                       "platform": platform, "confirmed": platform in confirm})
    if not any(a["platform"].startswith("macos") for a in assets):
        raise FeedError(f"{tag} has no Mac dmg; refusing a record without the main download")
    return {"version": version, "date": rel["published_at"][:10],
            "channel": "github-prerelease" if rel.get("prerelease") else "github-release",
            "tag": tag, "url": rel["html_url"], "notes": first_bullet(rel.get("body")), "assets": assets}


def in_feed(feed_dir, version):
    path = feed_dir / f"{PRODUCT}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"records": []}
    return any(r.get("version") == version for r in data["records"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add one Studio release to the family feed (WS-21).")
    ap.add_argument("version", nargs="?", help="without the leading v; default the newest release")
    ap.add_argument("--confirm", action="append", default=[], choices=sorted(set(PLATFORM_OF.values())),
                    help="a platform someone ran on real hardware (repeat for more)")
    ap.add_argument("--dry-run", action="store_true", help="print the record; write nothing")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 when the release is not in the feed")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    a = ap.parse_args(argv)
    feed_dir = a.root / "heliosoftware" / "feed"
    try:
        rel = fetch_release(a.version)
        if a.check:
            version = rel.get("tag_name", "").lstrip("v")
            if in_feed(feed_dir, version):
                print(f"feed_studio_release: {version} is in the feed")
                return 0
            print(f"feed_studio_release: {version} is on GitHub but not in the feed; run"
                  f" python3 tools/feed_studio_release.py {version}", file=sys.stderr)
            return 1
        templates = check_site.contract_block(a.root / check_site.CONTRACT_STUDIO, "assets")
        rec = record_from(rel, templates, set(a.confirm))
    except (FeedError, ValueError, KeyError) as e:
        print(f"feed_studio_release: {e}", file=sys.stderr)
        return 1
    errs = ar.validate_record(rec)
    if errs:
        for e in errs:
            print(f"feed_studio_release: {e}", file=sys.stderr)
        return 1
    if a.dry_run:
        print(json.dumps(rec, indent=1, ensure_ascii=False))
        return 0
    code = ar.append(feed_dir, PRODUCT, rec)
    if code == 0:
        print(f"appended HelioFITS Studio {rec['version']} ({rec['date']}); now run"
              " python3 heliosoftware/feed/build_feed.py")
    return code


if __name__ == "__main__":
    sys.exit(main())
