"""List the path-like `\\texttt{...}` items in the manuscript.

A reviewer-facing paper should not carry the repository's internal file
paths. This script lists every typewriter item that looks like a path or a
script name, so they can be found and rewritten in prose.

Usage:
    python -u artifacts/analysis/list_code_paths.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

PATTERNS = (".py", ".json", ".cc", ".sh", ".md", ".csv", ".txt", ".tex", "/")


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    lines = text.splitlines()
    seen = {}
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r"\\texttt\{([^}]*)\}", line):
            item = m.group(1)
            if any(p in item for p in PATTERNS):
                seen.setdefault(item, []).append(i)
    print(f"{len(seen)} distinct path-like items")
    print()
    for item, where in sorted(seen.items(), key=lambda kv: kv[1][0]):
        print(f"  line {where[0]:>5}  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
