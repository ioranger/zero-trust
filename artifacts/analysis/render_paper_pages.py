"""Render the pages of the built paper that carry the main results, and print a
page map of the document.

    python -u artifacts/analysis/render_paper_pages.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

ROOT = Path(r"F:\zero trust\zero-trust")
PDF = ROOT / "paper" / "template.pdf"
OUT = ROOT / "artifacts" / "analysis" / "paper_pages"

WANTED = [
    ("abstract", "Trust scores are useful in a cooperative UAV mission"),
    ("main comparison table", "Performance comparison of S-TIM with baseline methods"),
    ("method-class table", "Detection rate by"),
    ("duty-cycle sweep", "On--off detection rate"),
    ("ns-3 packet table", "Packet-level validation on five multi-seed"),
    ("spatial main table", "The published comparison, repeated in the spatially"),
    ("spatial blocks table", "Every arm run in the spatially inconsistent"),
    ("architecture controls", "Four-arm architecture control"),
]


def main() -> int:
    doc = fitz.open(PDF)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{PDF.name}: {doc.page_count} pages")
    print()
    print("=" * 92)
    print("PAGE MAP")
    print("=" * 92)
    hits: list[tuple[str, int]] = []
    for label, needle in WANTED:
        page = None
        for i in range(doc.page_count):
            if needle in doc[i].get_text():
                page = i + 1
                break
        if page is None:
            print(f"  {label:<26} (not found)")
            continue
        hits.append((label, page))
        print(f"  page {page:>3}   {label}")
    print()
    print("=" * 92)
    print("SECTION HEADINGS BY PAGE")
    print("=" * 92)
    for i in range(doc.page_count):
        for line in doc[i].get_text().splitlines():
            s = line.strip()
            if re.match(r"^\d+(\.\d+)?\s+[A-Z]", s) and len(s) < 90:
                print(f"  p{i + 1:>3}  {s}")
                break

    print()
    print("=" * 92)
    print("TABLES AND FIGURES BY PAGE")
    print("=" * 92)
    for i in range(doc.page_count):
        text = doc[i].get_text()
        for m in re.finditer(r"Table (\d+)\.", text):
            print(f"  p{i + 1:>3}  Table {m.group(1)}")
        for m in re.finditer(r"Figure (\d+)\.", text):
            print(f"  p{i + 1:>3}  Figure {m.group(1)}")

    rendered = sorted({1} | {p for _l, p in hits})
    print()
    print("=" * 92)
    print(f"RENDERING {len(rendered)} pages to {OUT}")
    print("=" * 92)
    for p in rendered:
        page = doc[p - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7))
        out = OUT / f"page_{p:02d}.png"
        pix.save(out)
        print(f"  {out}  ({out.stat().st_size // 1024} KB)")
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
