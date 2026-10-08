"""Tests for tools/watch.py and tools/verify_deploy.py.

Offline: a local http.server serves WS-2's fixture trees. Like GitHub Pages, it
answers a directory requested without a trailing slash with a 301.
Run: python3 -m unittest discover -s tools/tests -p 'test_watch.py'
"""
from __future__ import annotations

import contextlib
import datetime as dt
import functools
import http.server
import io
import pathlib
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.parse

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import watch  # noqa: E402

FIX = TOOLS / "tests" / "fixtures"
REPO = TOOLS.parent


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextlib.contextmanager
def serve(directory):
    handler = functools.partial(_Quiet, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


class FollowTests(unittest.TestCase):
    def verdict(self, tree, path, expected):
        with serve(tree) as base:
            res = watch.follow(base + path, base=base)
            return watch.short_link_verdict(path, expected, res, base), res

    def test_stub_lands_on_its_page(self):
        v, res = self.verdict(FIX / "ok-site", "/jhv", "/Research.html")
        self.assertEqual(v.level, "PASS", v)
        self.assertEqual((res.status, res.hops, res.title), (200, 1, "Research"))

    def test_stub_to_nowhere_fails(self):
        v, _ = self.verdict(FIX / "stub-to-nowhere", "/hfs", "/heliofits-studio/")
        self.assertEqual(v.level, "FAIL", v)
        self.assertIn("HTTP 404", v.msg)

    def test_wrong_expected_path_fails(self):
        v, _ = self.verdict(FIX / "ok-site", "/jhv", "/heliofits-studio/")
        self.assertEqual(v.level, "FAIL", v)
        self.assertIn("expected", v.msg)

    def test_redirect_loop_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "shop").mkdir()
            (pathlib.Path(tmp) / "shop" / "index.html").write_text(
                '<meta http-equiv="refresh" content="0; url=/shop">\n')
            v, _ = self.verdict(tmp, "/shop", "/shop")
        self.assertEqual(v.level, "FAIL", v)
        self.assertIn("loop", v.msg)

    def test_stub_to_empty_page_fails(self):
        v, res = self.verdict(FIX / "stub-to-empty-page", "/hfs", "/heliofits-studio/")
        self.assertEqual(res.status, 200)        # what a status-only check accepts
        self.assertEqual(v.level, "FAIL", v)
        self.assertIn("empty page", v.msg)

    def test_expectations_match_the_tracked_stubs(self):
        # A stub's meta refresh is where the live link lands; the watch must expect it.
        for path, expected in watch.SHORT_LINKS.items():
            stub = REPO / path.strip("/") / "index.html"
            m = re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', stub.read_text()) if stub.exists() else None
            if m:
                with self.subTest(path=path):
                    self.assertEqual(urllib.parse.urlsplit(m.group(1)).path, expected)


class FeedTests(unittest.TestCase):
    def feeds(self, tree):
        with serve(tree) as base:
            return {r.target: r for r in watch.probe_feeds(base, pathlib.Path(tree))}

    def test_ok_feed_passes_and_new_feed_skips_until_tracked(self):
        r = self.feeds(FIX / "ok-site")
        self.assertEqual(r["/heliograph/appcast.xml"].level, "PASS", r)
        self.assertEqual(r["/heliograph/version.json"].level, "PASS", r)
        self.assertEqual(r["/heliogram/appcast.xml"].level, "SKIP", r)

    def test_missing_legacy_feed_raises_the_alert(self):
        r = self.feeds(FIX / "no-legacy-appcast")["/heliograph/appcast.xml"]
        self.assertEqual(r.level, "FAIL", r)
        self.assertIn("FROZEN", r.msg)

    def test_missing_enclosure_fails(self):
        r = self.feeds(FIX / "missing-enclosure")["/heliograph/appcast.xml"]
        self.assertEqual(r.level, "FAIL", r)
        self.assertIn("HTTP 404", r.msg)

    def test_enclosure_length_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIX / "ok-site", tmp, dirs_exist_ok=True)
            (pathlib.Path(tmp) / "heliograph" / "App-1.0.dmg").write_bytes(b"longer\n")
            r = self.feeds(tmp)["/heliograph/appcast.xml"]
        self.assertEqual(r.level, "FAIL", r)
        self.assertIn("Content-Length 7", r.msg)


class SunTests(unittest.TestCase):
    def test_fresh_then_stale(self):
        stamp = (REPO / "fixtures" / "sun" / "image_times.txt").read_text().strip()
        t0 = watch.parse_utc(stamp)
        with serve(REPO) as base:
            bucket = base + "/fixtures/sun/"
            fresh = watch.probe_sun(base, REPO, bucket=bucket, now=t0 + dt.timedelta(minutes=30))
            stale = watch.probe_sun(base, REPO, bucket=bucket,
                                    now=t0 + dt.timedelta(hours=watch.SUN_STALE_HOURS + 1))
        self.assertEqual(len(fresh), 13, fresh)          # image_times.txt + 12 manifests
        self.assertEqual(fresh[0].level, "PASS", fresh[0])
        self.assertFalse([r for r in fresh if "missing contract field" in r.msg], fresh)
        self.assertEqual(stale[0].level, "FAIL", stale[0])
        self.assertIn("stale", stale[0].msg)


