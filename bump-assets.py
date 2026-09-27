#!/usr/bin/env python3
"""Stamp a fresh ?v= on every page's link to the shared CSS/JS.

Run after changing assets/site.css, assets/product.css, assets/site.js or a
partial. Each page then asks for exactly the files it was deployed with, so a
CDN edge still caching the old stylesheet can't pair it with new markup.
site.js passes the same stamp on to the header/footer partials.
"""
import pathlib, re, time

v = time.strftime("%Y%m%d%H%M")
pat = re.compile(r'(/assets/(?:site|product)\.(?:css|js))(?:\?v=\w+)?"')
total = 0
for p in pathlib.Path(__file__).parent.rglob("*.html"):
    s = p.read_text()
    s2, n = pat.subn(rf'\1?v={v}"', s)
    if n:
        p.write_text(s2)
        total += n
assert total, "no asset links found"
print(f"v={v}: {total} links updated")
