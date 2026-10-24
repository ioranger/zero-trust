"""Print the given lines of the manuscript in full.

Usage:
    python -u artifacts/analysis/show_lines.py <line-number> ...
"""

from __future__ import annotations

import sys
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    lines = TEX.read_text(encoding="utf-8").splitlines()
    for arg in sys.argv[1:]:
        n = int(arg)
        print(f"===== line {n} =====")
        print(lines[n - 1])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
