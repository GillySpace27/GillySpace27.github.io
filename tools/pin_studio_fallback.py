#!/usr/bin/env python3
"""Pin the offline fallback links on heliofits-studio/index.html to one release (WS-8).

python3 tools/pin_studio_fallback.py VERSION [--from-github] [--dry-run] [--root PATH]
python3 tools/pin_studio_fallback.py --from-github        (VERSION = the newest release tag)

Replaces every occurrence of the pinned version and exits 1, writing nothing, unless
the new version then occurs exactly as often as the old one did and PLATFORMS is
unchanged. Never touches PLATFORMS or a confirmed flag: a tile lights only after a
human runs that build on real hardware. --from-github reads the newest release
(releases?per_page=1; every release so far is a pre-release, which /releases/latest
skips) and refuses unless every asset in contracts/studio-release-assets.md exists.
Read-only against GitHub.
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
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402  (WS-4: contract_block, CONTRACT_STUDIO, STUDIO_PAGE, STUDIO_PIN_RE)

RELEASES_API = "https://api.github.com/repos/GillySpace27/HelioFITS-Studio/releases?per_page=1"
VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")
PLATFORMS_RE = re.compile(r"^const PLATFORMS = \{.*?^\};", re.M | re.S)
CONFIRMED_RE = re.compile(r"^\s*(\w+):\s*\{\s*confirmed:\s*(true|false)", re.M)


class PinError(Exception):
    pass


def version_rx(version):
    """The version as a whole token: not inside 10.8.2, 0.8.20 or 0.8.2.1."""
    return re.compile(r"(?<![\d.])" + re.escape(version) + r"(?!\.?\d)")


def pin(text, new):
    """(new_text, old_version, count); raises PinError and changes nothing on any mismatch."""
    if not VERSION_RE.match(new):
        raise PinError(f"not a version: {new!r}")
    m = check_site.STUDIO_PIN_RE.search(text)
    if not m:
        raise PinError("no HFStudio-<version>.dmg link on the page")
    plat = PLATFORMS_RE.search(text)
    if not plat:
        raise PinError("PLATFORMS not found on the page")
    old = m.group(1)
    before = len(version_rx(old).findall(text))
    if old == new:
        return text, old, before
    if version_rx(new).search(text):
        raise PinError(f"{new} already occurs on the page before patching; refusing to mix versions")
    out, replaced = version_rx(old).subn(new, text)
    after = len(version_rx(new).findall(out))
    if not (before == replaced == after) or version_rx(old).search(out):
        raise PinError(f"count mismatch: {before} occurrences of {old} before, {replaced} replaced, {after} of {new} after")
    new_plat = PLATFORMS_RE.search(out)
    if not new_plat or new_plat.group(0) != plat.group(0):
        raise PinError("PLATFORMS would change; it is edited by hand only")
    return out, old, before


def release_assets(url=RELEASES_API):
    """(newest tag, asset names) from the GitHub releases API; GET only."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "gilly.space-pin-studio-fallback"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            rels = json.load(r)
    except OSError as e:
        raise PinError(f"cannot read {url}: {e}") from e
    if not rels:
        raise PinError("GitHub lists no releases")
    return rels[0]["tag_name"], {a["name"] for a in rels[0].get("assets", [])}


def missing_assets(templates, version, names):
    return [t.replace("{v}", version) for t in templates if t.replace("{v}", version) not in names]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pin the Studio download page's fallback links (WS-8).")
    ap.add_argument("version", nargs="?")
    ap.add_argument("--from-github", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", type=pathlib.Path, default=TOOLS.parent)
    a = ap.parse_args(argv)
    if not a.version and not a.from_github:
        ap.error("VERSION is required without --from-github")
    page = a.root / check_site.STUDIO_PAGE
    version = a.version
    try:
        if a.from_github:
            tag, names = release_assets()
            if not version:
                version = tag[1:] if tag.startswith("v") else tag
            templates = check_site.contract_block(a.root / check_site.CONTRACT_STUDIO, "assets")
            try:  # an optional asset may be absent; its fallback link then stays on an older release
                optional = set(check_site.contract_block(a.root / check_site.CONTRACT_STUDIO, "optional-assets"))
            except ValueError:
                optional = set()
            templates = [t for t in templates if t not in optional]
            problems = [f"MISSING {n}" for n in missing_assets(templates, version, names)]
            if tag != "v" + version:
                problems.insert(0, f"newest release is {tag}, not v{version}")
            if problems:
                raise PinError("; ".join(problems))
        text = page.read_text(encoding="utf-8")
        new_text, old, count = pin(text, version)
    except (PinError, ValueError) as e:
        print(f"pin_studio_fallback: {e}", file=sys.stderr)
        return 1
    if new_text == text:
        print(f"already pinned to {version} ({count} occurrences); nothing to do")
    elif a.dry_run:
        print(f"would pin {old} -> {version}: {count} occurrences in {check_site.STUDIO_PAGE}")
    else:
        page.write_text(new_text, encoding="utf-8")
        print(f"pinned {old} -> {version}: {count} occurrences in {check_site.STUDIO_PAGE}")
    for pid, state in CONFIRMED_RE.findall(text):
        print(f"confirmed {pid}={state} (unchanged)")
    print("A tile lights only after someone runs that build on real hardware; then Gilly edits"
          " its confirmed flag in PLATFORMS by hand (SITE.md, Studio fallback pin).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
