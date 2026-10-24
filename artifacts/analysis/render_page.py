"""Render one page of the built paper, so a specific page can be checked
after a rebuild.

Usage:
    python -u artifacts/analysis/render_page.py <page-number>
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

ROOT = Path(r"F:\zero trust\zero-trust")
PDF = ROOT / "paper" / "template.pdf"
OUT = ROOT / "artifacts" / "analysis" / "paper_pages"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    page_no = int(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    page = doc[page_no - 1]
    out = OUT / f"page_{page_no:02d}.png"
    pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7))
    pix.save(out)
    print(f"{out}  ({out.stat().st_size // 1024} KB)")
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