class VerdictTests(unittest.TestCase):
    def test_studio_pin(self):
        self.assertEqual(watch.studio_verdict("0.8.3", "v0.8.3").level, "PASS")
        v = watch.studio_verdict("0.8.2", "v0.8.3")
        self.assertEqual(v.level, "FAIL")
        self.assertIn("pin_studio_fallback.py 0.8.3", v.msg)

    def test_worker(self):
        ok = b'{"model":"m","cacheEnabled":true,"today":"2026-10-01","aiCallsToday":3}'
        self.assertEqual(watch.worker_verdict(200, ok).level, "PASS")
        health = watch.WORKER_HEALTH_PREFIX.encode() + b" (Workers AI / Llama 4 Scout / one-line evocation)"
        self.assertEqual(watch.worker_verdict(200, health).level, "PASS")
        self.assertEqual(watch.worker_verdict(500, b"").level, "FAIL")
        self.assertEqual(watch.worker_verdict(200, b"<html>").level, "FAIL")


class IssueTests(unittest.TestCase):
    """sync_issue against a fake GitHub: one issue, created, commented, closed, never deleted."""

    def setUp(self):
        self.calls, self.issue = [], None
        self.real_gh = watch.gh

        def fake(method, path, token, payload=None):
            self.calls.append((method, path, payload))
            if method == "GET":
                return [self.issue] if self.issue else []
            if method == "POST" and path.endswith("/issues"):
                self.issue = {"number": 7, "title": payload["title"], "state": "open", "body": payload["body"]}
                return self.issue
            if method == "PATCH":
                self.issue.update(payload)
                return self.issue
            return {}
        watch.gh = fake

    def tearDown(self):
        watch.gh = self.real_gh

    def test_open_comment_close(self):
        bad = [watch.Result("FAIL", "shortlinks", "/hfs", "lands on HTTP 404")]
        good = [watch.Result("PASS", "shortlinks", "/hfs", "ok")]
        self.assertEqual(watch.sync_issue(bad, "o/r", "t"), "created")
        self.assertEqual(self.issue["title"], "Live-site watch")
        self.assertEqual(watch.sync_issue(bad, "o/r", "t"), "updated")
        worse = bad + [watch.Result("FAIL", "worker", "/status", "HTTP 500")]
        self.assertEqual(watch.sync_issue(worse, "o/r", "t"), "commented")
        self.assertEqual(watch.sync_issue(good, "o/r", "t"), "closed")
        self.assertEqual(self.issue["state"], "closed")
        self.assertEqual(watch.sync_issue(bad, "o/r", "t"), "reopened")
        self.assertFalse([c for c in self.calls if c[0] == "DELETE"])


class VerifyDeployTests(unittest.TestCase):
    def test_converged_and_not_converged(self):
        import verify_deploy
        with tempfile.TemporaryDirectory() as live, tempfile.TemporaryDirectory() as co:
            for d in (live, co):
                (pathlib.Path(d) / "a").mkdir()
                (pathlib.Path(d) / "a" / "index.html").write_text("<title>A</title>same\n")
            (pathlib.Path(co) / "b.css").write_text("new\n")
            (pathlib.Path(live) / "b.css").write_text("old\n")
            with serve(live) as base:
                self.assertEqual(verify_deploy.pending(base, pathlib.Path(co), ["a/index.html"]), [])
                self.assertEqual(verify_deploy.pending(base, pathlib.Path(co), ["b.css"]), ["b.css (HTTP 200)"])
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = verify_deploy.main(["--base", base, "--root", co, "--paths", "b.css",
                                               "--timeout", "0"])
        self.assertEqual(code, 3)
        self.assertIn("UNCHECKED: live site did not converge", out.getvalue())

    def test_live_url(self):
        import verify_deploy
        self.assertEqual(verify_deploy.live_url("https://x", "index.html"), "https://x/")
        self.assertEqual(verify_deploy.live_url("https://x", "sun/index.html"), "https://x/sun/")
        self.assertEqual(verify_deploy.live_url("https://x", "sun.html"), "https://x/sun.html")


class WorkflowTests(unittest.TestCase):
    def test_watch_yml_is_scheduled_and_read_only(self):
        y = (REPO / ".github" / "workflows" / "watch.yml").read_text()
        for need in ('cron: "17 */6 * * *"', "workflow_dispatch:", "page_build:", "issues: write",
                     "contents: read", "python3 tools/watch.py --issue", "python3 tools/verify_deploy.py"):
            self.assertIn(need, y)
        for never in ("contents: write", "pages: write", "DELETE", "git push"):
            self.assertNotIn(never, y)


if __name__ == "__main__":
    unittest.main()
