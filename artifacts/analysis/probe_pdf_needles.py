"""Report which pages of the built PDF contain a given string, so a failing
needle in the page map can be corrected.

Usage:
    python -u artifacts/analysis/probe_pdf_needles.py "text to look for"
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

PDF = Path(r"F:\zero trust\zero-trust\paper\template.pdf")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    needles = sys.argv[1:]
    doc = fitz.open(PDF)
    for needle in needles:
        pages = [i + 1 for i in range(doc.page_count)
                 if needle in doc[i].get_text()]
        print(f"  {needle!r}: pages {pages}" if pages
              else f"  {needle!r}: not found")
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
