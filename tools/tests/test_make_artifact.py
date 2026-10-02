"""WS-9: tools/make_artifact.py stages the Pages artifact and writes build.json
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

Every test builds a throwaway git repository; nothing touches the real checkout.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

INDEX = '<!doctype html>\n<link rel="stylesheet" href="/assets/site.css?v=202610011200">\n'
GOOGLE = "google690400622efc7ebc.html"


def ma():
    return importlib.import_module("make_artifact")


def git(root: pathlib.Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                       check=True, capture_output=True, text=True)
    return r.stdout.strip()


def make_repo(base: pathlib.Path, *, cname: bool = True, index: str = INDEX) -> pathlib.Path:
    root = base / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "dir with space").mkdir()
    git(root, "init", "-q")
    files = {
        GOOGLE: "google-site-verification: google690400622efc7ebc.html\n",
        "index.html": index,
        "a.txt": "a\n",
        "dir with space/b.txt": "b\n",
        ".github/workflows/x.yml": "name: x\n",
        ".gitignore": "ignored.txt\n",
        ".gitattributes": "* text=auto\n",
    }
    if cname:
        files["CNAME"] = "gilly.space\n"
    for rel, body in files.items():
        (root / rel).write_text(body)
    (root / "untracked.txt").write_text("not tracked\n")
    git(root, "add", "--", *files)
    git(root, "commit", "-q", "-m", "init")
    return root


def tree(out: pathlib.Path) -> set[str]:
    return {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}


class ArtifactTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = pathlib.Path(self._tmp.name)

    def test_stage_keeps_tracked_files_and_drops_dotfiles(self):
        root = make_repo(self.base)
        out = self.base / "out"
        n = ma().stage(root, out)
        self.assertEqual(tree(out), {"CNAME", GOOGLE, "index.html", "a.txt", "dir with space/b.txt"})
        self.assertEqual(n, 5)
        self.assertEqual((out / "dir with space" / "b.txt").read_text(), "b\n")

    def test_stage_never_writes_inside_content(self):
        root = make_repo(self.base)
        before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if ".git/" not in p.as_posix())
        ma().stage(root, self.base / "out")
        after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if ".git/" not in p.as_posix())
        self.assertEqual(before, after)

    def test_build_json_fields(self):
        root = make_repo(self.base)
        info = ma().build_json(root, "", "2026-10-01T12:34:56Z")
        sha = git(root, "rev-parse", "HEAD")
        self.assertEqual(list(info), ["commit", "ref", "stamp", "built_utc"])
        self.assertEqual(info, {"commit": sha, "ref": sha, "stamp": "202610011200",
                                "built_utc": "2026-10-01T12:34:56Z"})
        self.assertEqual(ma().build_json(root, "v1", "2026-10-01T12:34:56Z")["ref"], "v1")
        self.assertRegex(ma().build_json(root)["built_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_index_without_a_stamp_is_unstamped(self):
        root = make_repo(self.base, index="<!doctype html>\n<p>no assets</p>\n")
        self.assertEqual(ma().build_json(root)["stamp"], "unstamped")

    def test_missing_cname_refuses(self):
        root = make_repo(self.base, cname=False)
        with self.assertRaises(ma().ArtifactError) as cm:
            ma().stage(root, self.base / "out")
        self.assertIn("tree lacks CNAME", str(cm.exception))
        self.assertFalse((self.base / "out").exists())

    def test_out_must_be_empty(self):
        root = make_repo(self.base)
        out = self.base / "out"
        out.mkdir()
        (out / "keep.txt").write_text("x")
        with self.assertRaises(ma().ArtifactError) as cm:
            ma().stage(root, out)
        self.assertIn("is not empty", str(cm.exception))
        self.assertEqual(tree(out), {"keep.txt"})

    def test_skipped_names(self):
        m = ma()
        self.assertTrue(m.skipped(".github/workflows/x.yml"))
        self.assertTrue(m.skipped(".gitignore"))
        for hidden in (".mailmap", ".editorconfig", ".gitattributes", ".nojekyll",
                       "tools/.github/y", ".github-not-really/x", "bkk/lib/.gitattributes", ".well-known/x"):
            self.assertTrue(m.skipped(hidden), hidden)
        for private in ("assets/sass/libs/_vars.scss", "_config.yml", "_site/index.html", "a/_b/c.txt"):
            self.assertTrue(m.skipped(private), private)
        for build in ("__pycache__/x.py", "tools/__pycache__/x.cpython-311.pyc",
                      "tools/tests/__pycache__/test_x.cpython-311.pyc", "stray.pyc", "tools/mod.pyc"):
            self.assertTrue(m.skipped(build), build)
        for served in ("CNAME", "index.html", "a.txt", "dir with space/b.txt", "assets/site.css",
                       "heliosoftware/spec/agent-preamble.md", "my_file.txt", "a/b_c/d.txt", "x.pycx", "pyc"):
            self.assertFalse(m.skipped(served), served)

    def test_stage_drops_every_dot_underscore_and_build_path(self):
        root = make_repo(self.base)
        extra = {
            ".mailmap": "Gilly <x@example.com>\n",
            ".editorconfig": "root = true\n",
            ".nojekyll": "",
            "sub/.gitattributes": "* text=auto\n",
            "assets/sass/libs/_vars.scss": "$a: 1;\n",
            "assets/site.css": "a{}\n",
            "tools/tests/__pycache__/t.cpython-311.pyc": "x",
            "stray.pyc": "x",
            "heliosoftware/spec/agent-preamble.md": "preamble\n",
        }
        for rel, body in extra.items():
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(body)
        git(root, "add", "-f", "--", *extra)
        git(root, "commit", "-q", "-m", "more")
        out = self.base / "out"
        ma().stage(root, out)
        self.assertEqual(tree(out), {"CNAME", GOOGLE, "index.html", "a.txt", "dir with space/b.txt",
                                     "assets/site.css", "heliosoftware/spec/agent-preamble.md"})

    def test_cli_writes_build_json_and_prints_it(self):
        root = make_repo(self.base)
        out = self.base / "out"
        r = subprocess.run([sys.executable, str(TOOLS / "make_artifact.py"), "--content", str(root),
                            "--out", str(out), "--ref", "master", "--now", "2026-10-01T00:00:00Z"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        written = json.loads((out / "build.json").read_text())
        self.assertEqual(json.loads(r.stdout), written)
        self.assertEqual(written["ref"], "master")
        self.assertEqual(written["commit"], git(root, "rev-parse", "HEAD"))
        self.assertRegex(r.stderr, r"make_artifact: staged 5 files")

    def test_cli_refusal_is_exit_1_and_named(self):
        root = make_repo(self.base, cname=False)
        r = subprocess.run([sys.executable, str(TOOLS / "make_artifact.py"), "--content", str(root),
                            "--out", str(self.base / "out")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("make_artifact: REFUSE: tree lacks CNAME", r.stderr)

    def test_bad_now_is_a_usage_error(self):
        root = make_repo(self.base)
        r = subprocess.run([sys.executable, str(TOOLS / "make_artifact.py"), "--content", str(root),
                            "--out", str(self.base / "out"), "--now", "yesterday"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--now must look like", r.stderr)


if __name__ == "__main__":
    unittest.main()
