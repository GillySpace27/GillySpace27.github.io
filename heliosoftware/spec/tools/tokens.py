#!/usr/bin/env python3
"""Check or write the HelioSoftware family colour tokens in CSS files (suite SU-20).

  python3 tokens.py --check FILE...    exit 0 when every file matches tokens.json, 1 on drift
  python3 tokens.py --write FILE...    set each file's token values from tokens.json
  --spec PATH                          read another tokens.json (default: ../tokens.json)

tokens.json (one folder up) is the single source. Each CSS file carries one block between

  /* heliosoftware-tokens v1 begin */
  ...
  /* heliosoftware-tokens v1 end */

and only that block is read or changed. Inside it, the rule for the light selector
(tokens.json "selectors.light", ":root" on gilly.space) holds the "light" and "layout"
tokens, and the rule for the dark selector holds the "dark" tokens. Comments in the block
are ignored when comparing.

--check prints one line per problem:
  DRIFT <file> <selector> <name>: <found> != <expected>
  MISSING <file> <selector> <name>       (a token the file does not declare)
  EXTRA <file> <selector> <name>         (declared in the block, not in tokens.json)
  NOBLOCK <file>                         (no marked block, or more than one)
--write changes values in place, keeps comments and line layout, and adds missing tokens at
the end of their rule. It never removes a declaration: an EXTRA stays and keeps --check red
until tokens.json gains it or a person removes it.

Exit codes: 0 clean, 1 drift, 2 usage or a file without a block. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

BEGIN = "/* heliosoftware-tokens v1 begin */"
END = "/* heliosoftware-tokens v1 end */"
DEFAULT_SPEC = pathlib.Path(__file__).resolve().parent.parent / "tokens.json"

COMMENT = re.compile(r"/\*.*?\*/", re.S)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DECL = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def norm(value: str) -> str:
    return " ".join(value.split())


def expected(spec: dict) -> dict[str, dict[str, str]]:
    sel = spec["selectors"]
    light = dict(spec["light"])
    light.update(spec.get("layout", {}))
    return {sel["light"]: light, sel["dark"]: dict(spec["dark"])}


def block_span(text: str) -> tuple[int, int] | None:
    """(start, end) of the text between the markers, or None unless exactly one block."""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        return None
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    return (start, end) if start <= end else None


def parse(block: str) -> dict[str, dict[str, str]]:
    """{selector: {name: value}} for the rules in a block, comments removed."""
    rules: dict[str, dict[str, str]] = {}
    for m in RULE.finditer(COMMENT.sub("", block)):
        decls = rules.setdefault(norm(m.group(1)), {})
        for d in DECL.finditer(m.group(2)):
            decls[d.group(1)] = norm(d.group(2))
    return rules


def problems(path: str, text: str, want: dict[str, dict[str, str]]) -> list[str]:
    span = block_span(text)
    if span is None:
        return [f"NOBLOCK {path}"]
    have = parse(text[span[0]:span[1]])
    out: list[str] = []
    for sel, tokens in want.items():
        found = have.get(sel, {})
        for name, value in tokens.items():
            if name not in found:
                out.append(f"MISSING {path} {sel} {name}")
            elif found[name] != norm(value):
                out.append(f"DRIFT {path} {sel} {name}: {found[name]} != {norm(value)}")
        for name in found:
            if name not in tokens:
                out.append(f"EXTRA {path} {sel} {name}")
    return out


def rewrite_block(block: str, want: dict[str, dict[str, str]]) -> str:
    """The block with every wanted token set; comments, order and extras kept."""
    for sel, tokens in want.items():
        rule = None
        for m in RULE.finditer(block):
            if norm(COMMENT.sub("", m.group(1))) == sel:
                rule = m
                break
        if rule is None:
            body = "".join(f"  {k}: {v};\n" for k, v in tokens.items())
            block = block.rstrip("\n") + f"\n{sel} {{\n{body}}}\n"
            continue
        body = rule.group(2)
        seen = set()

        def setv(d: re.Match) -> str:
            name = d.group(1)
            if name not in tokens:
                return d.group(0)
            seen.add(name)
            if norm(d.group(2)) == norm(tokens[name]):
                return d.group(0)
            return f"{name}: {tokens[name]};"

        body = DECL.sub(setv, body)
        missing = [k for k in tokens if k not in seen]
        if missing:
            body = body.rstrip(" \n") + "\n" + "".join(f"  {k}: {tokens[k]};\n" for k in missing)
        block = block[:rule.start(2)] + body + block[rule.end(2):]
    return block


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--spec", type=pathlib.Path, default=DEFAULT_SPEC)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    want = expected(json.loads(args.spec.read_text(encoding="utf-8")))
    status = 0
    for path in args.files:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        if args.write:
            span = block_span(text)
            if span is None:
                print(f"NOBLOCK {path}")
                status = 2
                continue
            new = text[:span[0]] + rewrite_block(text[span[0]:span[1]], want) + text[span[1]:]
            if new != text:
                pathlib.Path(path).write_text(new, encoding="utf-8")
                print(f"wrote {path}")
            text = new
        found = problems(path, text, want)
        for line in found:
            print(line)
        if any(p.startswith("NOBLOCK") for p in found):
            status = 2
        elif found and status == 0:
            status = 1
    if status == 0:
        print(f"tokens: {len(args.files)} file(s) match {args.spec.name}")
    return status


if __name__ == "__main__":
    sys.exit(main())
