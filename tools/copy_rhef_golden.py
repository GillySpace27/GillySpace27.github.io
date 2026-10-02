#!/usr/bin/env python3
"""Copy a public subset of the RHEF golden bundle into heliosoftware/spec/rhef/ (suite SU-8).

  python3 tools/copy_rhef_golden.py --src <fastRHEF>/golden [--dest DIR] [--cases a,b,...]
                                    [--include-orhef] [--max-bytes N]
  python3 tools/copy_rhef_golden.py --verify [--dest DIR]

--src is the bundle written by fastRHEF `make golden`. Every file to copy is checked against
the sha256 in the bundle's manifest.json before anything is written. The manifest is copied
byte for byte to DEST/vectors.json and the files go to DEST/golden/<same relative path>.
Default cases: the four small 64 x 64 cases and the geometry case; the larger and the
data-derived cases stay private. Files named expected_oRHEF-2.0.* are withheld unless
--include-orhef (suite-decisions Q18). An existing file is never overwritten with different
bytes (CONFLICT), and a bundle_version different from the one already in DEST/vectors.json is
refused (NEW BUNDLE VERSION): a new version gets a new --dest and the old one stays.
--verify checks the published files against DEST/vectors.json (MISMATCH, EXTRA) and counts
the manifest entries that are not published. Exit 0 on success, 1 on any refusal or problem.
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT / "heliosoftware" / "spec" / "rhef"
PUBLIC_CASES = ("ties_zero_fill_64", "nan_holes_64", "negatives_64", "single_and_empty_annulus_64",
                "geometry_hpc_32")
TOP_LEVEL = ("README.md", "read_golden.py")
WITHHELD_PREFIX = "expected_oRHEF-2.0."
MAX_BYTES = 1_000_000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(raw: bytes) -> dict:
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest.get("files"), dict) or "bundle_version" not in manifest:
        raise ValueError("manifest.json lacks 'files' or 'bundle_version'")
    return manifest


def select(files: dict, cases: set, include_orhef: bool):
    chosen, withheld = [], []
    for path in sorted(files):
        if "/" not in path:
            if path in TOP_LEVEL:
                chosen.append(path)
            continue
        top, rest = path.split("/", 1)
        if top not in cases:
            continue
        if not include_orhef and rest.startswith(WITHHELD_PREFIX):
            withheld.append(path)
            continue
        chosen.append(path)
    return chosen, withheld


def copy(src: pathlib.Path, dest: pathlib.Path, cases: list, include_orhef: bool, max_bytes: int) -> int:
    try:
        raw = (src / "manifest.json").read_bytes()
        manifest = load_manifest(raw)
    except (OSError, ValueError) as err:
        print(f"ERROR cannot read {src / 'manifest.json'}: {err}")
        return 1
    files, version = manifest["files"], manifest["bundle_version"]
    unknown = [c for c in cases if not any(p.startswith(c + "/") for p in files)]
    if unknown:
        print("NOT IN BUNDLE " + ", ".join(unknown))
        return 1
    chosen, withheld = select(files, set(cases), include_orhef)
    payload: dict[str, bytes] = {}
    total = 0
    for rel in chosen:
        try:
            data = (src / rel).read_bytes()
        except OSError as err:
            print(f"ERROR cannot read {rel}: {err}")
            return 1
        if sha(data) != files[rel]:
            print(f"CORRUPT {rel}: sha256 differs from manifest.json")
            return 1
        payload[rel] = data
        total += len(data)
    if total > max_bytes:
        print(f"TOO LARGE {total} bytes exceeds --max-bytes {max_bytes}")
        return 1
    vec = dest / "vectors.json"
    if vec.exists():
        try:
            published = json.loads(vec.read_text(encoding="utf-8")).get("bundle_version")
        except ValueError:
            published = None
        if published != version:
            print(f"NEW BUNDLE VERSION {version} (published: {published}); use a new --dest")
            return 1
        if vec.read_bytes() != raw:
            print("CONFLICT vectors.json differs from this bundle's manifest.json")
            return 1
    for rel, data in payload.items():
        target = dest / "golden" / rel
        if target.exists() and target.read_bytes() != data:
            print(f"CONFLICT {rel}")
            return 1
    for rel, data in payload.items():
        target = dest / "golden" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    vec.parent.mkdir(parents=True, exist_ok=True)
    vec.write_bytes(raw)
    in_bundle = sorted({p.split("/", 1)[0] for p in files if "/" in p})
    private = [c for c in in_bundle if c not in cases]
    lines = [
        f"fastRHEF {manifest.get('generator_git_sha', 'unknown')} bundle {version} manifest-sha256 {sha(raw)}",
        "cases: " + ",".join(sorted(cases)),
        "withheld: " + ("none" if include_orhef else "expected_oRHEF-2.0.* (suite-decisions Q18)"),
        "not published: " + (",".join(private) if private else "none"),
    ]
    (dest / "golden" / "SOURCE.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"copied {len(payload)} files ({total} bytes) from bundle {version}; "
          f"withheld {len(withheld)}; {len(private)} cases not published")
    return 0


def verify(dest: pathlib.Path) -> int:
    vec = dest / "vectors.json"
    gold = dest / "golden"
    if not vec.is_file():
        print("MISSING vectors.json")
        return 1
    if not gold.is_dir():
        print("MISSING golden/")
        return 1
    try:
        files = load_manifest(vec.read_bytes())["files"]
    except (OSError, ValueError) as err:
        print(f"ERROR cannot read vectors.json: {err}")
        return 1
    bad = 0
    present = set()
    for path in sorted(p for p in gold.rglob("*") if p.is_file()):
        rel = path.relative_to(gold).as_posix()
        if rel == "SOURCE.txt":
            continue
        present.add(rel)
        if rel not in files:
            print(f"EXTRA {rel}")
            bad += 1
        elif sha(path.read_bytes()) != files[rel]:
            print(f"MISMATCH {rel}")
            bad += 1
    absent = len(set(files) - present)
    print(f"copy_rhef_golden: {len(present)} files checked, {bad} problem(s); {absent} manifest files not published")
    return 1 if bad else 0


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Copy a public subset of the RHEF golden bundle.")
    ap.add_argument("--src", help="fastRHEF golden/ folder (contains manifest.json)")
    ap.add_argument("--dest", default=str(DEFAULT_DEST), help="default: heliosoftware/spec/rhef")
    ap.add_argument("--cases", default=",".join(PUBLIC_CASES), help="comma list of case folders to publish")
    ap.add_argument("--include-orhef", action="store_true", help="also copy expected_oRHEF-2.0.* (needs Gilly's yes)")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    ap.add_argument("--verify", action="store_true", help="check the published copy against vectors.json")
    args = ap.parse_args(argv)
    dest = pathlib.Path(args.dest)
    if args.verify:
        return verify(dest)
    if not args.src:
        ap.error("--src is required unless --verify")
    cases = [c for c in args.cases.split(",") if c]
    return copy(pathlib.Path(args.src), dest, cases, args.include_orhef, args.max_bytes)


if __name__ == "__main__":
    sys.exit(main())
