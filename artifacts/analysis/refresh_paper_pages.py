"""Refresh the committed page renders from the built PDF.

The renders under `artifacts/analysis/paper_pages/` are snapshots of the
manuscript as built. They go stale whenever the source changes, and a stale
snapshot that still shows a removed method is worse than none, so this script
regenerates them from `paper/template.pdf` in one pass.

The pages kept are the ones that carry the main results: the abstract, the
comparison tables, the method-group table, the duty-cycle sweep, the packet-level
table, the spatial tables, the architecture controls, and the figures.

Usage:
    python -u artifacts/analysis/refresh_paper_pages.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

ROOT = Path(r"F:\zero trust\zero-trust")
PDF = ROOT / "paper" / "template.pdf"
OUT = ROOT / "artifacts" / "analysis" / "paper_pages"

# (output name, page number)
# every page that is kept in the folder, so that no snapshot goes stale
PAGES = [
    ("page_01.png", 1),
    ("page_02.png", 2),
    ("page_03.png", 3),
    ("page_04.png", 4),
    ("page_05.png", 5),
    ("page_07.png", 7),
    ("page_13.png", 13),
    ("page_16.png", 16),
    ("page_17.png", 17),
    ("page_18.png", 18),
    ("page_19.png", 19),
    ("page_20.png", 20),
    ("page_21.png", 21),
    ("page_22.png", 22),
    ("page_23.png", 23),
    ("page_24.png", 24),
    ("page_25.png", 25),
    ("page_26.png", 26),
    ("page_27.png", 27),
    ("page_28.png", 28),
]


def main() -> int:
    if not PDF.exists():
        print(f"!! {PDF} not found; build the paper first")
        return 2
    doc = fitz.open(PDF)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{PDF.name}: {doc.page_count} pages")
    for name, number in PAGES:
        if number > doc.page_count:
            print(f"  {name}: skipped, the document has {doc.page_count} pages")
            continue
        page = doc[number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7))
        out = OUT / name
        pix.save(out)
        print(f"  {out.name}  ({out.stat().st_size // 1024} KB)")
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
