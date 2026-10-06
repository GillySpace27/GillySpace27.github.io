#!/usr/bin/env python3
"""Orrery tracker for gilly.space (suite SU-5).

Wraps tools/check_site.py (WS-2) and its --online mode (SU-10): one milestone
for the offline checks, one for the live follow-the-redirect checks. A run that
cannot answer (script missing, --online not available) is UNCHECKED, not done.

  python3 tools/site_status.py [--json] [--emit]
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_SITE = os.path.join(ROOT, "tools", "check_site.py")
NAME = "site-gilly-space"
TITLE = "gilly.space site checks"
SUMMARY = re.compile(r"^check_site: (\d+) failures, (\d+) warnings, (\d+) known$", re.M)
MILESTONES = [
    ("offline", "Offline site check passes", []),
    ("online", "Live short links follow to their targets", ["--online"]),
]


def run_check(extra, timeout=600):
    """(exit code or None, combined output)."""
    if not os.path.exists(CHECK_SITE):
        return None, "tools/check_site.py missing (WS-2 not landed)"
    try:
        p = subprocess.run([sys.executable, CHECK_SITE] + extra, cwd=ROOT,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout} s"
    return p.returncode, p.stdout + p.stderr


def verdict(rc, out):
    """(done, note); done None means UNCHECKED."""
    if rc is None:
        return None, out
    if "unrecognized arguments: --online" in out:
        return None, "--online not available yet (SU-10)"
    found = list(SUMMARY.finditer(out))
    if not found:
        return None, f"exited {rc} without a summary line"
    f, w, k = found[-1].groups()
    note = f"{f} failures, {w} warnings, {k} known"
    if rc == 0:
        return True, note
    first = next((ln for ln in out.splitlines() if ln.startswith("FAIL ")), "")
    return False, note + (f"; first: {first[:160]}" if first else "")


def snapshot(results, now):
    milestones = []
    for key, label, extra in MILESTONES:
        done, note = results[key]
        milestones.append({"key": key, "label": label, "done": done is True,
                           "note": note if done is not None else f"UNCHECKED: {note}",
                           "gated": False, "how_kind": "shell",
                           "how": " ".join(["python3", "tools/check_site.py"] + extra)})
    states = [results[k][0] for k, _, _ in MILESTONES]
    verdict_word = "FAIL" if False in states else ("UNCHECKED" if None in states else "PASS")
    return {"name": NAME, "title": TITLE, "checked_at": now.isoformat(timespec="seconds"),
            "complete": sum(1 for m in milestones if m["done"]), "total": len(milestones),
            "next": next((m["label"] for m in milestones if not m["done"]), None),
            "external_state": verdict_word, "external_label": "check_site.py verdict",
            "milestones": milestones}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Orrery tracker for gilly.space.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--emit", action="store_true",
                    help="also write ~/.claude/runbooks/state/site-gilly-space.json (a cache, never truth)")
    args = ap.parse_args(argv)
    now = datetime.datetime.now(datetime.timezone.utc)
    snap = snapshot({key: verdict(*run_check(extra)) for key, _, extra in MILESTONES}, now)
    if args.json:
        print(json.dumps(snap, indent=2))
    else:
        print(f"{TITLE}: {snap['complete']}/{snap['total']} ({snap['external_state']})")
        for m in snap["milestones"]:
            print(f"{'[x]' if m['done'] else '[ ]'} {m['label']}  ({m['note']})")
    if args.emit:
        d = os.path.expanduser("~/.claude/runbooks/state")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, NAME + ".json"), "w") as f:
            json.dump(snap, f, indent=2)
        print(f"(snapshot written to {d}/{NAME}.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
