"""Report the pages of the built paper that carry almost no text.

A page with very little text is usually a page that holds only floats, and
LaTeX spreads those floats over the page with \\vfill, which reads as a hole
in the typeset paper. This script lists the sparse pages and the floats on
them, so they can be looked at.

Usage:
    python -u artifacts/analysis/audit_sparse_pages.py
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

ROOT = Path(r"F:\zero trust\zero-trust")
PDF = ROOT / "paper" / "template.pdf"
TEX = ROOT / "paper" / "template.tex"


def main() -> int:
    doc = fitz.open(str(PDF))
    text = TEX.read_bytes().decode("utf-8")

    print("=" * 92)
    print("sparse pages of the built paper")
    print("=" * 92)
    print(f"{'page':>5}  {'chars':>6}  {'images':>7}  note")
    sparse = []
    for i, page in enumerate(doc, 1):
        body = page.get_text().strip()
        images = len(page.get_images(full=True))
        # the running page number and the header/footer are not content
        note = ""
        if len(body) < 500 and images > 0:
            note = "mostly figures"
            sparse.append(i)
        print(f"{i:>5}  {len(body):>6}  {images:>7}  {note}")

    print()
    if sparse:
        print(f"pages that are mostly figures: {sparse}")
        for i in sparse:
            for m in re.finditer(r"\\caption\{(.+?)\}\s*\n", text, re.S):
                pass
            page = doc[i - 1]
            blocks = page.get_text("blocks")
            caps = [b[4].strip().split("\n")[0][:60] for b in blocks
                    if b[4].strip().startswith("Figure") or b[4].strip().startswith("Table")]
            print(f"  page {i}: {caps}")
    else:
        print("no page is mostly figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
