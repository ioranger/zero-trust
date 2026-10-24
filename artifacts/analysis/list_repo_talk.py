"""Report the sentences that point at code locations rather than at science.

Besides the file paths, a manuscript can carry repository talk that a
reviewer cannot act on: where a result is stored, which script produced it,
what a reader is told to look up in the accompanying code. This script lists
the lines that mention such things, so each can be rewritten in prose.

Usage:
    python -u artifacts/analysis/list_repo_talk.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# phrases that refer to the layout of the accompanying package rather than to
# the method or the result
PATTERNS = [
    r"in the artifact\b",
    r"in the repository",
    r"in the released artifact",
    r"of the artifact\b",
    r"the artifact\b",
    r"replication package",
    r"see the appendix",
    r"reported in the artifact",
    r"committed\b",
    r"source tree",
    r"package layout",
    r"\\texttt\{[^}]*/",
]


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("%"):
            continue
        hits = [p for p in PATTERNS if re.search(p, line, re.IGNORECASE)]
        if hits:
            print(f"line {i}: {', '.join(hits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
