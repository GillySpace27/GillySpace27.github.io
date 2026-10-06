#!/usr/bin/env python3
"""Write or check SHA256SUMS for heliosoftware/spec/ (HelioSoftware suite, SU-7).

  python3 spec_sums.py --write      rewrite SHA256SUMS from the files on disk
  python3 spec_sums.py --check      exit 0 when every file matches, 1 otherwise
  python3 spec_sums.py --dir DIR    operate on DIR instead of this script's folder

Line format (what `shasum -a 256 -c SHA256SUMS` reads): 64 lowercase hex digits,
two spaces, the path relative to the folder with forward slashes, sorted by path.
Left out: SHA256SUMS itself, any .claude folder (Claude Code worktrees),
__pycache__ folders, *.pyc and .DS_Store.

--check prints one line per problem: MISMATCH <path> (content differs),
MISSING <path> (listed, not on disk) or EXTRA <path> (on disk, not listed).
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys

SUMS = "SHA256SUMS"
SKIP_DIRS = {".claude", "__pycache__"}
SKIP_NAMES = {".DS_Store"}
HEX = set("0123456789abcdef")


def file_hashes(root: pathlib.Path) -> dict[str, str]:
    """{relative posix path: sha256 hex} for every counted file under root."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            full = pathlib.Path(dirpath, name)
            rel = full.relative_to(root).as_posix()
            if rel == SUMS or name in SKIP_NAMES or name.endswith(".pyc"):
                continue
            out[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
    return out


def render(hashes: dict[str, str]) -> str:
    return "".join(f"{h}  {p}\n" for p, h in sorted(hashes.items()))


def parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        digest, sep, path = line.partition("  ")
        if not sep or len(digest) != 64 or not set(digest) <= HEX or not path:
            raise ValueError(f"{SUMS}:{n}: expected '<64 hex>  <path>'")
        if path in out:
            raise ValueError(f"{SUMS}:{n}: {path} listed twice")
        out[path] = digest
    return out


def check(root: pathlib.Path) -> list[str]:
    sums = root / SUMS
    if not sums.is_file():
        return [f"MISSING {SUMS}"]
    want = parse(sums.read_text(encoding="utf-8"))
    have = file_hashes(root)
    problems = []
    for path in sorted(set(want) | set(have)):
        if path not in have:
            problems.append(f"MISSING {path}")
        elif path not in want:
            problems.append(f"EXTRA {path}")
        elif want[path] != have[path]:
            problems.append(f"MISMATCH {path}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write or check SHA256SUMS for heliosoftware/spec/.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="rewrite SHA256SUMS")
    mode.add_argument("--check", action="store_true", help="verify SHA256SUMS")
    ap.add_argument("--dir", default=str(pathlib.Path(__file__).resolve().parent),
                    help="folder to operate on (default: this script's folder)")
    args = ap.parse_args(argv)
    root = pathlib.Path(args.dir)
    if args.write:
        hashes = file_hashes(root)
        with open(root / SUMS, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(hashes))
        print(f"spec_sums: wrote {len(hashes)} entries")
        return 0
    try:
        problems = check(root)
    except ValueError as err:
        print(f"ERROR {err}")
        return 1
    for line in problems:
        print(line)
    if problems:
        print(f"spec_sums: {len(problems)} problem(s)")
        return 1
    print(f"spec_sums: {len(file_hashes(root))} files match {SUMS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
