"""Report the LaTeX warnings that matter for the manuscript.

Usage:
    python -u artifacts/analysis/latex_warnings.py [paper_dir]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHECKS = [
    ("undefined reference", r"LaTeX Warning: Reference `[^']*' on page \d+ undefined"),
    ("undefined citation", r"Citation `[^']*' on page \d+ undefined"),
    ("multiply defined label", r"multiply defined"),
    ("overfull hbox", r"Overfull \\hbox"),
    ("overfull vbox", r"Overfull \\vbox"),
    ("underfull hbox", r"Underfull \\hbox"),
    ("underfull vbox", r"Underfull \\vbox"),
    ("latex error", r"^! "),
]


def main() -> int:
    paper = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"F:\zero trust\zero-trust\paper")
    log = (paper / "template.log").read_text(encoding="utf-8", errors="replace")

    bad = 0
    for name, pat in CHECKS:
        hits = re.findall(pat, log, flags=re.MULTILINE)
        print(f"{name:<24}: {len(hits)}")
        if name in ("undefined reference", "undefined citation",
                    "multiply defined label", "latex error"):
            bad += len(hits)
        if name == "overfull hbox":
            for line in re.findall(r"Overfull \\hbox.*", log)[:10]:
                print(f"    {line}")

    print("-" * 60)
    print("BLOCKING ISSUES:", bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
