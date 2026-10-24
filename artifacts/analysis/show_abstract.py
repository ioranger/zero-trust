"""Print the abstract as plain text, so that it can be read without the
LaTeX markup in the way.

    python -u artifacts/analysis/show_abstract.py
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    m = re.search(r"\\abstract\{(.*?)\}\s*\n", text, re.DOTALL)
    if not m:
        print("!! the abstract was not found")
        return 2
    s = m.group(1)
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\texttt\{([^}]*)\}", r"\1", s)
    s = s.replace("\\%", "%").replace("---", "--").replace("--", "-")
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = s.replace("~", " ").replace("\\", "")
    words = len(s.split())
    print(f"abstract: {words} words")
    print("=" * 92)
    for para in s.split(". "):
        para = para.strip()
        if para:
            print(textwrap.fill(para + ".", width=94))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
