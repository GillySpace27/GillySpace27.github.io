#!/usr/bin/env python3
"""Live-site watch for gilly.space (WS-7): read-only probes of public URLs.

python3 tools/watch.py [--base URL] [--probe NAME ...] [--json] [--issue]
                       [--expect PATH=FINAL ...] [--root PATH]

Probes: shortlinks, feeds, sun, studio, worker. Exit 0 when nothing FAILs,
1 otherwise. Only GET and HEAD reach the site, the bucket, the Worker and the
GitHub releases API. With --issue (meant for Actions) it creates, comments on,
reopens or closes the one issue titled "Live-site watch"; it never deletes.
No visitor telemetry.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402  (WS-2 parsers; WS-4 contracts)

SITE_ORIGIN = "https://gilly.space"
USER_AGENT = "gilly.space-live-site-watch/1 (read-only)"
# Expected final path per short link, read from the tree at c272b93.
SHORT_LINKS = {
    "/hfs": "/heliofits-studio/",          # hfs/index.html:9,22
    "/hfstudio": "/heliofits-studio/",     # hfstudio/index.html:9,22
    "/punchstudio": "/heliofits-studio/",  # punchstudio/index.html:9,22
    "/jhv": "/heliofits-studio/",          # jhv/index.html:9,22 (owner question q6 open)
    "/heliofits": "/heliofits/",
    "/shop": "/shop",                      # shop/index.html:7-8 redirects to /shop; first live run records what Pages does
    "/heliograph/": "/heliograph/",
    "/heliogram/": "/heliogram/",
}
TRACKED_ONLY = {"/heliogram/": "heliogram/index.html"}   # probed once the page is tracked
KNOWN_404 = ("/HFS", "/HFStudio", "/JHV", "/HelioFITS")  # owner decision; never expected to pass
LEGACY_FEED = "heliograph/appcast.xml"                   # frozen: compiled into shipped apps
NEW_FEED = "heliogram/appcast.xml"
SUN_BUCKET = "https://the-sun-now.s3.us-east-2.amazonaws.com/"
SUN_STALE_HOURS = 3                                      # estimated; tune after a week of runs
STUDIO_API = "https://api.github.com/repos/GillySpace27/HelioFITS-Studio/releases?per_page=1"
STUDIO_PAGE_PATH = "/heliofits-studio/"
WORKER_URL = "https://enso-impressions.gilly-22d.workers.dev"   # enso/index.html:1838
WORKER_HEALTH_PREFIX = "enso-impressions worker is alive"       # worker/worker.js:115
WORKER_STATUS_KEYS = {"model", "cacheEnabled", "today", "aiCallsToday"}
ISSUE_TITLE = "Live-site watch"
ISSUE_LABEL = "live-site-watch"
GITHUB_API = "https://api.github.com"
LOOP = -1

FollowResult = collections.namedtuple("FollowResult", "final_url status length hops title")
Result = collections.namedtuple("Result", "level probe target msg")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_FINGERPRINT = re.compile(r"<!-- watch-fingerprint: ([0-9a-f]{64}) -->")


def fetch(url, method="GET", headers=None, timeout=20):
    """(status, final_url, body, headers); urllib follows HTTP redirects. Status 0: nothing answered."""
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.geturl() or url, e.read() or b"", e.headers or {}
    except (urllib.error.URLError, OSError) as e:
        return 0, url, str(getattr(e, "reason", e)).encode(), {}


def _to_base(url, base):
    if base != SITE_ORIGIN and url.startswith(SITE_ORIGIN + "/"):
        return base + url[len(SITE_ORIGIN):]
    return url


def follow(url, max_hops=5, base=SITE_ORIGIN):
    """Follow HTTP redirects, then static redirect pages, to the page a visitor ends on."""
    seen, hops = set(), 0
    while True:
        status, final, body, _ = fetch(url)
        text = body.decode("utf-8", "replace")
        m = _TITLE.search(text)
        title = html.unescape(m.group(1)).strip() if m else ""
        target = check_site.parse_redirect_target(text) if status == 200 else None
        if not target:
            return FollowResult(final, status, len(body), hops, title)
        seen.update((url, final))
        nxt = _to_base(urllib.parse.urljoin(final, html.unescape(target)), base)
        hops += 1
        if nxt in seen or hops > max_hops:
            return FollowResult(nxt, LOOP, len(body), hops, title)
        url = nxt


def _bare(url):
    return url.split("#", 1)[0].split("?", 1)[0]


def short_link_verdict(path, expected, res, base):
    want = base + expected
    if res.status == LOOP:
        return Result("FAIL", "shortlinks", path, f"redirect loop or too many hops ({res.hops}), last {res.final_url}")
    if res.status != 200:
        return Result("FAIL", "shortlinks", path, f"lands on HTTP {res.status} at {res.final_url}")
    if _bare(res.final_url) != want:
        return Result("FAIL", "shortlinks", path, f"lands on {res.final_url}, expected {want}")
    return Result("PASS", "shortlinks", path, f"{res.hops} hop(s) to {res.final_url} ({res.title})")


def probe_shortlinks(base, root):
    files = check_site.list_files(root)
    out = []
    for path, expected in SHORT_LINKS.items():
        need = TRACKED_ONLY.get(path)
        if need and need not in files:
            out.append(Result("SKIP", "shortlinks", path, f"{need} not tracked yet"))
            continue
        out.append(short_link_verdict(path, expected, follow(base + path, base=base), base))
    for path in KNOWN_404:
        res = follow(base + path, base=base)
        out.append(Result("INFO", "shortlinks", path,
                          f"cased link, owner decision (not tracked): HTTP {res.status} at {res.final_url}"))
    return out


def _feed(base, rel):
    target = "/" + rel
    status, _, body, _ = fetch(f"{base}/{rel}?cb={time.time_ns()}")
    if status != 200:
        msg = f"HTTP {status}"
        if rel == LEGACY_FEED:
            msg += (": the FROZEN legacy feed is gone; shipped Heliograph apps can no longer update."
                    " Restore heliograph/appcast.xml on master from git history")
        return Result("FAIL", "feeds", target, msg)
    try:
        tree = ET.fromstring(body)
        encs = check_site.feed_enclosures(body.decode("utf-8"))
    except (ET.ParseError, UnicodeDecodeError, ValueError) as e:
        return Result("FAIL", "feeds", target, f"not a readable appcast: {e}")
    if not encs:
        return Result("FAIL", "feeds", target, "no enclosure")
    # Newest first, as Sparkle's tools write it (heliograph/appcast.xml:6-30 has one item).
    enc_url, length = encs[0]
    sig = next(tree.iter("enclosure")).get(f"{{{check_site.SPARKLE_NS}}}edSignature")
    if not sig:
        return Result("FAIL", "feeds", target, f"newest enclosure {enc_url} has no sparkle:edSignature")
    hs, _, _, hh = fetch(_to_base(enc_url, base), method="HEAD")
    if hs != 200:
        return Result("FAIL", "feeds", target, f"newest enclosure {enc_url}: HTTP {hs}")
    got = hh.get("Content-Length")
    if got is None:
        return Result("WARN", "feeds", target, f"no Content-Length on HEAD {enc_url}; size not compared")
    if int(got) != length:
        return Result("FAIL", "feeds", target,
                      f"newest enclosure {enc_url}: appcast length {length}, served Content-Length {got}")
    return Result("PASS", "feeds", target, f"{enc_url} serves {got} bytes, signature present")


def _version_json(base, rel):
    target = "/" + rel
    status, _, body, _ = fetch(f"{base}/{rel}?cb={time.time_ns()}")
    if status != 200:
        return Result("FAIL", "feeds", target, f"HTTP {status}")
    try:
        data = json.loads(body)
    except ValueError:
        return Result("FAIL", "feeds", target, "not JSON")
    missing = [k for k in check_site.VERSION_JSON_KEYS if not isinstance(data, dict) or k not in data]
    if missing:
        return Result("FAIL", "feeds", target, f"missing key(s) {', '.join(missing)} (shape is frozen)")
    return Result("PASS", "feeds", target, f"version {data['version']} build {data['build']}")


def probe_feeds(base, root):
    files = check_site.list_files(root)
    out = []
    for rel in (LEGACY_FEED, NEW_FEED):
        if rel == NEW_FEED and rel not in files:
            out.append(Result("SKIP", "feeds", "/" + rel, "not tracked yet"))
            continue
        out.append(_feed(base, rel))
        out.append(_version_json(base, rel.replace("appcast.xml", "version.json")))
    return out


def parse_utc(s):
    t = dt.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def probe_sun(base, root, bucket=SUN_BUCKET, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    limit = dt.timedelta(hours=SUN_STALE_HOURS)
    doc = root / check_site.CONTRACT_SUN
    ids, fields = check_site.contract_block(doc, "ids"), check_site.contract_block(doc, "fields")
    cb = f"?cb={time.time_ns()}"

    def age(target, stamp):
        try:
            t = parse_utc(stamp)
        except ValueError:
            return Result("FAIL", "sun", target, f"unparseable time {stamp!r}")
        hours = (now - t).total_seconds() / 3600
        if hours > SUN_STALE_HOURS:
            return Result("FAIL", "sun", target,
                          f"stale: {stamp} is {hours:.1f} h old (limit {SUN_STALE_HOURS} h, estimated)")
        return Result("PASS", "sun", target, f"{stamp} ({hours * 60:.0f} min old)")

    out = []
    status, _, body, _ = fetch(bucket + "image_times.txt" + cb)
    out.append(age("image_times.txt", body.decode("utf-8", "replace")) if status == 200
               else Result("FAIL", "sun", "image_times.txt", f"HTTP {status}"))
    for pid in ids:
        key = f"manifest/{pid}.json"
        status, _, body, _ = fetch(bucket + key + cb)
        if status != 200:
            out.append(Result("FAIL", "sun", key, f"HTTP {status}"))
            continue
        try:
            m = json.loads(body)
        except ValueError:
            out.append(Result("FAIL", "sun", key, "not JSON"))
            continue
        missing = [f for f in fields if f not in m]
        if missing:
            out.append(Result("FAIL", "sun", key, f"missing contract field(s) {', '.join(missing)}"))
            continue
        out.append(age(key, str(m["updated"])))
    return out


def studio_verdict(pinned, newest_tag):
    newest = newest_tag[1:] if newest_tag.startswith("v") else newest_tag
    if pinned == newest:
        return Result("PASS", "studio", STUDIO_PAGE_PATH, f"fallback pin {pinned} equals newest release {newest_tag}")
    return Result("FAIL", "studio", STUDIO_PAGE_PATH,
                  f"fallback pin {pinned} differs from newest release {newest_tag}:"
                  f" run python3 tools/pin_studio_fallback.py {newest} --from-github (WS-8)")


def probe_studio(base, root):
    status, _, body, _ = fetch(f"{base}{STUDIO_PAGE_PATH}?cb={time.time_ns()}")
    if status != 200:
        return [Result("FAIL", "studio", STUDIO_PAGE_PATH, f"HTTP {status}")]
    pin = check_site.STUDIO_PIN_RE.search(body.decode("utf-8", "replace"))
    if not pin:
        return [Result("FAIL", "studio", STUDIO_PAGE_PATH, "no pinned HFStudio-<version>.dmg link on the live page")]
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    s, _, b, _ = fetch(STUDIO_API, headers=headers)
    try:
        rels = json.loads(b) if s == 200 else None
    except ValueError:
        rels = None
    if not rels:
        return [Result("WARN", "studio", STUDIO_PAGE_PATH, f"GitHub API HTTP {s}; pin {pin.group(1)} not compared")]
    return [studio_verdict(pin.group(1), rels[0]["tag_name"])]


def worker_verdict(status, body):
    text = body.decode("utf-8", "replace")
    if status != 200:
        return Result("FAIL", "worker", "/status", f"HTTP {status}")
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict) and WORKER_STATUS_KEYS <= data.keys():
        return Result("PASS", "worker", "/status", f"{data['aiCallsToday']} AI calls on {data['today']}")
    if text.startswith(WORKER_HEALTH_PREFIX):
        return Result("PASS", "worker", "/status", "health string (no /status yet; WS-6)")
    return Result("FAIL", "worker", "/status", f"unexpected body {text[:80]!r}")


def probe_worker(base, root):
    status, _, body, _ = fetch(WORKER_URL + "/status")
    return [worker_verdict(status, body)]


PROBES = {"shortlinks": probe_shortlinks, "feeds": probe_feeds, "sun": probe_sun,
          "studio": probe_studio, "worker": probe_worker}


def run_probes(base, root, names=None):
    out = []
    for name in names or PROBES:
        try:
            out.extend(PROBES[name](base, root))
        except Exception as e:  # a crashed probe is a failure, never a silent pass
            out.append(Result("FAIL", name, "-", f"probe crashed: {e!r}"))
    return out


def format_report(results):
    lines = [f"{r.level} {r.probe} {r.target} :: {r.msg}" for r in results]
    fails = sum(r.level == "FAIL" for r in results)
    warns = sum(r.level == "WARN" for r in results)
    lines.append(f"watch: {fails} failures, {warns} warnings")
    return "\n".join(lines)


def gh(method, path, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(GITHUB_API + path, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def _find_issue(repo, token):
    for page in range(1, 11):
        items = gh("GET", f"/repos/{repo}/issues?state=all&per_page=100&page={page}", token)
        for it in items:
            if it.get("title") == ISSUE_TITLE and "pull_request" not in it:
                return it
        if len(items) < 100:
            return None
    return None


def sync_issue(results, repo, token, run_url=""):
    """Keep one issue: create, comment, reopen or close it. Never delete."""
    fails = [r for r in results if r.level == "FAIL"]
    issue = _find_issue(repo, token)
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    if not fails:
        if issue and issue["state"] == "open":
            n = issue["number"]
            gh("POST", f"/repos/{repo}/issues/{n}/comments", token,
               {"body": f"Every probe passes at {now}. Closing. {run_url}".strip()})
            gh("PATCH", f"/repos/{repo}/issues/{n}", token, {"state": "closed", "state_reason": "completed"})
            return "closed"
        return "none"
    fp = hashlib.sha256("\n".join(sorted(f"{r.probe} {r.target}" for r in fails)).encode()).hexdigest()
    failing = "\n".join(f"{r.level} {r.probe} {r.target} :: {r.msg}" for r in fails)
    body = (f"Kept current by `.github/workflows/watch.yml` (WS-7): read-only probes of the public site."
            f" Closed, never deleted, when every probe passes.\n\nLatest run: {now} {run_url}\n\n"
            f"```text\n{format_report(results)}\n```\n\n<!-- watch-fingerprint: {fp} -->\n")
    if issue is None:
        gh("POST", f"/repos/{repo}/issues", token, {"title": ISSUE_TITLE, "body": body, "labels": [ISSUE_LABEL]})
        return "created"
    n = issue["number"]
    old = _FINGERPRINT.search(issue.get("body") or "")
    if issue["state"] == "closed":
        gh("PATCH", f"/repos/{repo}/issues/{n}", token, {"state": "open", "body": body})
        gh("POST", f"/repos/{repo}/issues/{n}/comments", token,
           {"body": f"Reopened at {now}: probes fail again.\n\n```text\n{failing}\n```"})
        return "reopened"
    gh("PATCH", f"/repos/{repo}/issues/{n}", token, {"body": body})
    if not old or old.group(1) != fp:
        gh("POST", f"/repos/{repo}/issues/{n}/comments", token,
           {"body": f"Failures changed at {now}.\n\n```text\n{failing}\n```"})
        return "commented"
    return "updated"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only live-site watch for gilly.space (WS-7).")
    ap.add_argument("--base", default=SITE_ORIGIN)
    ap.add_argument("--probe", nargs="+", choices=sorted(PROBES))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--issue", action="store_true",
                    help="sync the one 'Live-site watch' issue (needs GITHUB_TOKEN, GITHUB_REPOSITORY)")
    ap.add_argument("--expect", action="append", default=[], metavar="PATH=FINAL",
                    help="override one SHORT_LINKS expectation (used to prove the issue opens)")
    ap.add_argument("--root", type=pathlib.Path, default=TOOLS.parent)
    a = ap.parse_args(argv)
    for pair in a.expect:
        path, _, final = pair.partition("=")
        if not path or not final:
            ap.error(f"--expect needs PATH=FINAL, got {pair!r}")
        SHORT_LINKS[path] = final
    results = run_probes(a.base.rstrip("/"), a.root, a.probe)
    print(json.dumps([r._asdict() for r in results], indent=1) if a.json else format_report(results))
    if a.issue:
        token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
        if not token or not repo:
            print("watch: --issue needs GITHUB_TOKEN and GITHUB_REPOSITORY", file=sys.stderr)
            return 2
        run_id = os.environ.get("GITHUB_RUN_ID")
        run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run_id}" if run_id else ""
        print("issue:", sync_issue(results, repo, token, run_url))
    return 1 if any(r.level == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
