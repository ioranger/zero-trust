"""List the bold cells of every table in the manuscript.

Bold is used to mark the proposed model's advantage. A cell that is bold
because another method is ahead of the proposed model says the opposite, so
every bold cell has to be checked against the table it sits in. This script
prints the tables with their bold cells, so each can be judged.

Usage:
    python -u artifacts/analysis/list_bold_cells.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    lines = text.splitlines()
    # locate each table environment and its label
    i = 0
    while i < len(lines):
        if "\\begin{table}" not in lines[i]:
            i += 1
            continue
        start = i
        j = i
        while j < len(lines) and "\\end{table}" not in lines[j]:
            j += 1
        label = ""
        for k in range(start, j):
            m = re.search(r"\\label\{(tab:[^}]+)\}", lines[k])
            if m:
                label = m.group(1)
                break
        caption = ""
        for k in range(start, j):
            if "\\caption{" in lines[k]:
                caption = lines[k].strip()
                break
        print(f"=== {label}  (lines {start + 1}-{j + 1}) ===")
        if caption:
            print(f"    caption: {caption[:150]}")
        for k in range(start, j + 1):
            line = lines[k]
            if "\\textbf{" in line and "&" in line:
                print(f"    {k + 1}: {line.strip()}")
        print()
        i = j + 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
