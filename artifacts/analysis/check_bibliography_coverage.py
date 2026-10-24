"""Check that every bibliography entry is still cited.

A journal rejects a manuscript with uncited references, and removing a
related-work subsection removes the citations that support its entries. This
script reports the entries that nothing cites any more, and the citations
that no longer resolve.

Usage:
    python -u artifacts/analysis/check_bibliography_coverage.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    body = "\n".join(l for l in text.splitlines()
                     if not l.lstrip().startswith("%"))
    # the bibliography starts at the first \bibitem
    first = body.find("\\bibitem{")
    if first < 0:
        print("!! no bibliography found")
        return 1
    entries = re.findall(r"\\bibitem\{([^}]+)\}", body[first:])
    cited = set()
    for m in re.finditer(r"\\cite\{([^}]+)\}", body[:first]):
        cited.update(k.strip() for k in m.group(1).split(","))
    for m in re.finditer(r"\\cite\{([^}]+)\}", body[first:]):
        cited.update(k.strip() for k in m.group(1).split(","))

    print("=" * 78)
    print(f"bibliography entries: {len(entries)}")
    print("=" * 78)
    uncited = [e for e in entries if e not in cited]
    if uncited:
        print(f"  !! entries that nothing cites any more: {len(uncited)}")
        for e in uncited:
            print(f"     {e}")
    else:
        print("  every entry is cited")
    dangling = sorted(cited - set(entries))
    if dangling:
        print(f"  !! citations with no entry: {dangling}")
    else:
        print("  every citation resolves")
    print()
    print(f"  citations: {len(cited)} distinct")
    return 1 if (uncited or dangling) else 0


if __name__ == "__main__":
    raise SystemExit(main())
