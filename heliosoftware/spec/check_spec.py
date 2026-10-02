#!/usr/bin/env python3
"""Check vendored HelioSoftware spec copies for drift (suite SU-7). Standard library only.

  python3 check_spec.py [--spec-dir DIR] [--canonical FILE] PATH...

Each PATH is read and one of two markers is looked for.

1. A preamble block (agent files):
     <!-- heliosoftware-preamble v1 sha256=<64 hex> -->
     ...the bytes of heliosoftware/spec/agent-preamble.md...
     <!-- /heliosoftware-preamble -->
   OK when the bytes between the two marker lines hash to the stated value and,
   when a canonical copy is known, equal it. The canonical copy is --canonical
   FILE, else DIR/agent-preamble.md for --spec-dir DIR (default
   $HELIOSOFTWARE_SPEC_DIR).

2. A vendored header on line 1 (line 2 when line 1 starts with "#!"):
     <comment> heliosoftware-vendored: <label>:<path> sha256=<64 hex>
   where <comment> is "#", "//", ";" or "<!--". OK when the file with that one
   line removed hashes to the stated value and, when known, equals the canonical
   copy. The canonical copy is --canonical FILE, else, for label "Website" and a
   path under heliosoftware/spec/, the same path inside the spec dir.

Output per PATH: "OK <path>", "DRIFT <path>: <reason>", "NOMARKER <path>: ..." or
"UNREADABLE <path>: ...". Exit 0 when every PATH is OK, 1 when any is DRIFT, 2 when
any has no marker or cannot be read (2 wins over 1). With no spec dir and no
--canonical, only self-consistency is checked.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import sys

PREAMBLE_OPEN = re.compile(rb"^<!-- heliosoftware-preamble v1 sha256=([0-9a-f]{64}) -->$")
PREAMBLE_CLOSE = b"<!-- /heliosoftware-preamble -->"
VENDORED = re.compile(
    rb"^(?:#|//|;|<!--)\s*heliosoftware-vendored: ([A-Za-z0-9_-]+):(\S+) sha256=([0-9a-f]{64})(?:\s*-->)?\s*$")
SPEC_PREFIX = "heliosoftware/spec/"
PREAMBLE_FILE = "agent-preamble.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def eol(line: bytes) -> bytes:
    return line.rstrip(b"\r\n")


def read_canonical(path: pathlib.Path, what: str):
    """(bytes, None) or (None, reason)."""
    try:
        return path.read_bytes(), None
    except OSError:
        return None, f"canonical file not found: {what}"


def preamble_canonical(spec_dir, canonical_file):
    if canonical_file:
        return read_canonical(pathlib.Path(canonical_file), canonical_file)
    if spec_dir:
        return read_canonical(spec_dir / PREAMBLE_FILE, f"spec dir has no {PREAMBLE_FILE}")
    return None, None


def vendored_canonical(label, path, spec_dir, canonical_file):
    if canonical_file:
        return read_canonical(pathlib.Path(canonical_file), canonical_file)
    if spec_dir and label == "Website" and path.startswith(SPEC_PREFIX):
        rest = path[len(SPEC_PREFIX):]
        if ".." in pathlib.PurePosixPath(rest).parts:
            return None, f"refusing a path with '..': {path}"
        return read_canonical(spec_dir / rest, f"spec dir has no {rest}")
    return None, None


def check_preamble(lines, spec_dir, canonical_file):
    """None when there is no preamble marker, "" when OK, else the drift reason."""
    opens = [i for i, ln in enumerate(lines) if PREAMBLE_OPEN.match(eol(ln))]
    if not opens:
        return None
    closes = [i for i, ln in enumerate(lines) if eol(ln) == PREAMBLE_CLOSE]
    if len(opens) != 1 or len(closes) != 1 or closes[0] < opens[0]:
        return f"{len(opens)} opening and {len(closes)} closing markers, expected 1 and 1"
    stated = PREAMBLE_OPEN.match(eol(lines[opens[0]])).group(1).decode()
    body = b"".join(lines[opens[0] + 1:closes[0]])
    if sha(body) != stated:
        return "block text does not hash to the sha256 in its opening marker"
    canon, err = preamble_canonical(spec_dir, canonical_file)
    if err:
        return err
    if canon is not None and canon != body:
        return f"block text differs from the canonical {PREAMBLE_FILE}"
    return ""


def check_vendored(lines, spec_dir, canonical_file):
    """None when there is no vendored header, "" when OK, else the drift reason."""
    idx = 1 if lines and lines[0].startswith(b"#!") else 0
    if idx >= len(lines):
        return None
    m = VENDORED.match(eol(lines[idx]))
    if not m:
        return None
    label, path, stated = m.group(1).decode(), m.group(2).decode(), m.group(3).decode()
    body = b"".join(lines[:idx] + lines[idx + 1:])
    if sha(body) != stated:
        return "body does not hash to the sha256 in its vendored header"
    canon, err = vendored_canonical(label, path, spec_dir, canonical_file)
    if err:
        return err
    if canon is not None and canon != body:
        return f"body differs from the canonical {label}:{path}"
    return ""


def check_path(path, spec_dir, canonical_file):
    """(status, reason) with status OK, DRIFT, NOMARKER or UNREADABLE."""
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError as err:
        return "UNREADABLE", str(err)
    lines = data.splitlines(keepends=True)
    for check in (check_preamble, check_vendored):
        reason = check(lines, spec_dir, canonical_file)
        if reason is None:
            continue
        return ("OK", "") if reason == "" else ("DRIFT", reason)
    return "NOMARKER", "neither a preamble block nor a vendored header"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check vendored HelioSoftware spec copies for drift.")
    ap.add_argument("--spec-dir", default=os.environ.get("HELIOSOFTWARE_SPEC_DIR"),
                    help="a local Website heliosoftware/spec checkout (default: $HELIOSOFTWARE_SPEC_DIR)")
    ap.add_argument("--canonical", help="compare every PATH with this file instead of the spec dir")
    ap.add_argument("paths", nargs="+", metavar="PATH")
    args = ap.parse_args(argv)
    spec_dir = pathlib.Path(args.spec_dir) if args.spec_dir else None
    worst = 0
    for path in args.paths:
        status, reason = check_path(path, spec_dir, args.canonical)
        if status == "OK":
            print(f"OK {path}")
        elif status == "DRIFT":
            print(f"DRIFT {path}: {reason}")
            worst = max(worst, 1)
        else:
            print(f"{status} {path}: {reason}")
            worst = 2
    return worst


if __name__ == "__main__":
    sys.exit(main())
