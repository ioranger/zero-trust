"""Set the type size of the manuscript's tables.

The tables are scaled with `\\resizebox`, so the type size each one ends up
with follows from how wide its columns are rather than from the source.
Measured on the built PDF the sizes ran from 6.7 pt to 14.3 pt, which reads
as a set of tables set in different type, and the widest of them overflowed
the text width.

The factors below bring all the tables to about 9.5 pt with none of them
overflowing. Each replacement is anchored on the table's own header row, so
that a factor shared by two tables is changed in the right one.

Run `table_type_sizes.py` to measure the result.

Usage:
    python -u artifacts/analysis/set_table_scales.py
"""

from __future__ import annotations

from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# (header row that identifies the table, old factor, new factor)
SCALES = [
    ("Configuration & field amp. & position ratio",
     "1.02\\textwidth", "0.97\\textwidth"),            # spatial robust
    ("Arm & constant & dormant & on--off & position-inconsistent",
     "1.18\\textwidth", "0.99\\textwidth"),            # spatial blocks
    ("Arm & modality head & modality head accuracy",
     "1.17\\textwidth", "0.99\\textwidth"),            # architecture controls
]


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    for header, old, new in SCALES:
        i = text.find(header)
        if i < 0:
            print(f"!! the table with header {header!r} was not found")
            return 1
        j = text.rfind("\\resizebox{", 0, i)
        if j < 0:
            print(f"!! no resizebox before the header {header!r}")
            return 1
        k = text.find("}", j)
        current = text[j + len("\\resizebox{"):k]
        if current != old:
            print(f"!! {header!r}: expected factor {old}, found {current}")
            return 1
        text = text[:j] + f"\\resizebox{{{new}" + text[k:]
        print(f"  {header[:34]:<36}{old} -> {new}")
    TEX.write_text(text, encoding="utf-8", newline="")
    print("table scale factors updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
