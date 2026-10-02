"""WS-9: structure of .github/workflows/pages.yml. Text checks only (no YAML library,
no network); the live behaviour is rehearsed in Task 7
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
WF = REPO / ".github" / "workflows" / "pages.yml"


def read() -> str:
    return WF.read_text(encoding="utf-8")


def jobs(text: str) -> dict:
    body = text.split("\njobs:\n", 1)[1]
    names = re.findall(r"^  ([a-z]+):\s*$", body, re.M)
    parts = re.split(r"^  [a-z]+:\s*$", body, flags=re.M)[1:]
    return dict(zip(names, parts))


class PagesWorkflowTest(unittest.TestCase):
    def test_triggers_and_inputs(self):
        t = read()
        head = t.split("\njobs:\n", 1)[0]
        self.assertIn("name: pages", head)
        self.assertIn("  push:\n    branches: [master]", head)
        for name in ("workflow_dispatch:", "      ref:", "      skip_checks:", "      dry_run:"):
            self.assertIn(name, head)
        self.assertIn("concurrency:\n  group: pages\n  cancel-in-progress: false", head)

    def test_job_order_and_needs(self):
        j = jobs(read())
        self.assertEqual(list(j), ["check", "build", "deploy", "verify"])
        self.assertIn("uses: ./.github/workflows/check.yml", j["check"])
        self.assertIn("needs: check", j["build"])
        self.assertIn("needs: build", j["deploy"])
        self.assertIn("needs: [build, deploy]", j["verify"])

    def test_least_privilege(self):
        t = read()
        j = jobs(t)
        self.assertIn("permissions:\n  contents: read", t.split("\njobs:\n", 1)[0])
        for name in ("check", "build", "verify"):
            self.assertNotIn("pages: write", j[name])
            self.assertNotIn("id-token: write", j[name])
        self.assertIn("pages: write", j["deploy"])
        self.assertIn("id-token: write", j["deploy"])
        self.assertIn("name: github-pages", j["deploy"])
        self.assertRegex(j["deploy"], r"actions/deploy-pages@[0-9a-f]{40} # v4")
        self.assertNotIn("actions/deploy-pages", j["build"])

    def test_gates_are_in_the_text(self):
        t = read()
        j = jobs(t)
        self.assertIn("vars.PAGES_VIA_ACTIONS == 'true'", j["build"])
        self.assertIn("needs.check.result == 'skipped'", j["build"])
        self.assertIn("compare/master...", j["build"])
        self.assertIn("GATE ancestor REFUSE", j["build"])
        self.assertIn("python3 tools/make_artifact.py --content content", j["build"])
        self.assertRegex(j["build"], r"actions/upload-pages-artifact@[0-9a-f]{40} # v3")
        self.assertIn("!inputs.dry_run", j["deploy"])
        self.assertIn("python3 tools/verify_deploy.py --expect-sha", j["verify"])
        self.assertIn("skip_checks is for rollback and needs a ref", j["build"])

    def test_nothing_destructive_and_no_secrets(self):
        t = read()
        for never in ("--force", "git push", "contents: write", "secrets.", "rm -rf", "gh release", "gh api -X"):
            self.assertNotIn(never, t)


if __name__ == "__main__":
    unittest.main()
