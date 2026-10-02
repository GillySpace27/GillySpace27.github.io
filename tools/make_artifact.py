#!/usr/bin/env python3
"""Stage the files GitHub Pages will serve and write build.json (WS-9).

  python3 tools/make_artifact.py --content DIR --out DIR [--ref REF] [--now YYYY-MM-DDTHH:MM:SSZ]

--content is a git checkout of the commit to publish (its HEAD). Only tracked
files are staged ("git archive"), minus every path with a component that starts
with a dot or an underscore (.github/, .mailmap, .editorconfig, .gitattributes,
.nojekyll, _*.scss, ...) and minus __pycache__ and *.pyc: the branch source never
served them under Jekyll. The artifact is not run through Jekyll, so .nojekyll is
not needed here. Refuses a tree without CNAME,
google690400622efc7ebc.html or index.html, and an --out that is not empty.
Writes <out>/build.json and prints it. Never writes inside --content.
Standard library only; no tarfile extract filters, so it runs on Python 3.9.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile

# Never published: a path component starting with "." or "_" (Jekyll's own rule
# on the branch source), and Python build output.
HIDDEN_PREFIXES = (".", "_")
REQUIRED = ("CNAME", "google690400622efc7ebc.html", "index.html")
STAMP_RE = re.compile(r"/assets/site\.css\?v=(\d{12})\b")
NOW_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class ArtifactError(Exception):
    pass


def git(content, *args) -> bytes:
    r = subprocess.run(["git", "-C", str(content), *args], capture_output=True)
    if r.returncode:
        raise ArtifactError(f"git {' '.join(args)} failed in {content}: {r.stderr.decode().strip()}")
    return r.stdout


def head_sha(content) -> str:
    return git(content, "rev-parse", "HEAD").decode().strip()


def tracked(content) -> list:
    return [p for p in git(content, "ls-files", "-z").decode().split("\0") if p]


def build_json(content, ref: str = "", now: str = None) -> dict:
    """The receipt. Read from the commit (git show), not the working tree."""
    sha = head_sha(content)
    index = git(content, "show", "HEAD:index.html").decode("utf-8", errors="replace")
    m = STAMP_RE.search(index)
    when = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"commit": sha, "ref": ref or sha, "stamp": m.group(1) if m else "unstamped", "built_utc": when}


def skipped(name: str) -> bool:
    parts = [p for p in name.split("/") if p]
    return any(p.startswith(HIDDEN_PREFIXES) or p == "__pycache__" for p in parts) or name.endswith(".pyc")


def stage(content, out) -> int:
    out = pathlib.Path(out)
    files = set(tracked(content))
    missing = [p for p in REQUIRED if p not in files]
    if missing:
        raise ArtifactError("tree lacks " + ", ".join(missing))
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ArtifactError(f"{out} is not empty")
    proc = subprocess.Popen(["git", "-C", str(content), "archive", "--format=tar", "HEAD"],
                            stdout=subprocess.PIPE)
    n = 0
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
        for m in tf:
            if skipped(m.name):
                continue
            dest = out / m.name
            if m.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            elif m.isreg():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tf.extractfile(m).read())
                os.chmod(dest, m.mode & 0o777)
                n += 1
            else:
                raise ArtifactError(f"{m.name}: only regular files are published")
    if proc.wait():
        raise ArtifactError("git archive failed")
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Stage the Pages artifact and write build.json.")
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--ref", default="")
    ap.add_argument("--now", default=None, help="UTC time to record, YYYY-MM-DDTHH:MM:SSZ (tests)")
    a = ap.parse_args(argv)
    if a.now and not NOW_RE.fullmatch(a.now):
        ap.error("--now must look like 2026-10-01T18:00:00Z")
    try:
        info = build_json(a.content, a.ref, a.now)
        n = stage(a.content, a.out)
    except ArtifactError as e:
        print(f"make_artifact: REFUSE: {e}", file=sys.stderr)
        return 1
    (a.out / "build.json").write_text(json.dumps(info) + "\n", encoding="utf-8")
    print(json.dumps(info))
    print(f"make_artifact: staged {n} files in {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
