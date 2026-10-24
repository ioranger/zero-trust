"""Bring the tables to a common type size.

The tables are scaled with `\\resizebox`, so the type size each one ends up
with depends on how wide its columns are, not on the source. Measured on the
built PDF, the sizes ranged from 7.6 pt to 11.2 pt, which reads as a set of
tables set in different type.

This script reports the current sizes and the scale each table needs, so the
resizebox factors can be chosen against a common target rather than by eye.

Usage:
    python -u artifacts/analysis/table_type_sizes.py
"""

from __future__ import annotations

from pathlib import Path

import fitz

PDF = Path(r"F:\zero trust\zero-trust\paper\template.pdf")

# (label, needle identifying the table's first data row, current scale factor)
TABLES = [
    ("Table 3  main comparison", "84.8", 0.73),
    ("Table 5  probe level", "0.9724", 0.96),
    ("Table 6  duty cycle", "12.0", 0.41),
    ("Table 7  ns-3 packet", "0.990", 0.84),
    ("Table 8  spatial main", "39.8", 0.96),
    ("Table 9  spatial robust", "field amplitude 0.30", 1.02),
    ("Table 10 spatial blocks", "marginal + shape", 1.18),
    ("Table 11 architecture controls", "0.143", 1.17),
]

TARGET = 9.5


def main() -> int:
    doc = fitz.open(PDF)
    print(f"{'table':<32}{'page':>6}{'size':>8}{'scale':>9}{'suggested':>11}")
    print("-" * 66)
    for label, needle, scale in TABLES:
        size = None
        page_no = None
        for i in range(doc.page_count):
            for block in doc[i].get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(s["text"] for s in line["spans"])
                    if needle in text and line["spans"]:
                        size = max(round(s["size"], 1) for s in line["spans"])
                        page_no = i + 1
                        break
                if size:
                    break
            if size:
                break
        if size is None:
            print(f"{label:<32}{'--':>6}{'not found':>8}")
            continue
        if scale is None:
            # natural width: the size is what \footnotesize produced
            print(f"{label:<32}{page_no:>6}{size:>8.1f}{'natural':>9}"
                  f"{'widen':>11}")
            continue
        factor = TARGET / size
        new_scale = scale * factor
        print(f"{label:<32}{page_no:>6}{size:>8.1f}{scale:>9.2f}"
              f"{new_scale:>11.2f}")
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
