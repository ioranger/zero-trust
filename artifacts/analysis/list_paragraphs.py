"""List the paragraphs of a line range with their word counts, so that only
the fat ones have to be read and rewritten."""

from __future__ import annotations

import re
import sys
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")


def strip_tex(s: str) -> str:
    s = re.sub(r"%.*", "", s)
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\ref\{[^}]*\}", "", s)
    s = re.sub(r"\\texttt\{[^}]*\}", "CODE", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", s)
    s = re.sub(r"[{}$&\\~^]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    lines = TEX.read_text(encoding="utf-8").splitlines()
    block = "\n".join(lines[lo - 1:hi])
    # split on blank lines
    for para in re.split(r"\n\s*\n", block):
        p = para.strip()
        if not p:
            continue
        w = len(strip_tex(p).split())
        head = p[:70].replace("\n", " ")
        kind = "TABLE" if "\\begin{table}" in p else (
            "EQ" if "\\begin{equation" in p else "P")
        print(f"{w:>5}w  {kind:<6} {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
