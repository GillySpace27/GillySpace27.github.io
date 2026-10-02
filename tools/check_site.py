#!/usr/bin/env python3
"""One stdlib checker for gilly.space, run locally and in CI on a case-sensitive runner.

  python3 tools/check_site.py [--root PATH] [--only RULE ...]

Exit 0 when there is no FAIL outside tools/known_failures.txt, else 1.
Output: one line per finding, "<LEVEL> <rule> <path>:<line> <target> :: <message>",
LEVEL in FAIL, WARN, KNOWN, SKIP; last line "check_site: <f> failures, <w> warnings, <k> known".

Links resolve against `git ls-files` with exact case, never the disk: the Mac
disk is case-insensitive and GitHub Pages is not. Rules: link, stub, json,
xml, feed, stamp, size, a11y (warn only). `--online` is reserved for SU-10.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import fnmatch
import html.parser
import json
import pathlib
import posixpath
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET

IGNORED_PREFIXES = ("tools/tests/fixtures/", ".claude/")
SAME_ORIGIN_HOSTS = ("gilly.space", "www.gilly.space")
FROZEN_FEED = ("heliograph/appcast.xml", "heliograph/version.json")
HELIOGRAM_FEED = ("heliogram/appcast.xml", "heliogram/version.json")
VERSION_JSON_KEYS = ("version", "build", "page")
SPARKLE_NS = "http://www.andymatuschak.org/xml-namespaces/sparkle"   # for WS-4 and WS-7 (sparkle:* attributes)
SIZE_LIMIT_BYTES = 10 * 1024 * 1024
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "blob:", "#")
LINK_ATTRS = ("href", "src", "poster", "srcset")
PLACEHOLDER = re.compile(r"__[A-Z][A-Z_]*__")   # partials/head.html and tools/templates/ fill-ins


@dataclasses.dataclass
class Ctx:
    root: pathlib.Path
    files: set[str]     # repo-relative POSIX paths, exact case
    pages: list[str]    # tracked *.html outside IGNORED_PREFIXES


Finding = collections.namedtuple("Finding", "level rule path line target msg")
CHECKS: list = []           # callables (ctx: Ctx) -> list[Finding], run in order
EXTERNAL_CHECKS: list = [   # (rule, script, argv); argv runs with cwd = root
    ("stamp", "bump-assets.py", ["python3", "bump-assets.py", "--check"]),
]


def check(rule: str):
    def register(fn):
        fn.rule = rule
        CHECKS.append(fn)
        return fn
    return register


def list_files(root: pathlib.Path) -> set[str]:
    if (root / ".git").exists():
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             check=True, capture_output=True).stdout.decode()
        names = [n for n in out.split("\0") if n]
    else:
        names = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    return {n for n in names if not n.startswith(IGNORED_PREFIXES)}


def read_list(root: pathlib.Path, name: str) -> list[str]:
    p = root / "tools" / name
    if not p.exists():
        return []
    lines = (ln.split("#", 1)[0].strip() for ln in p.read_text().splitlines())
    return [ln for ln in lines if ln]


def resolve(path: str, files: set[str]) -> str | None:
    """Map a URL path to the tracked file GitHub Pages would serve, exact case."""
    p = path.lstrip("/")
    if p == "" or p.endswith("/"):
        cand = p + "index.html"
        return cand if cand in files else None
    if p in files:
        return p
    for cand in (p + ".html", p + "/index.html"):
        if cand in files:
            return cand
    return None


def url_path(page: str, raw: str) -> str | None:
    """Same-origin URL path ("/a/b.html") for an href in `page`, or None to skip."""
    raw = raw.strip()
    if not raw or raw.startswith(SKIP_SCHEMES) or "${" in raw or "{{" in raw or PLACEHOLDER.search(raw):
        return None
    u = urllib.parse.urlsplit(raw)
    if u.scheme or raw.startswith("//"):
        if u.scheme not in ("http", "https", "") or (u.hostname or "") not in SAME_ORIGIN_HOSTS:
            return None
        return urllib.parse.unquote(u.path or "/")
    if not u.path:
        return None
    path = urllib.parse.unquote(u.path)
    if path.startswith("/"):
        return path
    joined = posixpath.normpath(posixpath.join("/" + posixpath.dirname(page), path))
    return joined + ("/" if path.endswith("/") and joined != "/" else "")


def case_hint(path: str, files: set[str]) -> str:
    want = path.lstrip("/").lower()
    for cand in (want, want + "index.html", want + ".html", want + "/index.html"):
        for f in files:
            if f.lower() == cand:
                return f" (case differs: tracked as {f})"
    return ""


def line_of(text: str, needle: str) -> int:
    i = text.find(needle)
    return text.count("\n", 0, i) + 1 if i >= 0 else 0


class _Links(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[int, str]] = []
        self.tags: list[tuple[str, dict, int]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        self.tags.append((tag, a, line))
        for name in LINK_ATTRS:
            v = a.get(name)
            if not v:
                continue
            if name == "srcset":
                for part in v.split(","):
                    if part.strip():
                        self.links.append((line, part.strip().split()[0]))
            else:
                self.links.append((line, v))


def parse_page(text: str) -> _Links:
    p = _Links()
    p.feed(text)
    p.close()
    return p


_META_REFRESH = re.compile(
    r"""<meta[^>]+http-equiv=["']?refresh["']?[^>]*content=["']?\s*\d+\s*;\s*url=([^"'>\s]+)""", re.I)
_LOCATION_REPLACE = re.compile(r"""location\.replace\(\s*["']([^"']+)["']\s*\)""")


def redirect_targets(html_text: str) -> list[str]:
    return [m.group(1) for rx in (_META_REFRESH, _LOCATION_REPLACE) for m in rx.finditer(html_text)]


def parse_redirect_target(html_text: str) -> str | None:
    """Target of a static redirect page: meta refresh first, then location.replace("...")."""
    t = redirect_targets(html_text)
    return t[0] if t else None


def feed_enclosures(xml_text: str) -> list[tuple[str, int]]:
    """(url, length) of every <enclosure> in a Sparkle appcast."""
    out = []
    for enc in ET.fromstring(xml_text.encode()).iter("enclosure"):
        length = enc.get("length") or "0"
        out.append((enc.get("url", ""), int(length) if length.isdigit() else 0))
    return out


def sun_product_ids(sun_html: str) -> list[str]:
    """Ids in sun.html's PRODUCTS literal, in order (read only; nobody edits PRODUCTS)."""
    m = re.search(r"const PRODUCTS = \[(.*?)\n\s*\];", sun_html, re.S)
    return re.findall(r'\[\s*"([^"]+)"\s*,', m.group(1)) if m else []


def text(ctx: Ctx, rel: str) -> str:
    return (ctx.root / rel).read_text(encoding="utf-8", errors="replace")


@check("link")
def check_links(ctx: Ctx) -> list[Finding]:
    out = []
    for page in ctx.pages:
        for line, raw in parse_page(text(ctx, page)).links:
            if "/releases/latest" in raw:
                out.append(Finding("FAIL", "link", page, line, raw,
                                   "hand out the /releases index, never /releases/latest"))
                continue
            path = url_path(page, raw)
            if path is not None and resolve(path, ctx.files) is None:
                out.append(Finding("FAIL", "link", page, line, raw,
                                   f"no tracked file for {path}{case_hint(path, ctx.files)}"))
    if "sitemap.xml" in ctx.files:
        body = text(ctx, "sitemap.xml")
        try:
            locs = [e.text or "" for e in ET.fromstring(body.encode()).iter(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        except ET.ParseError:
            locs = []
        for loc in locs:
            path = url_path("sitemap.xml", loc.strip())
            if path is not None and resolve(path, ctx.files) is None:
                out.append(Finding("FAIL", "link", "sitemap.xml", line_of(body, loc), loc,
                                   f"no tracked file for {path}{case_hint(path, ctx.files)}"))
    return out


@check("stub")
def check_stubs(ctx: Ctx) -> list[Finding]:
    out = []
    for page in ctx.pages:
        body = text(ctx, page)
        targets = redirect_targets(body)
        if not targets:
            continue
        target = targets[0]
        line = line_of(body, target)
        if len(set(targets)) > 1:
            out.append(Finding("FAIL", "stub", page, line, target,
                               "meta refresh and location.replace disagree: " + " vs ".join(sorted(set(targets)))))
        if "/releases/latest" in target:
            out.append(Finding("FAIL", "stub", page, line, target,
                               "hand out the /releases index, never /releases/latest"))
        path = url_path(page, target)
        if path is None:
            continue
        dest = resolve(path, ctx.files)
        if dest is None:
            out.append(Finding("FAIL", "stub", page, line, target,
                               f"redirect target is not a tracked page{case_hint(path, ctx.files)}"))
        elif dest == page:
            out.append(Finding("FAIL", "stub", page, line, target, "redirects to itself"))
        elif not dest.endswith(".html"):
            out.append(Finding("FAIL", "stub", page, line, target, f"redirect target {dest} is not a page"))
        else:
            bare = path.strip("/")
            if not path.endswith("/") and "." not in posixpath.basename(bare) \
                    and bare + ".html" in ctx.files and bare + "/index.html" in ctx.files:
                out.append(Finding("WARN", "stub", page, line, target,
                                   f"resolves to {dest} here; {bare}/index.html also exists, so the live "
                                   "answer depends on GitHub Pages' lookup order (WS-7 follows it live)"))
    return out


@check("json")
def check_json(ctx: Ctx) -> list[Finding]:
    out = []
    for rel in sorted(f for f in ctx.files if f.endswith(".json")):
        try:
            json.loads(text(ctx, rel))
        except ValueError as e:
            out.append(Finding("FAIL", "json", rel, getattr(e, "lineno", 0), "-", f"invalid JSON: {e}"))
    return out


@check("xml")
def check_xml(ctx: Ctx) -> list[Finding]:
    out = []
    for rel in sorted(f for f in ctx.files if f.endswith(".xml")):
        try:
            ET.fromstring((ctx.root / rel).read_bytes())
        except ET.ParseError as e:
            out.append(Finding("FAIL", "xml", rel, e.position[0], "-", f"invalid XML: {e}"))
    return out


@check("feed")
def check_feed(ctx: Ctx) -> list[Finding]:
    out = []
    for group, frozen in ((FROZEN_FEED, True), (HELIOGRAM_FEED, False)):
        if not frozen and not any(p in ctx.files for p in group):
            out.append(Finding("SKIP", "feed", group[0], 0, "-", "not tracked yet"))
            continue
        appcast, version = group
        for rel in group:
            if rel not in ctx.files:
                out.append(Finding("FAIL", "feed", rel, 0, "-",
                                   "update feed file is not tracked; installed apps poll this URL"
                                   if frozen else "feed is half present; both files must be tracked"))
        if appcast in ctx.files:
            body = text(ctx, appcast)
            try:
                encs = feed_enclosures(body)
            except ET.ParseError:
                encs = []   # the xml rule reports it
            for url, length in encs:
                path = url_path(appcast, url)
                if path is None:
                    continue
                rel = path.lstrip("/")
                if rel not in ctx.files:
                    out.append(Finding("FAIL", "feed", appcast, line_of(body, url), url,
                                       "enclosure is not tracked; signed update downloads would 404"))
                elif length and (ctx.root / rel).stat().st_size != length:
                    out.append(Finding("FAIL", "feed", appcast, line_of(body, url), url,
                                       f"enclosure length {length} != tracked file size {(ctx.root / rel).stat().st_size}"))
        if version in ctx.files:
            try:
                data = json.loads(text(ctx, version))
            except ValueError:
                continue    # the json rule reports it
            missing = [k for k in VERSION_JSON_KEYS if not isinstance(data, dict) or k not in data]
            if missing:
                out.append(Finding("FAIL", "feed", version, 1, "-",
                                   "version.json lost key(s) " + ", ".join(missing) + "; its shape is frozen"))
    return out


@check("size")
def check_size(ctx: Ctx) -> list[Finding]:
    allow = read_list(ctx.root, "size_allowlist.txt")
    out = []
    for rel in sorted(ctx.files):
        p = ctx.root / rel
        if not p.is_file() or p.stat().st_size <= SIZE_LIMIT_BYTES:
            continue
        if not any(fnmatch.fnmatchcase(rel, pat) for pat in allow):
            out.append(Finding("FAIL", "size", rel, 0, "-",
                               f"{p.stat().st_size} bytes is over {SIZE_LIMIT_BYTES}; "
                               "add it to tools/size_allowlist.txt only with Gilly's yes"))
    return out


@check("a11y")
def check_a11y(ctx: Ctx) -> list[Finding]:
    archived = read_list(ctx.root, "archived_pages.txt")
    out = []
    for page in ctx.pages:
        if page.startswith("partials/") or any(fnmatch.fnmatchcase(page, pat) for pat in archived):
            continue
        body = text(ctx, page)
        if "<html" not in body.lower() or redirect_targets(body):
            continue    # fragment or redirect stub
        tags = parse_page(body).tags
        html_tag = next((a for t, a, _ in tags if t == "html"), {})
        if not html_tag.get("lang"):
            out.append(Finding("WARN", "a11y", page, 1, "-", "<html> has no lang"))
        if not any(t == "main" or a.get("role") == "main" for t, a, _ in tags):
            out.append(Finding("WARN", "a11y", page, 0, "-", "no <main> landmark"))
        has_skip = 'data-include="header"' in body or any(
            t == "a" and "skip" in (a.get("class") or "") for t, a, _ in tags)
        if not has_skip:
            out.append(Finding("WARN", "a11y", page, 0, "-", "no skip link (and no shared header)"))
        for t, a, line in tags:
            if t == "img" and "alt" not in a:
                out.append(Finding("WARN", "a11y", page, line, a.get("src") or "-", "<img> has no alt"))
    return out


class _NavLinks(html.parser.HTMLParser):
    """(href, label) of the links in the first nav labelled "Primary"; the drop-down menu is skipped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list = []
        self._in_nav = False
        self._menu = 0          # div depth inside nav-drop__menu
        self._href = None
        self._label: list = []
        self._done = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self._done:
            return
        if tag == "nav" and a.get("aria-label") == "Primary":
            self._in_nav = True
        elif self._in_nav and tag == "div":
            if self._menu or "nav-drop__menu" in (a.get("class") or ""):
                self._menu += 1
        elif self._in_nav and tag == "a" and not self._menu:
            self._href, self._label = a.get("href") or "", []

    def handle_data(self, data):
        if self._href is not None:
            self._label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._label).split())))
            self._href = None
        elif tag == "div" and self._menu:
            self._menu -= 1
        elif tag == "nav" and self._in_nav:
            self._in_nav, self._done = False, True


def nav_links(html_text: str) -> list:
    p = _NavLinks()
    p.feed(html_text)
    p.close()
    return p.links


def parity_note(want: list, got: list) -> str:
    wh, gh = [h for h, _ in want], [h for h, _ in got]
    missing = [h for h in wh if h not in gh]
    extra = [h for h in gh if h not in wh]
    bits = ([f"missing {', '.join(missing)}"] if missing else []) + ([f"extra {', '.join(extra)}"] if extra else [])
    return "; ".join(bits) or "same links, different order or labels"


@check("parity")
def check_parity(ctx: Ctx) -> list[Finding]:
    """Warn-only (WS-10): the other copies of the nav against partials/header.html."""
    if "partials/header.html" not in ctx.files:
        return []
    want = nav_links(text(ctx, "partials/header.html"))
    out = []
    if "assets/site.js" in ctx.files:
        js = text(ctx, "assets/site.js")
        m = re.search(r"var HEADER_FALLBACK = (?:/\* bake:header-fallback \*/ )?'((?:[^'\\\n]|\\.)*)'", js)
        if m and nav_links(m.group(1)) != want:
            out.append(Finding("WARN", "parity", "assets/site.js", line_of(js, "var HEADER_FALLBACK"),
                               "HEADER_FALLBACK", "differs from partials/header.html: " + parity_note(want, nav_links(m.group(1)))))
        urls = re.findall(r"\bu: '([^']*)'", js)
        lacking = [h for h, _ in want if h not in urls]
        if urls and lacking:
            out.append(Finding("WARN", "parity", "assets/site.js", line_of(js, "var ITEMS"), "ITEMS",
                               "command palette has no entry for " + ", ".join(lacking)))
    for page in ctx.pages:
        body = text(ctx, page)
        m = re.search(r"<noscript>(.*?)</noscript>", body, re.S)
        if not m or 'aria-label="Primary"' not in m.group(1):
            continue
        got = nav_links(m.group(1))
        if got != want:
            out.append(Finding("WARN", "parity", page, line_of(body, "<noscript>"), "noscript",
                               "differs from partials/header.html: " + parity_note(want, got)))
    return out


def run_external(ctx: Ctx, rule: str, script: str, argv: list[str]) -> list[Finding]:
    if not (ctx.root / script).exists():
        return [Finding("SKIP", rule, script, 0, "-", "script not present yet")]
    if argv[-1] not in (ctx.root / script).read_text(encoding="utf-8", errors="replace"):
        # Never run a version that ignores the flag: the pre-WS-1 bump-assets.py
        # would rewrite pages (and .claude/worktrees/) instead of checking.
        return [Finding("SKIP", rule, script, 0, "-", f"script has no {argv[-1]} yet")]
    argv = [sys.executable if a == "python3" else a for a in argv]
    r = subprocess.run(argv, cwd=ctx.root, capture_output=True, text=True)
    if r.returncode == 0:
        return []
    out = []
    for ln in r.stdout.splitlines():
        parts = ln.split(None, 2)
        if len(parts) >= 2 and parts[0].isupper() and parts[0] != "WARN":
            path = parts[1].rstrip(":")
            out.append(Finding("FAIL", rule, path, 0, "-", parts[2] if len(parts) > 2 else ln))
    if not out:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["no output"]
        out.append(Finding("FAIL", rule, script, 0, "-", f"exit {r.returncode}: {tail[0]}"))
    return out


def load_known(root: pathlib.Path) -> set[tuple[str, str, str]]:
    known = set()
    for ln in read_list(root, "known_failures.txt"):
        parts = ln.split()
        if len(parts) >= 2:
            known.add((parts[0], parts[1], parts[2] if len(parts) > 2 else "-"))
    return known


def build_ctx(root: pathlib.Path) -> Ctx:
    files = list_files(root)
    pages = sorted(f for f in files if f.endswith(".html"))
    return Ctx(root=root, files=files, pages=pages)


def run(root: pathlib.Path, only: list[str] | None = None) -> tuple[int, list[Finding]]:
    ctx = build_ctx(root)
    findings: list[Finding] = []
    for fn in CHECKS:
        if not only or fn.rule in only:
            findings += fn(ctx)
    for rule, script, argv in EXTERNAL_CHECKS:
        if not only or rule in only:
            findings += run_external(ctx, rule, script, argv)
    known = load_known(root)
    findings = [f._replace(level="KNOWN") if f.level == "FAIL" and (f.rule, f.path, f.target) in known else f
                for f in findings]
    fails = sum(f.level == "FAIL" for f in findings)
    return (1 if fails else 0), findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="gilly.space site checks")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--only", nargs="+", action="extend", metavar="RULE")
    args = ap.parse_args(argv)
    code, findings = run(args.root.resolve(), args.only)
    for f in findings:
        print(f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}")
    c = collections.Counter(f.level for f in findings)
    print(f"check_site: {c['FAIL']} failures, {c['WARN']} warnings, {c['KNOWN']} known")
    return code



# ---- rule `contract` (WS-4): what the site reads from Sunback, Heliogram and Studio ----
import fnmatch, json, pathlib, re  # noqa: E401  (repeats are harmless)

CONTRACT_SUN = "contracts/sun-bucket.md"
CONTRACT_HELIOGRAM = "contracts/heliogram-publish.md"
CONTRACT_STUDIO = "contracts/studio-release-assets.md"
SUN_FIXTURES = "fixtures/sun/"
SUN_READERS = ("sun.html", "assets/sun.js")  # files whose m.<field> reads and BUCKET line are checked (WS-5)
STUDIO_PAGE = "heliofits-studio/index.html"
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$")
MANIFEST_FIELD_RE = re.compile(r"\bm\.([A-Za-z_]\w*)")


def contract_block(path: pathlib.Path, tag: str) -> list[str]:
    """Non-empty, stripped lines of the first fenced block opened with three backticks plus tag.

    Raises ValueError when the file has no closed block with that tag.
    """
    inside, out = False, []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not inside:
            inside = s == "```" + tag
        elif s.startswith("```"):
            return out
        elif s:
            out.append(s)
    raise ValueError(f"{path}: no closed ```{tag} block")


def _contract_missing(ctx, rel):
    # The real repo must carry every contract; a fixture tree (no .git) may omit some.
    level = "FAIL" if (ctx.root / ".git").exists() else "SKIP"
    return [Finding(level, "contract", rel, 0, "", "contract file not tracked")]


def _text(ctx, rel):
    return (ctx.root / rel).read_text(encoding="utf-8")


def check_sun_contract(ctx):
    if CONTRACT_SUN not in ctx.files:
        return _contract_missing(ctx, CONTRACT_SUN)
    doc = ctx.root / CONTRACT_SUN
    try:
        ids, fields, optional = (contract_block(doc, t) for t in ("ids", "fields", "optional"))
    except ValueError as e:
        return [Finding("FAIL", "contract", CONTRACT_SUN, 0, "", str(e))]
    if "sun.html" not in ctx.files:
        return [Finding("FAIL", "contract", "sun.html", 0, "", "sun.html not tracked")]
    out, known, sun = [], set(fields) | set(optional), _text(ctx, "sun.html")
    page_ids = sun_product_ids(sun)
    if ids != page_ids:
        out.append(Finding("FAIL", "contract", CONTRACT_SUN, 0, "ids",
                           f"ids block {ids} differs from sun.html PRODUCTS {page_ids}"))
    for src in SUN_READERS:
        if src not in ctx.files:
            continue
        for n, line in enumerate(_text(ctx, src).splitlines(), 1):
            for name in MANIFEST_FIELD_RE.findall(line):
                if name not in known:
                    out.append(Finding("FAIL", "contract", src, n, "m." + name,
                                       f"{src} reads m.{name}, which {CONTRACT_SUN} does not list"))
            if "/fixtures/" in line and 'location.hostname === "localhost"' not in line:
                out.append(Finding("FAIL", "contract", src, n, "BUCKET",
                                   "fixture path not gated on localhost"))
    for pid in ids:
        rel = f"{SUN_FIXTURES}manifest/{pid}.json"
        if rel not in ctx.files:
            out.append(Finding("FAIL", "contract", rel, 0, "", "fixture manifest missing"))
            continue
        try:
            m = json.loads(_text(ctx, rel))
        except ValueError as e:
            out.append(Finding("FAIL", "contract", rel, 0, "", f"not JSON: {e}"))
            continue
        for f in fields:
            if not (isinstance(m.get(f), str) and m[f]):
                out.append(Finding("FAIL", "contract", rel, 0, f, f"lacks field {f}"))
        for f in m:
            if f not in known:
                out.append(Finding("WARN", "contract", rel, 0, f,
                                   f"field {f} is not in the contract; add it to the optional block"))
        if isinstance(m.get("updated"), str) and not ISO_UTC_RE.match(m["updated"]):
            out.append(Finding("FAIL", "contract", rel, 0, "updated",
                               f"updated {m['updated']!r} is not ISO 8601"))
        for f in ("thumb", "img1k"):
            if isinstance(m.get(f), str) and m[f] and SUN_FIXTURES + m[f] not in ctx.files:
                out.append(Finding("FAIL", "contract", rel, 0, f,
                                   f"placeholder {SUN_FIXTURES}{m[f]} not tracked"))
    times = SUN_FIXTURES + "image_times.txt"
    if times not in ctx.files:
        out.append(Finding("FAIL", "contract", times, 0, "", "fixture missing"))
    elif not ISO_UTC_RE.match(_text(ctx, times).strip()):
        out.append(Finding("FAIL", "contract", times, 0, "", "not one ISO 8601 time"))
    return out


def check_heliogram_contract(ctx):
    if CONTRACT_HELIOGRAM not in ctx.files:
        return _contract_missing(ctx, CONTRACT_HELIOGRAM)
    doc = ctx.root / CONTRACT_HELIOGRAM
    try:
        frozen, writes = (contract_block(doc, t) for t in ("frozen", "writes"))
    except ValueError as e:
        return [Finding("FAIL", "contract", CONTRACT_HELIOGRAM, 0, "", str(e))]
    out = []
    for rel in FROZEN_FEED:
        if rel not in frozen:
            out.append(Finding("FAIL", "contract", CONTRACT_HELIOGRAM, 0, rel,
                               "FROZEN_FEED path missing from the frozen block"))
    for rel in frozen:
        if rel not in ctx.files:
            out.append(Finding("FAIL", "contract", rel, 0, "",
                               "frozen path not tracked (a Heliogram publish must not remove it)"))
    for rel in FROZEN_FEED + HELIOGRAM_FEED:
        if rel.endswith("version.json") and rel in ctx.files:
            try:
                data = json.loads(_text(ctx, rel))
            except ValueError as e:
                out.append(Finding("FAIL", "contract", rel, 0, "", f"not JSON: {e}"))
                continue
            lost = [k for k in VERSION_JSON_KEYS if k not in data]
            if lost:
                out.append(Finding("FAIL", "contract", rel, 0, ",".join(lost),
                                   "version.json lost keys " + ", ".join(lost)))
    if any(p.startswith("heliogram/") for p in ctx.files):
        for pattern in writes:
            if not any(fnmatch.fnmatchcase(p, pattern) for p in ctx.files):
                out.append(Finding("FAIL", "contract", pattern, 0, "",
                                   "publish.sh writes this, but no tracked file matches"))
    return out


STUDIO_PIN_RE = re.compile(r"HFStudio-(\d+(?:\.\d+)+)\.dmg")
PLATFORM_RE = re.compile(
    r"^\s*(\w+):\s*\{\s*confirmed:\s*(?:true|false),\s*asset:\s*/(.+?)/([a-z]*),", re.M)


def check_studio_contract(ctx):
    if CONTRACT_STUDIO not in ctx.files:
        return _contract_missing(ctx, CONTRACT_STUDIO)
    try:
        templates = contract_block(ctx.root / CONTRACT_STUDIO, "assets")
    except ValueError as e:
        return [Finding("FAIL", "contract", CONTRACT_STUDIO, 0, "", str(e))]
    if STUDIO_PAGE not in ctx.files:
        return [Finding("FAIL", "contract", STUDIO_PAGE, 0, "", "Studio page not tracked")]
    page = _text(ctx, STUDIO_PAGE)
    pin = STUDIO_PIN_RE.search(page)
    if not pin:
        return [Finding("FAIL", "contract", STUDIO_PAGE, 0, "", "no pinned HFStudio-<version>.dmg link")]
    ver, out = pin.group(1), []
    names = [t.replace("{v}", ver) for t in templates]
    for name in names:
        if f"/releases/download/v{ver}/{name}" not in page:
            out.append(Finding("FAIL", "contract", STUDIO_PAGE, 0, name,
                               f"no fallback link to v{ver}/{name}"))
    platforms = PLATFORM_RE.findall(page)
    if not platforms:
        out.append(Finding("FAIL", "contract", STUDIO_PAGE, 0, "PLATFORMS", "PLATFORMS not found"))
    for pid, src, flags in platforms:
        rx = re.compile(src, re.I if "i" in flags else 0)
        hits = [n for n in names if rx.search(n)]
        if len(hits) != 1:
            out.append(Finding("FAIL", "contract", STUDIO_PAGE, 0, "PLATFORMS." + pid,
                               f"PLATFORMS.{pid} matches {len(hits)} assets {hits}; expected exactly 1"))
    return out


@check("contract")
def check_contracts(ctx):
    return check_sun_contract(ctx) + check_heliogram_contract(ctx) + check_studio_contract(ctx)


if __name__ == "__main__":
    sys.exit(main())
