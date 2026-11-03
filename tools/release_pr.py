#!/usr/bin/env python3
"""Turn a feed record a release script just wrote into a pull request on gilly.space (WS-22).

python3 tools/release_pr.py --product heliofits-studio --version 0.8.9 [--build N] [--dry-run] [--yes]

The Studio and Peek release scripts append their record to heliosoftware/feed/<product>.json in
the local Website checkout ($SITE) and rebuild What's new there. This script takes that record and,
in a temporary worktree on a fresh origin/master, appends the same record, runs build_feed.py and,
for Studio, pin_studio_fallback.py --from-github. check_site.py fails a feed that is newer than the
Studio page's fallback links, so a Studio record cannot ship before the pin, and the pin refuses
until package.yml has attached the Windows and Linux packages: run this again then, or let
release-sync.yml open the same pull request. Then it runs check_site.py, commits on branch
release/<product>-<version>, pushes the branch and opens a pull request. Merging it is the deploy,
and that stays Gilly's click. The local checkout is read, never changed.

Pushing asks y/N on a terminal; --yes skips the question (only for a person who has said yes).
Without a terminal and without --yes it stops before the push and prints what to run.
Exit 0 PR opened (or nothing to do), 1 refused or failed, 2 stopped before the push.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEED = ROOT / "heliosoftware" / "feed"
sys.path.insert(0, str(FEED))
import append_record as ar  # noqa: E402

PRODUCTS = {"heliofits-studio", "heliofits", "heliogram", "sunback"}


class PRError(Exception):
    pass


def find_record(feed_dir: pathlib.Path, product: str, version: str, build: int | None = None) -> dict:
    """The record for (version, build) in feed_dir/<product>.json; the last match when build is None."""
    path = feed_dir / f"{product}.json"
    if not path.exists():
        raise PRError(f"{path} does not exist; run the release script's feed step first")
    data = json.loads(path.read_text(encoding="utf-8"))
    hits = [r for r in data.get("records", [])
            if r.get("version") == version and (build is None or r.get("build") == build)]
    if not hits:
        raise PRError(f"{product} {version} is not in {path}; run the release script's feed step first")
    rec = hits[-1]
    errs = ar.validate_record(rec)
    if errs:
        raise PRError("the local record is invalid: " + "; ".join(errs))
    return rec


def on_master(product: str, rec: dict) -> bool:
    """True when origin/master's feed already holds this (version, build)."""
    r = git("show", f"origin/master:heliosoftware/feed/{product}.json", check=False, capture=True)
    if r.returncode != 0:
        return False
    return any(o.get("version") == rec["version"] and o.get("build") == rec.get("build")
               for o in json.loads(r.stdout).get("records", []))


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def refresh_version_text(root: pathlib.Path, product: str, version: str) -> list[str]:
    """Raise every static <span data-release="product" data-release-field="version">X</span> below
    version to version, in tracked .html pages. Returns the pages changed. Studio is left to
    pin_studio_fallback.py, which also moves its download links."""
    rx = re.compile(r'(data-release="%s" data-release-field="version">)(\d+(?:\.\d+)*)(<)' % re.escape(product))
    files = git("ls-files", "*.html", cwd=root, capture=True).stdout.split()
    changed = []
    for rel in files:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        new = rx.sub(lambda m: m.group(1) + (version if _vt(m.group(2)) < _vt(version) else m.group(2)) + m.group(3), text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(rel)
    return changed


def branch_name(product: str, rec: dict) -> str:
    build = f"-build.{rec['build']}" if rec.get("build") is not None else ""
    return f"release/{product}-{rec['version']}{build}"


def git(*args, cwd=ROOT, check=True, capture=False):
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=capture)
    if check and r.returncode != 0:
        raise PRError(f"git {' '.join(args)} failed ({r.returncode}): {(r.stderr or '').strip()[-300:]}")
    return r


def run(cmd, cwd, check=True):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, text=True)
    if check and r.returncode != 0:
        raise PRError(f"{' '.join(cmd)} exited {r.returncode}")
    return r.returncode


def confirm_push(branch: str, yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        return False
    ans = input(f"Push {branch} to gilly.space and open a pull request? [y/N] ")
    return ans.strip().lower() in ("y", "yes")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--product", required=True, choices=sorted(PRODUCTS))
    ap.add_argument("--version", required=True)
    ap.add_argument("--build", type=int)
    ap.add_argument("--dry-run", action="store_true", help="prepare and check the branch; push nothing")
    ap.add_argument("--yes", action="store_true", help="push without asking (Gilly said yes)")
    a = ap.parse_args(argv)
    try:
        rec = find_record(FEED, a.product, a.version, a.build)
        branch = branch_name(a.product, rec)
        git("fetch", "origin", "master")
        if on_master(a.product, rec):
            print(f"release_pr: {a.product} {a.version} is already on master; nothing to do")
            return 0
        if git("ls-remote", "--exit-code", "--heads", "origin", branch, check=False, capture=True).returncode == 0:
            print(f"release_pr: {branch} is already on origin; its pull request is the one to merge")
            return 0
        with tempfile.TemporaryDirectory(prefix="release-pr-") as tmp:
            wt = pathlib.Path(tmp) / "site"
            if git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False, capture=True).returncode == 0:
                raise PRError(f"local branch {branch} already exists; push it (see its log) or rename it")
            git("worktree", "add", "-q", "--detach", str(wt), "origin/master")
            try:
                code = ar.append(wt / "heliosoftware" / "feed", a.product, rec)
                if code != 0:
                    raise PRError(f"append_record returned {code}")
                run([sys.executable, "heliosoftware/feed/build_feed.py"], wt)
                if a.product == "heliofits-studio":
                    if run([sys.executable, "tools/pin_studio_fallback.py", "--from-github"], wt, check=False):
                        raise PRError("the Studio fallback links cannot be pinned yet (package.yml attaches the"
                                      " Windows and Linux packages after publish). Run this again when it has"
                                      " finished, or let release-sync.yml open the pull request; nothing was committed")
                else:
                    for rel in refresh_version_text(wt, a.product, rec["version"]):
                        print(f"release_pr: static version text in {rel} raised to {rec['version']}")
                run([sys.executable, "tools/check_site.py"], wt)
                git("switch", "-q", "-c", branch, cwd=wt)
                git("add", "-A", cwd=wt)
                title = f"Feed: {ar.PRODUCTS[a.product][0]} {rec['version']}"
                git("commit", "-q", "-m", f"{title}\n\nWritten by tools/release_pr.py from the release script's feed record.", cwd=wt)
                if a.dry_run or not confirm_push(branch, a.yes):
                    print(f"release_pr: stopped before the push. The commit is on local branch {branch}."
                          f" To publish it: git push -u origin {branch} && gh pr create --base master --head {branch} --fill")
                    return 2
                git("push", "-u", "origin", branch, cwd=wt)
                body = (f"{title}, appended by the release script and rebuilt with build_feed.py.\n\n"
                        f"Release: {rec['url']}\n\nMerging publishes gilly.space.")
                run(["gh", "pr", "create", "--repo", "GillySpace27/GillySpace27.github.io", "--base", "master",
                     "--head", branch, "--title", title, "--body", body], wt)
                return 0
            finally:
                git("worktree", "remove", "--force", str(wt), check=False)
    except PRError as e:
        print(f"release_pr: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
