"""List the remaining American spellings in the manuscript source, with the
line each one sits on, so that the last of them can be cleared.

    python -u artifacts/analysis/remaining_us_spellings.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"

US = [
    "behaviors", "behavioral", "behavior", "neighborhoods", "neighborhood",
    "normalized", "normalizing", "normalization", "modeled", "modeling",
    "optimization", "optimizer", "optimized", "optimizing", "optimize",
    "summarization", "summarized", "summarizes", "summarize",
    "characterization", "characterized", "characterize",
    "generalization", "generalized", "generalize",
    "labeled", "labeling", "favorable", "unfavorable", "favor",
    "recognizes", "recognize", "recognized", "analyzed", "analyze",
]


def main() -> int:
    lines = TEX.read_text(encoding="utf-8").splitlines()
    hits = 0
    print("=" * 96)
    print("REMAINING AMERICAN SPELLINGS IN THE SOURCE")
    print("=" * 96)
    for i, line in enumerate(lines, 1):
        found = [w for w in US if re.search(r"(?<!\\)\b" + re.escape(w) + r"\b", line)]
        if found:
            hits += len(found)
            kind = "comment" if line.lstrip().startswith("%") else "body   "
            print(f"  L{i:<5} [{kind}] {found}")
            s = line.strip()
            print(f"           {s[:150]}")
    print()
    print(f"  total: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
