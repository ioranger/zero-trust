"""Check the manuscript's inline bibliography against the citations.

The bibliography is written inline (`thebibliography`), so the checks that
usually read a .bib file are done on the source: every entry must be cited
somewhere, and every citation must have an entry.

    python -u artifacts/analysis/bibliography_audit.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    body = text.split("\\begin{document}", 1)[-1]

    bib = body.split("\\begin{thebibliography}", 1)[-1]
    bib = bib.split("\\end{thebibliography}", 1)[0]
    entries = re.findall(r"\\bibitem\{([^}]+)\}", bib)
    labels = re.findall(r"\\bibitem\[([^\]]*)\]\{([^}]+)\}", bib)

    cited = Counter()
    for group in re.findall(r"\\cite\{([^}]*)\}", body):
        for k in group.split(","):
            k = k.strip()
            if k:
                cited[k] += 1

    print("=" * 92)
    print(f"bibliography entries: {len(entries)}   distinct citation keys: {len(cited)}")
    print("=" * 92)

    uncited = [e for e in entries if e not in cited]
    missing = [k for k in cited if k not in entries]
    print(f"  entries never cited ({len(uncited)}):")
    for e in uncited:
        print(f"    - {e}")
    print(f"  citation keys without an entry ({len(missing)}):")
    for k in missing:
        print(f"    - {k}")
    once = [k for k, v in cited.items() if v == 1]
    print(f"  entries cited exactly once ({len(once)}): {once}")

    print()
    print("  entry labels and their citation counts:")
    for label, key in labels:
        print(f"    {key:<34} {cited.get(key, 0):>3}x   {label[:60]}")

    # ordering: MDPI expects the bibliography to be in citation order
    order = [k for k, _ in labels]
    first_use = []
    for k in order:
        first_use.append(next((i for i, c in enumerate(cited.keys()) if c == k), 10 ** 6))
    print()
    if first_use == sorted(first_use):
        print("  bibliography order matches first citation order")
    else:
        print("  bibliography order does NOT match first citation order:")
        for key, pos in zip(order, first_use):
            print(f"    {key:<34} first cited at position {pos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
