"""WS-9: the deploy-files rule of tools/check_site.py
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402

FIX = TOOLS / "tests" / "fixtures"
REPO = TOOLS.parent
CNAME = "CNAME"
GOOGLE = "google690400622efc7ebc.html"


def lines(findings) -> list[str]:
    return [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]


class DeployFilesTest(unittest.TestCase):
    def test_rule_is_registered(self):
        self.assertIn("deploy-files", [fn.rule for fn in check_site.CHECKS])

    def test_missing_files_fail(self):
        code, findings = check_site.run(FIX / "missing-deploy-files", ["deploy-files"])
        out = lines(findings)
        self.assertEqual(code, 1, out)
        self.assertIn(f"FAIL deploy-files {CNAME}:0 - :: must stay tracked: "
                      + check_site.DEPLOY_REQUIRED[CNAME], out)
        self.assertIn(f"FAIL deploy-files {GOOGLE}:0 - :: must stay tracked: "
                      + check_site.DEPLOY_REQUIRED[GOOGLE], out)

    def test_ok_site_has_both(self):
        code, findings = check_site.run(FIX / "ok-site", ["deploy-files"])
        self.assertEqual((code, lines(findings)), (0, []))

    def test_real_tree_has_both(self):
        code, findings = check_site.run(REPO, ["deploy-files"])
        self.assertEqual((code, lines(findings)), (0, []))


if __name__ == "__main__":
    unittest.main()
