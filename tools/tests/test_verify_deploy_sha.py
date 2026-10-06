"""WS-9: tools/verify_deploy.py --expect-sha polls build.json
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

Offline: a local http.server stands in for Pages; the watch probes are mocked.
"""
from __future__ import annotations

import contextlib
import functools
import http.server
import importlib
import io
import json
import pathlib
import sys
import tempfile
import threading
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

A = "a" * 40
B = "b" * 40


def vd():
    return importlib.import_module("verify_deploy")


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


class ShaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.live = pathlib.Path(self._tmp.name)

    def put(self, commit):
        (self.live / "build.json").write_text(json.dumps(
            {"commit": commit, "ref": commit, "stamp": "202610011200", "built_utc": "2026-10-01T12:00:00Z"}))

    def run_main(self, base, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = vd().main(["--base", base, "--root", str(self.live), *args])
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_live_commit_reads_build_json(self):
        self.put(A)
        with serve(self.live) as base:
            self.assertEqual(vd().live_commit(base), A)

    def test_live_commit_is_none_when_missing(self):
        with serve(self.live) as base:
            self.assertIsNone(vd().live_commit(base))

    def test_sha_pending(self):
        self.put(A)
        with serve(self.live) as base:
            v = vd()
            self.assertEqual(v.sha_pending(base, None), [])
            self.assertEqual(v.sha_pending(base, A), [])
            self.assertEqual(v.sha_pending(base, A[:7]), [])
            self.assertEqual(v.sha_pending(base, B), ["build.json commit aaaaaaaaaaaa != bbbbbbbbbbbb"])
        empty = pathlib.Path(self._tmp.name) / "empty"
        empty.mkdir()
        with serve(empty) as base:
            self.assertEqual(vd().sha_pending(base, B), ["build.json unreadable, wanted commit bbbbbbbbbbbb"])

    def test_main_mismatch_is_unchecked(self):
        self.put(A)
        with serve(self.live) as base:
            code, out, _ = self.run_main(base, "--expect-sha", B, "--timeout", "0")
        self.assertEqual(code, 3)
        self.assertIn("UNCHECKED: live site did not converge within 0 s: "
                      "build.json commit aaaaaaaaaaaa != bbbbbbbbbbbb", out)

    def test_main_match_passes_when_probes_pass(self):
        self.put(A)
        with serve(self.live) as base, mock.patch.object(vd().watch, "run_probes", return_value=[]):
            code, out, _ = self.run_main(base, "--expect-sha", A.upper(), "--timeout", "0")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("PASS: "), out)
        self.assertIn("build.json aaaaaaaaaaaa", out)

    def test_main_probe_failure_is_fail_not_pass(self):
        self.put(A)
        bad = [vd().watch.Result("FAIL", "studio", "/heliofits-studio/", "boom")]
        with serve(self.live) as base, \
                mock.patch.object(vd().watch, "run_probes", return_value=bad), \
                mock.patch.object(vd().watch, "format_report", return_value="FAIL studio /heliofits-studio/ :: boom"):
            code, out, _ = self.run_main(base, "--expect-sha", A, "--timeout", "0")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: 1 probe result(s) failed after", out)

    def test_main_needs_paths_or_sha(self):
        code, _, err = self.run_main("http://127.0.0.1:9")
        self.assertEqual(code, 2)
        self.assertIn("give --paths, --expect-sha or both", err)

    def test_main_rejects_a_short_sha(self):
        code, _, err = self.run_main("http://127.0.0.1:9", "--expect-sha", "abc12")
        self.assertEqual(code, 2)
        self.assertIn("--expect-sha must be 7 to 40 hex digits", err)


if __name__ == "__main__":
    unittest.main()
