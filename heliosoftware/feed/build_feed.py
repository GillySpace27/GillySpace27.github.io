#!/usr/bin/env python3
"""Render the family release feed (suite SU-11).

    python3 heliosoftware/feed/build_feed.py [--check] [--feed-dir DIR]

Reads heliosoftware/feed/*.json and writes heliosoftware/feed.xml (Atom) and
heliosoftware/whats-new/index.html. Deterministic: no clock, so --check can run in CI.
Both outputs are regenerated from tracked records; nothing else is written. Exit 1
(nothing written) when a record is invalid or the hub page has no ?v= stamp to copy;
--check writes nothing and exits 1 when an output would change.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import append_record as ar  # noqa: E402

ATOM = "http://www.w3.org/2005/Atom"
SITE = "https://gilly.space"
STAMP_RE = re.compile(r"/assets/site\.css\?v=(\w+)")
CHANNEL_LABEL = {
    "mac-app-store": "Mac App Store",
    "github-prerelease": "GitHub pre-release",
    "github-release": "GitHub release",
    "direct": "direct download",
    "pypi": "PyPI",
}

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What's new · HelioSoftware · gilly.space</title>
<meta name="description" content="Release notes for Heliogram, HelioFITS, HelioFITS Studio and sunback, newest first.">
<link rel="alternate" type="application/atom+xml" title="HelioSoftware releases" href="/heliosoftware/feed.xml">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<script>
  (function () {
    try {
      var mode = localStorage.getItem('enso-theme') || 'system';
      var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (mode === 'dark' || (mode === 'system' && prefersDark)) document.documentElement.classList.add('dark');
    } catch (e) {}
  })();
</script>
<meta name="theme-color" content="#faf8f3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#1a1814" media="(prefers-color-scheme: dark)">
<link rel="stylesheet" href="/assets/css/academicons.min.css">
<link rel="stylesheet" href="/assets/css/font-awesome.min.css">
<link rel="stylesheet" href="/assets/site.css?v=@STAMP@">
<link rel="stylesheet" href="/assets/product.css?v=@STAMP@">
</head>
<body>
<div data-include="header"></div>
<main id="main" class="product product--wide" data-no-blank>
  <p class="eyebrow"><a href="/heliosoftware/">HelioSoftware</a></p>
  <h1>What's new</h1>
  <p class="tag">Every release of the family, newest first. Also as an <a href="/heliosoftware/feed.xml">Atom feed</a>.</p>
  <ul class="points">
@ENTRIES@
  </ul>
</main>
<div data-include="footer"></div>
<script src="/assets/site.js?v=@STAMP@"></script>
</body>
</html>
"""


def vkey(version: str) -> tuple[int, ...]:
    m = re.search(r"\d+(?:\.\d+)*", str(version))
    return tuple(int(x) for x in m.group(0).split(".")) if m else ()


def load_entries(feed_dir: pathlib.Path):
    entries: list = []
    errors: list[str] = []
    for path in sorted(feed_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{path.name}: not valid JSON ({exc})")
            continue
        product = data.get("product")
        if product != path.stem or product not in ar.PRODUCTS:
            errors.append(f"{path.name}: product {product!r} does not match the file name or is unknown")
            continue
        name = data.get("name") or ar.PRODUCTS[product][0]
        for rec in data.get("records", []):
            errors += [f"{product} {rec.get('version')}: {e}" for e in ar.validate_record(rec)]
            entries.append((product, name, rec))
    return entries, errors


def order(entries):
    return sorted(entries, key=lambda e: (e[2].get("date", ""), e[0], vkey(e[2].get("version", "")),
                                          e[2].get("build") or 0), reverse=True)


def entry_id(product: str, rec: dict) -> str:
    build = f"-build.{rec['build']}" if rec.get("build") is not None else ""
    return f"tag:gilly.space,{rec['date']}:{product}-{rec['version']}{build}"


def render_atom(entries) -> str:
    ET.register_namespace("", ATOM)

    def q(tag):
        return f"{{{ATOM}}}{tag}"

    def add(parent, tag, text=None, **attrs):
        el = ET.SubElement(parent, q(tag), attrs)
        if text is not None:
            el.text = text
        return el

    ordered = order(entries)
    newest = ordered[0][2]["date"] if ordered else "1970-01-01"
    feed = ET.Element(q("feed"))
    add(feed, "title", "HelioSoftware releases")
    add(feed, "id", f"{SITE}/heliosoftware/feed.xml")
    add(feed, "updated", f"{newest}T00:00:00Z")
    add(add(feed, "author"), "name", "gilly.space")
    add(feed, "link", rel="self", href=f"{SITE}/heliosoftware/feed.xml")
    add(feed, "link", rel="alternate", href=f"{SITE}/heliosoftware/whats-new/")
    for product, name, rec in ordered:
        e = add(feed, "entry")
        add(e, "id", entry_id(product, rec))
        add(e, "title", f"{rec.get('name') or name} {rec['version']}")
        add(e, "updated", f"{rec['date']}T00:00:00Z")
        add(e, "link", rel="alternate", href=rec["url"])
        add(e, "summary", rec["notes"])
    ET.indent(feed)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(feed, encoding="unicode") + "\n"


def render_page(entries, stamp: str) -> str:
    items = []
    for product, name, rec in order(entries):
        title = html.escape(f"{rec.get('name') or name} {rec['version']}")
        label = CHANNEL_LABEL[rec["channel"]]
        notes = html.escape(rec["notes"])
        url = html.escape(rec["url"], quote=True)
        items.append(f'    <li><b>{title}</b> · {rec["date"]} · {label}<br>{notes} <a href="{url}">Release page</a></li>')
    return PAGE.replace("@STAMP@", stamp).replace("@ENTRIES@", "\n".join(items))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--feed-dir", type=pathlib.Path, default=HERE)
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 when an output would change")
    args = ap.parse_args(argv)
    feed_dir = args.feed_dir.resolve()
    site = feed_dir.parent
    entries, errors = load_entries(feed_dir)
    hub = site / "index.html"
    m = STAMP_RE.search(hub.read_text(encoding="utf-8")) if hub.exists() else None
    if not m:
        errors.append(f"{hub}: no /assets/site.css?v=<stamp> link to copy the stamp from (bump-assets.py writes it)")
    if errors:
        for e in errors:
            print(f"build_feed: {e}", file=sys.stderr)
        return 1
    outputs = {site / "feed.xml": render_atom(entries),
               site / "whats-new" / "index.html": render_page(entries, m.group(1))}
    stale = [p for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    if args.check:
        for p in stale:
            print(f"build_feed: {p.relative_to(site)} would change; run python3 heliosoftware/feed/build_feed.py",
                  file=sys.stderr)
        return 1 if stale else 0
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(outputs[p], encoding="utf-8")
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
