"""Count the numerals in the abstract, so that the number budget of the
abstract can be tracked when it is edited.

    python -u artifacts/analysis/abstract_number_budget.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    m = re.search(r"\\abstract\{(.*?)\}\n", text, re.DOTALL)
    if not m:
        print("!! the abstract was not found")
        return 2
    a = m.group(1)
    nums = re.findall(r"\d+(?:\.\d+)?(?:--\d+(?:\.\d+)?)?", a)
    pvals = [n for n in nums if "^{-6}" in a[max(0, a.find(n) - 12):a.find(n) + 14]]
    print("=" * 92)
    print("ABSTRACT NUMBER BUDGET")
    print("=" * 92)
    print(f"  words: {len(a.split())}")
    print(f"  numerals: {len(nums)}")
    print(f"  of which p-value exponents: {len(pvals)}")
    print()
    for n in nums:
        i = a.find(n)
        ctx = a[max(0, i - 60):i + 40].replace("\n", " ")
        print(f"    {n:<10} ...{ctx}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
