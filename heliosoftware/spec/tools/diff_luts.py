#!/usr/bin/env python3
"""Report how far candidate colour tables are from the reference tables (suite SU-12, report only).

    python3 diff_luts.py --ref heliosoftware/spec/colormaps --candidate DIR_OR_FILE [--tol 1]
    python3 diff_luts.py --ref ... --candidate sunpy:                 # the installed sunpy
    python3 diff_luts.py --ref ... --candidate sunback:~/vscode/sunback

Reference: <name>.json files {"name", "source", "rgb": 256 x [r, g, b]} written by HelioFITS's
tools/colormaps/gen_colormaps.py --json-out. Candidates (a folder is scanned, a file is one table):
  *.json  the same shape
  *.csv   256 rows of r,g,b (lines starting # and an "r,g,b" header are skipped); name = file stem
  *.ggr   a GIMP gradient as HelioFITS Studio reads it (LUT.readGimpGradient: 256 samples at i/255);
          AIA<n>.ggr maps to the reference name sdoaia<n>, any other stem is used as is
  sunpy:  the installed sunpy's tables (needs sunpy and numpy)
  sunback:<root>  sunback's own sunback/science/color_tables.py aia_color_table for each AIA wavelength
Prints "<name> maxdiff=<n> OK|OVER" per compared table, "NOREF <name>" for a candidate with no reference,
"UNCHECKED <path>: <reason>" for a file it cannot judge, and a last line "diff_luts: <c> compared, <o> over tol".
Exit 1 when any table is over --tol (default 1, in 0-255 steps), 2 on unreadable input. Report only: no
product CI runs it, and nothing is replaced in any product.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys


class Bad(Exception):
    """A file or table that cannot be read or judged; the message says why."""


def check_rgb(rgb, where):
    if not isinstance(rgb, list) or len(rgb) != 256 or any(not isinstance(t, list) or len(t) != 3 for t in rgb):
        raise Bad(f"{where}: expected 256 rows of 3 values")
    for t in rgb:
        for v in t:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 255:
                raise Bad(f"{where}: value {v!r} is not an integer in 0-255")


def load_json(path):
    try:
        d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        name, rgb = d["name"], d["rgb"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Bad(f"{path}: not a table file ({exc!r})") from None
    check_rgb(rgb, str(path))
    return name, rgb


def load_csv(path):
    rows = []
    try:
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower() == "r,g,b":
                continue
            rows.append([int(x) for x in line.split(",")])
    except (OSError, ValueError) as exc:
        raise Bad(f"{path}: not a CSV table ({exc!r})") from None
    check_rgb(rows, str(path))
    return pathlib.Path(path).stem, rows


def _app(x):                      # Studio's appD: ((int) (x * 0xff)) & 0xff
    return int(x * 255) & 0xFF


def _factor(btype, left, mid, right, x):
    midn = (mid - left) / (right - left)
    pos = (x - left) / (right - left)
    f = 0.5 * (pos / midn) if pos <= midn else 0.5 * (pos - midn) / (1.0 - midn) + 0.5
    if btype == 0:
        return f
    if btype == 1:                # curved; the Java uses the absolute middle stop here, so does this port
        return math.pow(pos, math.log(0.5) / math.log(mid))
    if btype == 2:
        return (math.sin(-math.pi / 2 + math.pi * f) + 1) / 2
    if btype == 3:
        return math.sqrt(1 - (f - 1) * (f - 1))
    if btype == 4:
        return 1 - math.sqrt(1 - f * f)
    raise Bad(f"unknown blending type {btype}")


def ggr_name(stem):
    m = re.fullmatch(r"AIA(\d+)", stem)
    return "sdoaia" + m.group(1) if m else stem


def load_ggr_text(text, where):
    lines = text.splitlines()
    if len(lines) < 4 or lines[0] != "GIMP Gradient" or not lines[1].startswith("Name: "):
        raise Bad(f"{where}: not a GIMP gradient")
    try:
        n = int(lines[2])
        segs = []
        for ln in lines[3:3 + n]:
            t = ln.split(" ")
            if len(t) not in (13, 15):
                raise Bad(f"{where}: bad segment line")
            segs.append(([float(v) for v in t[:11]], int(t[11]), int(t[12])))
        rgb = []
        for i in range(256):
            x = i / 255.0
            for v, btype, bcolor in segs:
                if v[0] <= x <= v[2]:
                    if bcolor != 0:
                        raise Bad(f"{where}: HSV segment blending is not ported (UNCHECKED)")
                    f = _factor(btype, v[0], v[1], v[2], x)
                    rgb.append([_app(v[3] + (v[7] - v[3]) * f), _app(v[4] + (v[8] - v[4]) * f),
                                _app(v[5] + (v[9] - v[5]) * f)])
                    break
            else:
                raise Bad(f"{where}: no segment covers {x}")
    except (ValueError, ZeroDivisionError) as exc:
        raise Bad(f"{where}: unreadable gradient ({exc!r})") from None
    return lines[1][6:], rgb


def load_ggr(path):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise Bad(f"{path}: {exc}") from None
    _, rgb = load_ggr_text(text, str(path))
    return ggr_name(pathlib.Path(path).stem), rgb


def load_sunpy():
    try:
        import numpy as np
        import sunpy.visualization.colormaps as cm
    except ImportError as exc:
        raise SystemExit(f"diff_luts: UNCHECKED, sunpy or numpy is not installed ({exc})")
    for key in sorted(cm.cmlist):
        rgba = cm.cmlist[key](np.arange(256), bytes=True)
        yield key, [[int(v) for v in row[:3]] for row in rgba]


def load_sunback(root):
    try:
        import importlib.util
        import astropy.units as u
        import numpy as np
        path = pathlib.Path(root).expanduser() / "sunback" / "science" / "color_tables.py"
        spec = importlib.util.spec_from_file_location("sunback_color_tables", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except (ImportError, OSError, AssertionError) as exc:
        raise SystemExit(f"diff_luts: UNCHECKED, cannot load sunback's color_tables.py ({exc!r})")
    for wave in sorted(int(k.value) for k in mod.aia_wave_dict):
        rgba = mod.aia_color_table(wave * u.angstrom)(np.arange(256), bytes=True)
        yield "sdoaia%d" % wave, [[int(v) for v in row[:3]] for row in rgba]


def candidates(spec):
    """Yield (label, name, rgb) or (label, None, reason) for a file that cannot be judged."""
    if spec == "sunpy:":
        for name, rgb in load_sunpy():
            yield "sunpy", name, rgb
        return
    if spec.startswith("sunback:"):
        for name, rgb in load_sunback(spec[len("sunback:"):]):
            yield "sunback", name, rgb
        return
    p = pathlib.Path(spec).expanduser()
    files = sorted(q for q in p.iterdir() if q.suffix in (".json", ".csv", ".ggr")) if p.is_dir() else [p]
    loaders = {".json": load_json, ".csv": load_csv, ".ggr": load_ggr}
    for q in files:
        try:
            name, rgb = loaders[q.suffix](q)
        except KeyError:
            raise Bad(f"{q}: unsupported file type") from None
        except Bad as exc:
            yield str(q), None, str(exc)
            continue
        yield str(q), name, rgb


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", required=True, help="folder of reference <name>.json tables")
    ap.add_argument("--candidate", required=True, help="folder, file, sunpy: or sunback:<root>")
    ap.add_argument("--tol", type=int, default=1, help="largest allowed channel difference (default 1)")
    args = ap.parse_args(argv)
    ref = {}
    try:
        for q in sorted(pathlib.Path(args.ref).expanduser().glob("*.json")):
            name, rgb = load_json(q)
            ref[name] = rgb
        if not ref:
            raise Bad(f"{args.ref}: no reference tables")
        compared = over = 0
        for label, name, rgb in candidates(args.candidate):
            if name is None:
                print(f"UNCHECKED {label}: {rgb}")
                continue
            if name not in ref:
                print(f"NOREF {name}")
                continue
            d = max(abs(a - b) for ra, rb in zip(ref[name], rgb) for a, b in zip(ra, rb))
            status = "OK" if d <= args.tol else "OVER"
            compared += 1
            over += status == "OVER"
            print(f"{name} maxdiff={d} {status}")
    except Bad as exc:
        print(f"diff_luts: {exc}", file=sys.stderr)
        return 2
    print(f"diff_luts: {compared} compared, {over} over tol")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
