"""Tests for tools/site_status.py (suite SU-5).

Run: python3 -m unittest discover -s tools/tests -p 'test_site_status.py'
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import site_status as ss  # noqa: E402

NOW = datetime.datetime(2026, 10, 1, 18, 0, tzinfo=datetime.timezone.utc)


class Verdict(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(ss.verdict(0, "check_site: 0 failures, 2 warnings, 1 known\n"),
                         (True, "0 failures, 2 warnings, 1 known"))

    def test_fail_names_the_first_failure(self):
        done, note = ss.verdict(1, "FAIL link about.html:3 /x/ :: missing\n"
                                   "check_site: 1 failures, 0 warnings, 0 known\n")
        self.assertFalse(done)
        self.assertIn("first: FAIL link about.html:3", note)

    def test_online_not_landed_is_unchecked(self):
        self.assertEqual(ss.verdict(2, "usage: check_site.py [-h]\n"
                                       "check_site.py: error: unrecognized arguments: --online\n"),
                         (None, "--online not available yet (SU-10)"))

    def test_missing_script_is_unchecked(self):
        self.assertIsNone(ss.verdict(None, "tools/check_site.py missing (WS-2 not landed)")[0])


class Snapshot(unittest.TestCase):
    def test_incomplete_state_counts_less_than_total(self):
        snap = ss.snapshot({"offline": (False, "1 failures, 0 warnings, 0 known"),
                            "online": (None, "--online not available yet (SU-10)")}, NOW)
        self.assertEqual((snap["complete"], snap["total"], snap["external_state"]), (0, 2, "FAIL"))
        self.assertTrue(snap["milestones"][1]["note"].startswith("UNCHECKED: "))

    def test_snapshot_has_the_orrery_shape(self):
        snap = ss.snapshot({"offline": (True, "ok"), "online": (True, "ok")}, NOW)
        self.assertEqual(set(snap), {"name", "title", "checked_at", "complete", "total", "next",
                                     "external_state", "external_label", "milestones"})
        self.assertEqual((snap["name"], snap["complete"], snap["next"]), ("site-gilly-space", 2, None))


if __name__ == "__main__":
    unittest.main()
