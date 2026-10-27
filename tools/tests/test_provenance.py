"""SU-18 (gilly.space part): the provenance spec, attribution.json and check_provenance.py."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "heliosoftware" / "spec"
TOOL = SPEC / "tools" / "check_provenance.py"
ATTR = json.loads((SPEC / "attribution.json").read_text(encoding="utf-8"))
STAMP = "RHEF sunkit-0.7 via sunkit 0.7.0; upsilon=0.35,0.35; deviations=none"
OBJ = {"product": "heliogram", "version": "0.8", "instrument": "SDO/AIA 171", "observed": "2026-10-02T18:30:00Z",
       "credit": ATTR["credit"], "rhef": None, "citation": None}

spec = importlib.util.spec_from_file_location("check_provenance", TOOL)
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


def chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def png(texts: dict) -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    out = cp.PNG_MAGIC + chunk(b"IHDR", ihdr)
    for k, v in texts.items():
        out += chunk(b"tEXt", k.encode("latin-1") + b"\0" + v.encode("utf-8"))
    return out + chunk(b"IDAT", zlib.compress(b"\0\0")) + chunk(b"IEND", b"")


def card(text: str) -> bytes:
    return text.ljust(80).encode("ascii")


def fits(cards: list) -> bytes:
    raw = b"".join(card(c) for c in ["SIMPLE  =                    T"] + cards + ["END"])
    return raw.ljust(2880)


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_tool(self, *paths):
        r = subprocess.run([sys.executable, str(TOOL), *map(str, paths)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def write(self, name, data):
        p = self.tmp / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return p


class AttributionTest(Case):
    def test_the_credit_is_the_line_the_wall_already_shows(self):
        self.assertIn(ATTR["credit"], (ROOT / "sun-wall.html").read_text(encoding="utf-8"))

    def test_the_citation_is_unset_until_gilly_chooses(self):
        self.assertIsNone(ATTR["rhef_citation"])
        self.assertIsNone(ATTR["rhef_doi"])

    def test_the_stamp_pattern_is_the_conventions_pattern(self):
        text = (SPEC / "rhef" / "conventions.md").read_text(encoding="utf-8")
        self.assertIn(cp.STAMP.pattern, text)

    def test_files_are_listed_on_the_spec_index_and_have_no_em_dash(self):
        html = (SPEC / "index.html").read_text(encoding="utf-8")
        for name in ("provenance.md", "attribution.json", "tools/check_provenance.py"):
            self.assertEqual(html.count(f'href="{name}"'), 1, name)
            self.assertNotIn(chr(0x2014), (SPEC / name).read_text(encoding="utf-8"), name)


class CreditsTest(Case):
    def test_every_instrument_credit_is_ascii_and_has_a_source(self):
        self.assertGreater(len(ATTR["credits"]), 0)
        for key, c in ATTR["credits"].items():
            self.assertEqual(set(c) - {"note"}, {"credit", "credit_source", "acknowledgement", "kind", "source"}, key)
            self.assertIn(c["kind"], ("required", "suggested", "none_found"), key)
            if c["credit"] is not None:
                self.assertTrue(c["credit"].isascii(), key)
                self.assertTrue(c["credit_source"].startswith("https://"), key)
            if c["kind"] != "none_found":
                self.assertTrue(c["source"].startswith("https://"), key)

    def test_joined_instrument_credits_pass_and_a_stranger_or_a_repeat_fails(self):
        lasco, aia = ATTR["credits"]["SOHO/LASCO"]["credit"], ATTR["credits"]["SDO/AIA"]["credit"]
        for good in (aia, lasco + " " + aia, ATTR["credit_fallback"], ATTR["credit"]):
            self.assertEqual(cp.check_object(dict(OBJ, credit=good)), [], good)
        for bad in (aia + " " + aia, lasco + " Somebody else", lasco + "  " + aia, ATTR["credit_fallback"] + " " + aia):
            self.assertIn("credit differs", "; ".join(cp.check_object(dict(OBJ, credit=bad))), bad)


class SidecarTest(Case):
    def test_a_full_sidecar_passes(self):
        p = self.write("a.provenance.json", json.dumps(OBJ))
        self.assertEqual(self.run_tool(p)[0], 0)

    def test_a_missing_field_a_bad_time_and_a_wrong_credit_are_named(self):
        bad = dict(OBJ, observed="yesterday", credit="Somebody else")
        del bad["product"]
        code, out = self.run_tool(self.write("b.provenance.json", json.dumps(bad)))
        self.assertEqual(code, 1)
        for needle in ("missing product", "observed is not", "credit differs"):
            self.assertIn(needle, out)

    def test_rhef_must_be_a_stamp_line_and_values_must_be_strings(self):
        self.assertIn("rhef is not a stamp line", "; ".join(cp.check_object(dict(OBJ, rhef="RHEF something"))))
        self.assertEqual(cp.check_object(dict(OBJ, rhef=STAMP)), [])
        self.assertIn("version is not a string or null", "; ".join(cp.check_object(dict(OBJ, version=8))))


class PngTest(Case):
    def test_png_with_provenance_passes_and_without_fails(self):
        ok = self.write("ok.png", png({"HelioSoftware-Provenance": json.dumps(OBJ)}))
        no = self.write("no.png", png({"Software": "x"}))
        self.assertEqual(self.run_tool(ok)[0], 0)
        code, out = self.run_tool(no)
        self.assertEqual((code, "no HelioSoftware-Provenance chunk" in out), (1, True))

    def test_an_rhef_png_needs_its_stamp_chunk_and_the_disclaimer(self):
        obj = dict(OBJ, rhef=STAMP)
        bare = png({"HelioSoftware-Provenance": json.dumps(obj)})
        self.assertEqual(len(cp.check_png(bare)), 2)
        full = png({"HelioSoftware-Provenance": json.dumps(obj), "RHEF": STAMP, "Disclaimer": ATTR["disclaimer"]})
        self.assertEqual(cp.check_png(full), [])
        stray = png({"HelioSoftware-Provenance": json.dumps(OBJ), "RHEF": STAMP})
        self.assertIn("RHEF chunk without rhef", "; ".join(cp.check_png(stray)))


class FitsTest(Case):
    def test_origin_and_credit_pass(self):
        data = fits(["ORIGIN  = 'heliofits 1.2'", "HISTORY " + ATTR["credit"]])
        self.assertEqual(self.run_tool(self.write("a.fits", data))[0], 0)

    def test_missing_origin_and_credit_fail(self):
        code, out = self.run_tool(self.write("b.fits", fits(["BITPIX  =                  -32"])))
        self.assertEqual(code, 1)
        self.assertIn("missing ORIGIN", out)
        self.assertIn("missing the credit line", out)

    def test_a_stamp_needs_its_disclaimer_and_a_split_line_is_joined(self):
        base = ["ORIGIN  = 'heliofits 1.2'", "HISTORY " + ATTR["credit"], "HISTORY " + STAMP]
        self.assertIn("missing the disclaimer", "; ".join(cp.check_fits(fits(base))))
        self.assertEqual(cp.check_fits(fits(base + ["HISTORY " + ATTR["disclaimer"]])), [])
        long_stamp = STAMP.replace("deviations=none", "deviations=GEOM-PX,BIN-HALF,DTYPE-IN")
        self.assertGreater(len(long_stamp), 72)
        split = ["ORIGIN  = 'x 1'", "HISTORY " + ATTR["credit"], "HISTORY " + long_stamp[:72], "HISTORY " + long_stamp[72:],
                 "HISTORY " + ATTR["disclaimer"]]
        self.assertEqual(cp.check_fits(fits(split)), [], "a filled card continues; a short one ends its line")
        broken = split[:2] + ["HISTORY " + long_stamp[:60], "HISTORY " + long_stamp[60:]] + split[4:]
        self.assertIn("not a stamp line", "; ".join(cp.check_fits(fits(broken))))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class Mp4Test(Case):
    def make(self, name, *meta, flags=()):
        out = self.tmp / name
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1:r=5", *flags]
        for m in meta:
            cmd += ["-metadata", m]
        subprocess.run(cmd + [str(out)], check=True)
        return out

    def test_description_with_the_credit_passes(self):
        p = self.make("a.mp4", "description=" + ATTR["credit"], "comment=" + STAMP)
        self.assertEqual(self.run_tool(p)[0], 0)

    def test_no_description_or_a_bad_stamp_fails(self):
        self.assertEqual(self.run_tool(self.make("b.mp4"))[0], 1)
        p = self.make("c.mp4", "description=" + ATTR["credit"], "comment=RHEF broken")
        self.assertIn("comment is not a stamp line", self.run_tool(p)[1])

    def test_mdta_keys_from_use_metadata_tags_are_read(self):
        # Studio writes a custom hfrecord tag, which needs -movflags use_metadata_tags; ffmpeg
        # then stores every tag as an mdta key instead of the classic desc and (c)cmt atoms.
        tags = ("-movflags", "use_metadata_tags")
        p = self.make("d.mp4", "description=" + ATTR["credit"], "comment=" + STAMP, "hfrecord={}", flags=tags)
        self.assertEqual(self.run_tool(p)[0], 0)
        p = self.make("e.mp4", "description=" + ATTR["credit"], "comment=RHEF broken", flags=tags)
        self.assertIn("comment is not a stamp line", self.run_tool(p)[1])
        self.assertEqual(self.run_tool(self.make("f.mp4", "hfrecord={}", flags=tags))[0], 1)


class ExitCodeTest(Case):
    def test_no_file_an_unknown_file_and_a_corrupt_file_exit_2(self):
        self.assertEqual(self.run_tool()[0], 2)
        self.assertEqual(self.run_tool(self.write("a.txt", "x"))[0], 2)
        self.assertEqual(self.run_tool(self.write("bad.png", "not a png"))[0], 2)
        self.assertEqual(self.run_tool(self.tmp / "missing.png")[0], 2)

    def test_one_failure_among_passes_is_exit_1(self):
        ok = self.write("ok.provenance.json", json.dumps(OBJ))
        bad = self.write("bad.provenance.json", "{}")
        self.assertEqual(self.run_tool(ok, bad)[0], 1)


if __name__ == "__main__":
    unittest.main()
