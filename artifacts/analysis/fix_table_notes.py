"""End the table's own line before its note, in every table that has one.

A table note written after `\\end{tabular}}` continues on the line the table
occupies, because the closing brace of the `\\resizebox{...}{!}{%` group ends
the box but not the line. Where the table is narrower than the text width the
note is therefore typeset to the right of the table instead of below it, which
is what Table 9 and Table 10 showed on page 24.

This script inserts `\\par` between the closing brace and the note in every
table that carries one, so each note starts below its table.

Usage:
    python -u artifacts/analysis/fix_table_notes.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    # The note always follows the closing brace of the resizebox group and
    # begins with the size commands that set it.
    pattern = re.compile(r"(\\end\{tabular\}\})(\n)(\\vspace\{2pt\}\n"
                         r"\\raggedright\\scriptsize\n)")
    hits = pattern.findall(text)
    print(f"tables with a note: {len(hits)}")
    if not hits:
        print("!! no table note found; the source layout has changed")
        return 1
    text = pattern.sub(r"\1\2\\par\2\3", text)
    TEX.write_text(text, encoding="utf-8", newline="")
    print("every table note now starts on its own line below the table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
