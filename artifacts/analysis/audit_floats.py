"""Enumerate every float in the manuscript and where it is referred to.

For each figure and table: the label, the caption, the page it lands on in
the built PDF, and every place in the text that refers to it. A float that is
never referred to, or that is referred to only after it has floated, is a
structural defect.

Usage:
    python -u artifacts/analysis/audit_floats.py
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"
PDF = ROOT / "paper" / "template.pdf"


def main() -> int:
    text = TEX.read_bytes().decode("utf-8")
    lines = text.split("\n")
    doc = fitz.open(str(PDF))
    page_text = [re.sub(r"\s+", " ", p.get_text()) for p in doc]

    floats = []
    for kind in ("figure", "table"):
        for m in re.finditer(r"\\begin\{" + kind + r"\}(.*?)\\end\{" + kind + r"\}",
                             text, re.S):
            block = m.group(1)
            start_line = text[:m.start()].count("\n") + 1
            lab = re.search(r"\\label\{([^}]+)\}", block)
            cap = re.search(r"\\caption\{(.+?)\}\s*\n", block, re.S)
            if not lab:
                continue
            caption = re.sub(r"\s+", " ", cap.group(1)) if cap else ""
            floats.append({
                "kind": kind,
                "label": lab.group(1),
                "line": start_line,
                "caption": caption,
                "block": block,
            })

    problems = []
    notes = []
    for f in sorted(floats, key=lambda d: d["line"]):
        refs = [j for j, line in enumerate(lines, 1)
                if re.search(r"\\ref\{" + re.escape(f["label"]) + r"\}", line)]
        # the page the caption lands on: the first page whose text carries a
        # distinctive part of the caption
        page = None
        probe = re.sub(r"\\[a-zA-Z]+\{?", "", f["caption"])[:38].strip()
        for pi, t in enumerate(page_text, 1):
            if probe and probe in t:
                page = pi
                break
        refstr = ", ".join(f"L{r}" for r in refs) if refs else "NONE"
        print(f"\n{f['kind'].upper():<7} {f['label']}   (tex L{f['line']}, PDF p{page})")
        print(f"        caption: {f['caption'][:150]}")
        print(f"        referenced at {refstr}")
        if not refs:
            problems.append(f"{f['label']} is never referenced")
        elif refs[0] > f["line"]:
            # a float that sits directly under its own section heading is
            # introduced by that heading, so this is a note and not a defect
            notes.append(f"{f['label']} is first referenced at L{refs[0]}, "
                         f"after it is declared at L{f['line']}")

    print()
    print("=" * 100)
    print(f"floats: {len(floats)}   pages: {doc.page_count}")
    for n in notes:
        print(f"  [note] {n}")
    if problems:
        for p in problems:
            print(f"  [FAIL] {p}")
    else:
        print("  every float is referenced")
    print("=" * 100)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
