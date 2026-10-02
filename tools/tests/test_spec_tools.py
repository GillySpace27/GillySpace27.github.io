"""Tests for the stdlib tools under heliosoftware/spec/ and for the folder itself.

Run from the Website root:  python3 -m unittest tools.tests.test_spec_tools
or:                         python3 -m unittest discover -s tools/tests -p 'test_*.py'
Each tool is imported by path, so the working directory does not matter.
"""
import contextlib
import hashlib
import importlib.util
import io
import os
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True      # never leave __pycache__ inside spec/
ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "heliosoftware" / "spec"


def load_tool(rel):
    """Import heliosoftware/spec/<rel> by path; FileNotFoundError when it does not exist."""
    path = SPEC / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, *argv):
    """Call mod.main(argv) and return (exit code, captured stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = mod.main(list(argv))
        except SystemExit as err:
            code = err.code
    return code, out.getvalue()


def sha(data):
    return hashlib.sha256(data).hexdigest()


class SpecSumsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool("spec_sums.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        (self.dir / "a.txt").write_text("alpha\n")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "b.txt").write_text("beta\n")

    def sums(self, flag):
        return run(self.tool, flag, "--dir", str(self.dir))

    def test_write_then_check(self):
        code, out = self.sums("--write")
        self.assertEqual((code, out), (0, "spec_sums: wrote 2 entries\n"))
        text = (self.dir / "SHA256SUMS").read_text()
        self.assertEqual(text, f"{sha(b'alpha' + bytes([10]))}  a.txt\n{sha(b'beta' + bytes([10]))}  sub/b.txt\n")
        first = (self.dir / "SHA256SUMS").read_bytes()
        self.sums("--write")
        self.assertEqual((self.dir / "SHA256SUMS").read_bytes(), first, "a second write is byte-identical")
        code, out = self.sums("--check")
        self.assertEqual((code, out), (0, "spec_sums: 2 files match SHA256SUMS\n"))

    def test_changed_byte_is_a_mismatch(self):
        self.sums("--write")
        (self.dir / "a.txt").write_text("alphb\n")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH a.txt\n", out)
        self.assertIn("spec_sums: 1 problem(s)", out)

    def test_new_file_is_extra(self):
        self.sums("--write")
        (self.dir / "c.txt").write_text("gamma\n")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("EXTRA c.txt\n", out)

    def test_removed_file_is_missing(self):
        self.sums("--write")
        os.remove(self.dir / "sub" / "b.txt")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("MISSING sub/b.txt\n", out)

    def test_excluded_paths_are_not_listed(self):
        (self.dir / ".claude" / "worktrees" / "w").mkdir(parents=True)
        (self.dir / ".claude" / "worktrees" / "w" / "x.txt").write_text("worktree\n")
        (self.dir / "__pycache__").mkdir()
        (self.dir / "__pycache__" / "m.cpython-311.pyc").write_bytes(b"pyc")
        (self.dir / "top.pyc").write_bytes(b"pyc")
        (self.dir / ".DS_Store").write_bytes(b"ds")
        self.sums("--write")
        listed = [ln.split("  ", 1)[1] for ln in (self.dir / "SHA256SUMS").read_text().splitlines()]
        self.assertEqual(listed, ["a.txt", "sub/b.txt"])
        self.assertEqual(self.sums("--check")[0], 0)

    def test_missing_sums_file(self):
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("MISSING SHA256SUMS", out)

    def test_malformed_line(self):
        (self.dir / "SHA256SUMS").write_text("not a hash line\n")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("SHA256SUMS:1", out)



class CheckSpecTests(unittest.TestCase):
    CANON = b"## Rules\n\nBe careful.\nTwo lines.\n"
    BODY = b"echo gate\nexit 0\n"

    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool("check_spec.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        env = mock.patch.dict(os.environ)       # a developer's own HELIOSOFTWARE_SPEC_DIR must not leak in
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("HELIOSOFTWARE_SPEC_DIR", None)
        self.spec = self.dir / "spec"
        (self.spec / "tools").mkdir(parents=True)
        (self.spec / "agent-preamble.md").write_bytes(self.CANON)

    def put(self, name, data):
        path = self.dir / name
        path.write_bytes(data)
        return str(path)

    @staticmethod
    def block(body, stated=None):
        stated = sha(body) if stated is None else stated
        return (b"# Title\n\n<!-- heliosoftware-preamble v1 sha256=" + stated.encode() + b" -->\n"
                + body + b"<!-- /heliosoftware-preamble -->\n\nafter\n")

    @staticmethod
    def vendored(body, label="HelioFITS", path="release-gates.sh", shebang=b""):
        stated = sha(shebang + body)
        head = f"# heliosoftware-vendored: {label}:{path} sha256={stated}\n".encode()
        return shebang + head + body

    def test_preamble_ok_without_a_canonical_copy(self):
        f = self.put("CLAUDE.md", self.block(self.CANON))
        self.assertEqual(run(self.tool, f), (0, f"OK {f}\n"))

    def test_preamble_body_edit_is_drift(self):
        edited = self.CANON.replace(b"careful", b"carefull")
        f = self.put("CLAUDE.md", self.block(edited, stated=sha(self.CANON)))
        code, out = run(self.tool, f)
        self.assertEqual(code, 1)
        self.assertIn(f"DRIFT {f}: block text does not hash to the sha256 in its opening marker", out)

    def test_restamped_copy_still_drifts_from_the_spec_dir(self):
        f = self.put("CLAUDE.md", self.block(b"## Rules\n\nBe reckless.\n"))
        code, out = run(self.tool, "--spec-dir", str(self.spec), f)
        self.assertEqual(code, 1)
        self.assertIn(f"DRIFT {f}: block text differs from the canonical agent-preamble.md", out)

    def test_preamble_matching_the_spec_dir_is_ok(self):
        f = self.put("CLAUDE.md", self.block(self.CANON))
        self.assertEqual(run(self.tool, "--spec-dir", str(self.spec), f), (0, f"OK {f}\n"))

    def test_canonical_flag_wins_over_the_spec_dir(self):
        other = b"## Rules\n\nOther.\n"
        canon = self.put("canon.md", other)
        f = self.put("CLAUDE.md", self.block(other))
        self.assertEqual(run(self.tool, "--spec-dir", str(self.spec), "--canonical", canon, f), (0, f"OK {f}\n"))

    def test_environment_variable_names_the_spec_dir(self):
        f = self.put("CLAUDE.md", self.block(b"## Rules\n\nBe reckless.\n"))
        with mock.patch.dict(os.environ, {"HELIOSOFTWARE_SPEC_DIR": str(self.spec)}):
            code, out = run(self.tool, f)
        self.assertEqual(code, 1)
        self.assertIn("differs from the canonical agent-preamble.md", out)

    def test_two_blocks_are_drift(self):
        one = self.block(self.CANON)
        f = self.put("CLAUDE.md", one + one)
        code, out = run(self.tool, f)
        self.assertEqual(code, 1)
        self.assertIn(f"DRIFT {f}: 2 opening and 2 closing markers, expected 1 and 1", out)

    def test_vendored_header_on_line_one(self):
        f = self.put("gates.txt", self.vendored(self.BODY))
        self.assertEqual(run(self.tool, f), (0, f"OK {f}\n"))

    def test_vendored_header_after_a_shebang(self):
        f = self.put("release-gates.sh", self.vendored(self.BODY, shebang=b"#!/bin/bash\n"))
        self.assertEqual(run(self.tool, f), (0, f"OK {f}\n"))

    def test_vendored_body_edit_is_drift(self):
        f = self.put("gates.txt", self.vendored(self.BODY).replace(b"exit 0", b"exit 1"))
        code, out = run(self.tool, f)
        self.assertEqual(code, 1)
        self.assertIn(f"DRIFT {f}: body does not hash to the sha256 in its vendored header", out)

    def test_vendored_website_copy_is_compared_with_the_spec_dir(self):
        rel = "heliosoftware/spec/tools/no_em_dash.py"
        (self.spec / "tools" / "no_em_dash.py").write_bytes(self.BODY)
        same = self.put("a.py", self.vendored(self.BODY, label="Website", path=rel))
        stale = self.put("b.py", self.vendored(b"echo gate\nexit 2\n", label="Website", path=rel))
        code, out = run(self.tool, "--spec-dir", str(self.spec), same, stale)
        self.assertEqual(code, 1)
        self.assertIn(f"OK {same}\n", out)
        self.assertIn(f"DRIFT {stale}: body differs from the canonical Website:{rel}", out)

    def test_vendored_header_on_line_three_is_not_a_marker(self):
        f = self.put("late.txt", b"one\ntwo\n" + self.vendored(self.BODY))
        code, out = run(self.tool, f)
        self.assertEqual(code, 2)
        self.assertIn(f"NOMARKER {f}:", out)

    def test_no_marker_exits_2(self):
        f = self.put("plain.txt", b"hello\n")
        code, out = run(self.tool, f)
        self.assertEqual(code, 2)
        self.assertIn(f"NOMARKER {f}: neither a preamble block nor a vendored header", out)

    def test_unreadable_exits_2(self):
        missing = str(self.dir / "nope.txt")
        code, out = run(self.tool, missing)
        self.assertEqual(code, 2)
        self.assertIn(f"UNREADABLE {missing}:", out)

    def test_no_marker_wins_over_drift(self):
        drift = self.put("CLAUDE.md", self.block(self.CANON.replace(b"careful", b"carefull"), stated=sha(self.CANON)))
        plain = self.put("plain.txt", b"hello\n")
        code, out = run(self.tool, drift, plain)
        self.assertEqual(code, 2)
        self.assertIn("DRIFT ", out)
        self.assertIn("NOMARKER ", out)



class SpecFolderTests(unittest.TestCase):
    """Checks on the real heliosoftware/spec/ folder (the CI hook for every later initiative)."""

    TEXT_SUFFIXES = {".html", ".md", ".py", ".json", ".txt", ".mjs", ".js", ".xml", ".css"}

    def test_sums_match_the_folder(self):
        code, out = run(load_tool("spec_sums.py"), "--check")
        self.assertEqual(code, 0, out)

    def test_every_top_level_entry_is_linked_from_index_html(self):
        html = (SPEC / "index.html").read_text(encoding="utf-8")
        linked = set()
        for href in re.findall(r'href="([^"#?]+)"', html):
            if re.match(r"^(?:[a-z]+:|/)", href):
                continue
            linked.add(href.split("/")[0])
        entries = {p.name for p in SPEC.iterdir()
                   if not p.name.startswith(".") and p.name not in ("__pycache__", "index.html")}
        self.assertEqual(sorted(entries - linked), [], "files in spec/ that index.html does not link")

    def test_no_em_dash_in_text_files(self):
        bad = []
        for path in SPEC.rglob("*"):
            if path.is_file() and (path.suffix in self.TEXT_SUFFIXES or path.name == "SHA256SUMS"):
                if b"\xe2\x80\x94" in path.read_bytes():
                    bad.append(path.relative_to(SPEC).as_posix())
        self.assertEqual(bad, [])



def load_site_tool(rel):
    """Import tools/<rel> by path (the stdlib tools that live beside the spec folder)."""
    path = ROOT / "tools" / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RhefCopyTests(unittest.TestCase):
    """tools/copy_rhef_golden.py against a synthetic bundle shaped like fastRHEF golden/."""

    @classmethod
    def setUpClass(cls):
        cls.tool = load_site_tool("copy_rhef_golden.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.dest = self.base / "dest"
        self.src, self.raw = self.make_bundle(self.base / "golden")

    @staticmethod
    def make_bundle(root, version="1.0.0", payload=b"\x02" * 16):
        import json
        files = {
            "README.md": b"readme\n",
            "read_golden.py": b"# reader\n",
            "ties_zero_fill_64/case.properties": b"case_id=ties_zero_fill_64\n",
            "ties_zero_fill_64/input.f64": b"\x00" * 16,
            "ties_zero_fill_64/expected_oRHEF-2.0.f64": b"\x01" * 16,
            "ties_zero_fill_64/expected_sunkit-0.7.f64": payload,
            "geometry_hpc_32/header.json": b"{}\n",
            "equal_width_128/input.f64": b"\x03" * 16,
        }
        for rel, data in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        manifest = {"bundle_version": version, "generator": "tools/make_golden.py", "generator_git_sha": "abc123",
                    "files": {rel: sha(data) for rel, data in files.items()}}
        raw = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
        (root / "manifest.json").write_bytes(raw)
        return root, raw

    def copy(self, *extra):
        return run(self.tool, "--src", str(self.src), "--dest", str(self.dest),
                   "--cases", "ties_zero_fill_64,geometry_hpc_32", *extra)

    def published(self):
        gold = self.dest / "golden"
        return sorted(p.relative_to(gold).as_posix() for p in gold.rglob("*") if p.is_file())

    def test_default_copy_withholds_orhef_and_private_cases(self):
        code, out = self.copy()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.published(), [
            "README.md", "SOURCE.txt", "geometry_hpc_32/header.json", "read_golden.py",
            "ties_zero_fill_64/case.properties", "ties_zero_fill_64/expected_sunkit-0.7.f64",
            "ties_zero_fill_64/input.f64"])
        self.assertEqual((self.dest / "vectors.json").read_bytes(), self.raw, "the manifest is copied byte for byte")
        first = (self.dest / "golden" / "SOURCE.txt").read_text().splitlines()[0]
        self.assertRegex(first, r"^fastRHEF abc123 bundle 1\.0\.0 manifest-sha256 [0-9a-f]{64}$")
        self.assertIn("withheld: expected_oRHEF-2.0.*", (self.dest / "golden" / "SOURCE.txt").read_text())
        self.assertIn("copied 6 files", out)
        code, out = run(self.tool, "--verify", "--dest", str(self.dest))
        self.assertEqual(code, 0, out)
        self.assertIn("6 files checked, 0 problem(s); 2 manifest files not published", out)

    def test_include_orhef_copies_the_expectation(self):
        code, out = self.copy("--include-orhef")
        self.assertEqual(code, 0, out)
        self.assertIn("ties_zero_fill_64/expected_oRHEF-2.0.f64", self.published())
        self.assertIn("withheld: none", (self.dest / "golden" / "SOURCE.txt").read_text())

    def test_corrupt_source_file_writes_nothing(self):
        (self.src / "ties_zero_fill_64" / "input.f64").write_bytes(b"\xff" * 16)
        code, out = self.copy()
        self.assertEqual(code, 1)
        self.assertIn("CORRUPT ties_zero_fill_64/input.f64: sha256 differs from manifest.json", out)
        self.assertFalse((self.dest / "vectors.json").exists())

    def test_verify_finds_a_flipped_byte_and_an_extra_file(self):
        self.copy()
        target = self.dest / "golden" / "ties_zero_fill_64" / "input.f64"
        target.write_bytes(b"\x09" + target.read_bytes()[1:])
        (self.dest / "golden" / "stray.bin").write_bytes(b"x")
        code, out = run(self.tool, "--verify", "--dest", str(self.dest))
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH ties_zero_fill_64/input.f64", out)
        self.assertIn("EXTRA stray.bin", out)

    def test_second_identical_copy_is_fine_and_a_tampered_file_is_a_conflict(self):
        self.assertEqual(self.copy()[0], 0)
        self.assertEqual(self.copy()[0], 0)
        target = self.dest / "golden" / "geometry_hpc_32" / "header.json"
        target.write_bytes(b"{ }\n")
        code, out = self.copy()
        self.assertEqual(code, 1)
        self.assertIn("CONFLICT geometry_hpc_32/header.json", out)
        self.assertEqual(target.read_bytes(), b"{ }\n", "nothing was overwritten")

    def test_changed_content_with_the_same_version_is_a_conflict(self):
        self.copy()
        other, _ = self.make_bundle(self.base / "golden2", payload=b"\x07" * 16)
        code, out = run(self.tool, "--src", str(other), "--dest", str(self.dest),
                        "--cases", "ties_zero_fill_64,geometry_hpc_32")
        self.assertEqual(code, 1)
        self.assertIn("CONFLICT vectors.json differs from this bundle's manifest.json", out)

    def test_a_new_bundle_version_needs_a_new_destination(self):
        self.copy()
        newer, _ = self.make_bundle(self.base / "golden3", version="1.1.0")
        code, out = run(self.tool, "--src", str(newer), "--dest", str(self.dest),
                        "--cases", "ties_zero_fill_64,geometry_hpc_32")
        self.assertEqual(code, 1)
        self.assertIn("NEW BUNDLE VERSION 1.1.0 (published: 1.0.0)", out)

    def test_size_limit_and_unknown_case(self):
        code, out = self.copy("--max-bytes", "10")
        self.assertEqual(code, 1)
        self.assertIn("TOO LARGE", out)
        code, out = run(self.tool, "--src", str(self.src), "--dest", str(self.dest), "--cases", "nope_64")
        self.assertEqual(code, 1)
        self.assertIn("NOT IN BUNDLE nope_64", out)

    def test_verify_without_a_copy(self):
        code, out = run(self.tool, "--verify", "--dest", str(self.dest))
        self.assertEqual(code, 1)
        self.assertIn("MISSING vectors.json", out)



class RhefTableTests(unittest.TestCase):
    LINES = (
        "noise before\n"
        "RHEF-CONFORMANCE impl=heliofits-swift bundle=1.0.0 case=ties_zero_fill_64 convention=sunkit-0.7 max_abs_diff=1.200e-04 result=REPORT\n"
        "RHEF-CONFORMANCE impl=heliofits-swift bundle=1.0.0 case=nan_holes_64 convention=sunkit-0.7 max_abs_diff=0.000e+00 result=PASS\n"
        "RHEF-CONFORMANCE impl=heliofits-swift summary pass=1 report=1 fail=0 mode=report\n"
        "RHEF-CONFORMANCE impl=idl bundle=1.0.0 case=ties_zero_fill_64 convention=sunkit-0.7 max_abs_diff=nan result=FAIL\n"
        "RHEF-CONFORMANCE impl=idl summary pass=0 report=0 fail=1 mode=enforce\n")

    @classmethod
    def setUpClass(cls):
        cls.tool = load_site_tool("rhef_conformance_table.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def put(self, name, text):
        path = self.dir / name
        path.write_text(text)
        return str(path)

    def test_table_has_one_row_per_case_and_one_column_per_implementation(self):
        code, out = run(self.tool, self.put("runs.txt", self.LINES))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines(), [
            "Bundle 1.0.0.",
            "",
            "| Case (convention) | heliofits-swift | idl |",
            "|---|---|---|",
            "| nan_holes_64 (sunkit-0.7) | 0.000e+00 PASS | - |",
            "| ties_zero_fill_64 (sunkit-0.7) | 1.200e-04 REPORT | nan FAIL |",
            "| mode | report | enforce |"])

    def test_no_lines_and_mixed_bundles_are_errors(self):
        code, out = run(self.tool, self.put("empty.txt", "nothing\n"))
        self.assertEqual(code, 1)
        self.assertIn("no RHEF-CONFORMANCE lines", out)
        mixed = self.LINES + "RHEF-CONFORMANCE impl=idl bundle=1.1.0 case=x convention=sunkit-0.7 max_abs_diff=0.000e+00 result=PASS\n"
        code, out = run(self.tool, self.put("mixed.txt", mixed))
        self.assertEqual(code, 1)
        self.assertIn("mixed bundle versions: 1.0.0, 1.1.0", out)

    def test_into_replaces_only_the_marked_region(self):
        page = self.put("page.md", "before\n<!-- conformance-table begin -->\nold\n<!-- conformance-table end -->\nafter\n")
        code, out = run(self.tool, "--into", page, self.put("runs.txt", self.LINES))
        self.assertEqual(code, 0, out)
        text = pathlib.Path(page).read_text()
        self.assertTrue(text.startswith("before\n<!-- conformance-table begin -->\nBundle 1.0.0."))
        self.assertTrue(text.endswith("| mode | report | enforce |\n<!-- conformance-table end -->\nafter\n"))
        self.assertNotIn("old", text)

    def test_into_refuses_a_page_without_exactly_one_pair_of_markers(self):
        page = self.put("bare.md", "no markers here\n")
        code, out = run(self.tool, "--into", page, self.put("runs.txt", self.LINES))
        self.assertEqual(code, 1)
        self.assertIn("expected exactly one begin and one end marker", out)
        self.assertEqual(pathlib.Path(page).read_text(), "no markers here\n")


# end of spec tool tests
if __name__ == "__main__":
    unittest.main()
