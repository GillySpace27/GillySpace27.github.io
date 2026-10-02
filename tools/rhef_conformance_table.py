#!/usr/bin/env python3
"""Turn RHEF-CONFORMANCE runner lines into a markdown table (suite SU-8).

  <runner output> | python3 tools/rhef_conformance_table.py
  python3 tools/rhef_conformance_table.py run-a.txt run-b.txt
  python3 tools/rhef_conformance_table.py --into heliosoftware/spec/rhef/conventions.md run-a.txt ...

Reads lines in the format the conformance runners print (RH-6):
  RHEF-CONFORMANCE impl=<id> bundle=<v> case=<case> convention=<id> max_abs_diff=<%.3e|nan> result=<PASS|REPORT|FAIL>
  RHEF-CONFORMANCE impl=<id> summary pass=<n> report=<n> fail=<n> mode=<report|enforce>
Any other line is ignored. One row per "case (convention)", one column per implementation,
a final "mode" row. Exit 1 when there are no result lines, when the lines come from more than
one bundle version, or when --into finds other than one begin and one end marker.
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys

CASE_LINE = re.compile(r"^RHEF-CONFORMANCE impl=(\S+) bundle=(\S+) case=(\S+) convention=(\S+) "
                       r"max_abs_diff=(\S+) result=(PASS|REPORT|FAIL)\s*$")
SUMMARY_LINE = re.compile(r"^RHEF-CONFORMANCE impl=(\S+) summary pass=\d+ report=\d+ fail=\d+ "
                          r"mode=(report|enforce)\s*$")
BEGIN = "<!-- conformance-table begin -->"
END = "<!-- conformance-table end -->"


def parse(lines):
    cells: dict = {}
    modes: dict = {}
    bundles: set = set()
    for line in lines:
        m = CASE_LINE.match(line)
        if m:
            impl, bundle, case, convention, diff, result = m.groups()
            cells.setdefault((case, convention), {})[impl] = f"{diff} {result}"
            bundles.add(bundle)
            continue
        m = SUMMARY_LINE.match(line)
        if m:
            modes[m.group(1)] = m.group(2)
    return cells, modes, bundles


def render(cells, modes, bundles) -> str:
    impls = sorted({i for row in cells.values() for i in row})
    out = [f"Bundle {next(iter(bundles))}.", "", "| Case (convention) | " + " | ".join(impls) + " |",
           "|---|" + "---|" * len(impls)]
    for case, convention in sorted(cells):
        row = cells[(case, convention)]
        out.append(f"| {case} ({convention}) | " + " | ".join(row.get(i, "-") for i in impls) + " |")
    out.append("| mode | " + " | ".join(modes.get(i, "-") for i in impls) + " |")
    return "\n".join(out)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="RHEF-CONFORMANCE lines to a markdown table.")
    ap.add_argument("files", nargs="*", metavar="FILE", help="runner output files (default: stdin)")
    ap.add_argument("--into", metavar="PAGE", help="replace the region between the table markers in PAGE")
    args = ap.parse_args(argv)
    lines: list = []
    if args.files:
        for name in args.files:
            with open(name, encoding="utf-8") as fh:
                lines.extend(fh.read().splitlines())
    else:
        lines = sys.stdin.read().splitlines()
    cells, modes, bundles = parse(lines)
    if not cells:
        print("no RHEF-CONFORMANCE lines")
        return 1
    if len(bundles) > 1:
        print("mixed bundle versions: " + ", ".join(sorted(bundles)))
        return 1
    table = render(cells, modes, bundles)
    if not args.into:
        print(table)
        return 0
    with open(args.into, encoding="utf-8") as fh:
        text = fh.read()
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        print(f"{args.into}: expected exactly one begin and one end marker, in order")
        return 1
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    with open(args.into, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + BEGIN + "\n" + table + "\n" + END + tail)
    print(f"updated {args.into}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
