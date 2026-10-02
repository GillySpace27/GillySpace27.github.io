"""Checks on the workflow files SU-10 owns or extends (Website). Run:
python3 -m unittest discover -s tools/tests -p 'test_workflows_su10.py' -v
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


class Workflows(unittest.TestCase):
    def read(self, name: str) -> str:
        return (WF / name).read_text(encoding="utf-8")

    def test_check_yml_has_the_em_dash_job(self):
        wf = self.read("check.yml")
        for needle in ("  em-dash:", "fetch-depth: 0", "heliosoftware/spec/tools/no_em_dash.py --base"):
            self.assertIn(needle, wf)

    def test_site_checks_runs_the_live_check_daily_and_only_that(self):
        wf = self.read("site-checks.yml")
        for needle in ("name: site-checks", "schedule:", 'cron: "23 6 * * *"', "workflow_dispatch:",
                       "contents: read", "python3 tools/check_site.py --online"):
            self.assertIn(needle, wf)
        for banned in ("pull_request", "push:", "secrets."):
            self.assertNotIn(banned, wf)

    def test_every_action_is_pinned_to_a_commit(self):
        bad = []
        for p in sorted(WF.glob("*.yml")):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                m = re.search(r"uses:\s*([\w./-]+)@(\S+)", line)
                if m and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)):
                    bad.append(f"{p.name}:{n} {m.group(1)}@{m.group(2)}")
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
