#!/usr/bin/env python3
"""After a push Gilly approved: wait until the live site serves this checkout, then probe it once (WS-7).

python3 tools/verify_deploy.py --paths PATH [PATH ...] [--timeout 600] [--interval 15]
                               [--base URL] [--root PATH]

PATH is repo-relative. Prints PASS (exit 0), FAIL: <reason> (exit 1: converged, a
probe failed) or UNCHECKED: <reason> (exit 3: did not converge). Never silent.
Read-only: GET requests with a cache-busting query.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import watch  # noqa: E402


def live_url(base, rel):
    rel = rel.lstrip("/")
    if rel == "index.html":
        return base + "/"
    if rel.endswith("/index.html"):
        return f"{base}/{rel[:-len('index.html')]}"
    return f"{base}/{rel}"


def pending(base, root, paths):
    """Paths whose live bytes differ from the checkout, with the HTTP status seen."""
    out = []
    for rel in paths:
        want = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        status, _, body, _ = watch.fetch(f"{live_url(base, rel)}?cb={time.time_ns()}")
        if status != 200 or hashlib.sha256(body).hexdigest() != want:
            out.append(f"{rel} (HTTP {status})")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wait for a Pages deploy to converge, then run watch.py once.")
    ap.add_argument("--paths", nargs="+", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--base", default=watch.SITE_ORIGIN)
    ap.add_argument("--root", type=pathlib.Path, default=TOOLS.parent)
    a = ap.parse_args(argv)
    base = a.base.rstrip("/")
    missing = [p for p in a.paths if not (a.root / p).is_file()]
    if missing:
        print(f"UNCHECKED: not files in this checkout: {', '.join(missing)}")
        return 3
    deadline = time.monotonic() + a.timeout
    while True:
        left = pending(base, a.root, a.paths)
        if not left:
            break
        if time.monotonic() >= deadline:
            print(f"UNCHECKED: live site did not converge within {a.timeout} s: {', '.join(left)}")
            return 3
        time.sleep(a.interval)
    fails = [r for r in watch.run_probes(base, a.root) if r.level == "FAIL"]
    if fails:
        print(watch.format_report(fails))
        print(f"FAIL: {len(fails)} probe result(s) failed after {len(a.paths)} path(s) converged")
        return 1
    print(f"PASS: {len(a.paths)} path(s) live and every probe passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
