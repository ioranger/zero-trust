"""Count the two spellings of the intermittent attack class and show where the
hyphenated one appears.

    python -u artifacts/analysis/term_consistency.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"


def main() -> int:
    raw = TEX.read_text(encoding="utf-8")
    body = raw.split("\\begin{document}", 1)[-1]
    body = "\n".join(l for l in body.splitlines()
                     if not l.lstrip().startswith("%"))
    print("=" * 92)
    print("ATTACK CLASS NAME")
    print("=" * 92)
    print(f"  on--off (en dash): {len(re.findall(r'on--off', body))}")
    print(f"  on-off  (hyphen)  : {len(re.findall(r'on-off', body))}")
    print()
    print("  the hyphenated form, in context:")
    for i, line in enumerate(body.splitlines(), 1):
        if "on-off" in line:
            s = line.strip()
            print(f"    {s[:190]}")
    print()
    print("=" * 92)
    print("OTHER SPELLING PAIRS IN THE BODY")
    print("=" * 92)
    pairs = [
        ("behaviour", "behavior"), ("behavioural", "behavioral"),
        ("neighbourhood", "neighborhood"), ("neighbourhood-relative", "neighborhood-relative"),
        ("normalised", "normalized"), ("normalisation", "normalization"),
        ("modelling", "modeling"), ("modelled", "modeled"),
        ("optimisation", "optimization"), ("optimiser", "optimizer"),
        ("optimise", "optimize"), ("summarisation", "summarization"),
        ("characterisation", "characterization"), ("characterise", "characterize"),
        ("generalisation", "generalization"), ("labelled", "labeled"),
        ("favourable", "favorable"), ("favour", "favor"),
        ("recognise", "recognize"), ("centring", "centering"),
        ("analyse", "analyze"), ("analysed", "analyzed"),
        ("towards ", "toward "), ("amongst", "among"),
    ]
    for uk, us in pairs:
        n_uk = len(re.findall(r"\b" + uk, body, re.IGNORECASE))
        n_us = len(re.findall(r"\b" + us, body, re.IGNORECASE))
        if n_uk or n_us:
            mark = "  <-- MIXED" if n_uk and n_us else ""
            print(f"  {uk:<24} {n_uk:>3}x   |   {us:<22} {n_us:>3}x{mark}")
    print()
    print("=" * 92)
    print("'percent' / 'per cent' OUTSIDE THE BIBLIOGRAPHY")
    print("=" * 92)
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"\b(percent|per cent)\b", line, re.IGNORECASE):
            print(f"    {line.strip()[:190]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
