#!/usr/bin/env python3
"""Stamp a fresh ?v= on every page's link to the shared CSS/JS.

Run after changing assets/site.css, assets/product.css, assets/site.js,
assets/product.js or a partial. Each page then asks for exactly the files it
was deployed with, so a CDN edge still caching the old stylesheet can't pair
it with new markup. site.js passes the same stamp on to the header/footer
partials, and sw.js gets CACHE_VERSION = 'gilly-<stamp>' so returning
visitors drop the old service-worker cache.

Only HTML files tracked by git in this checkout are touched (git ls-files),
never .claude/worktrees/ or any other checkout below it.

  python3 bump-assets.py              stamp every tracked page and sw.js
  python3 bump-assets.py --dry-run    list what would change, write nothing
  python3 bump-assets.py --check      exit 1 if stamps disagree or are missing
  --root PATH                         repository to work on (default: here)
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import subprocess
import sys
import time

STAMPED_ASSETS = ("site.css", "product.css", "site.js", "product.js")
CHECK_WARN_ONLY = ("heliograph/index.html", "heliogram/index.html")
LINK = re.compile(r'(/assets/(?:%s))(?:\?v=(\w+))?"' % "|".join(re.escape(a) for a in STAMPED_ASSETS))
SW_LINE = re.compile(r"const CACHE_VERSION = '([^']*)';")


def tracked_html(root: pathlib.Path) -> list[pathlib.Path]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "*.html"],
                         check=True, capture_output=True).stdout.decode()
    return [root / rel for rel in out.split("\0") if rel]


def check(root: pathlib.Path, pages: list[pathlib.Path]) -> int:
    stamps: dict[str, list[str]] = {}
    problems: list[tuple[str, str]] = []
    for p in pages:
        rel = p.relative_to(root).as_posix()
        for m in LINK.finditer(p.read_text()):
            if m.group(2):
                stamps.setdefault(rel, []).append(m.group(2))
            else:
                problems.append((rel, f"unstamped link to {m.group(1)}"))
    counts = collections.Counter(s for vs in stamps.values() for s in vs)
    majority = max(counts, key=lambda s: (counts[s], s)) if counts else None
    for rel, vs in stamps.items():
        for other in sorted(set(vs) - {majority}):
            problems.append((rel, f"v={other} differs from v={majority}"))
    sw = root / "sw.js"
    if majority and sw.exists():
        m = SW_LINE.search(sw.read_text())
        if not m:
            problems.append(("sw.js", "no CACHE_VERSION line"))
        elif m.group(1) != f"gilly-{majority}":
            problems.append(("sw.js", f"CACHE_VERSION {m.group(1)} is not gilly-{majority}"))
    failed = 0
    for rel, reason in problems:
        if rel in CHECK_WARN_ONLY:
            print(f"WARN {rel}: {reason}")
        else:
            print(f"STAMP {rel}: {reason}")
            failed = 1
    return failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()
    pages = tracked_html(root)
    if args.check:
        return check(root, pages)

    v = time.strftime("%Y%m%d%H%M")
    sw = root / "sw.js"
    sw_text, sw_n = SW_LINE.subn(f"const CACHE_VERSION = 'gilly-{v}';", sw.read_text())
    if sw_n != 1:
        print(f"sw.js: expected 1 CACHE_VERSION line, found {sw_n}; nothing written", file=sys.stderr)
        return 1
    total = 0
    for p in pages:
        s = p.read_text()
        s2, n = LINK.subn(rf'\1?v={v}"', s)
        if not n:
            continue
        total += n
        if args.dry_run:
            print(f"would update {p.relative_to(root).as_posix()} ({n})")
        else:
            p.write_text(s2)
    assert total, "no asset links found"
    if args.dry_run:
        print(f"would update sw.js (CACHE_VERSION gilly-{v})")
        print(f"v={v}: {total} links would be updated (dry run, nothing written)")
        return 0
    sw.write_text(sw_text)
    print(f"v={v}: {total} links updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
