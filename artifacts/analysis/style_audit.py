"""Style and academic-convention audit of the manuscript source.

Pure text analysis: it does not judge, it lists the places where a convention
could be violated, so that each one can be looked at in context.

    python -u artifacts/analysis/style_audit.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"


def find(text: str, pattern: str) -> list[tuple[int, str]]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line, re.IGNORECASE):
            out.append((i, line.strip()))
    return out


def report(title: str, rows: list[tuple[int, str]], limit: int = 14) -> None:
    print()
    print("=" * 96)
    print(f"{title}   ({len(rows)} hit(s))")
    print("=" * 96)
    for i, line in rows[:limit]:
        print(f"  L{i:<5} {line[:150]}")
    if len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more")


def main() -> int:
    raw = TEX.read_text(encoding="utf-8")
    # the body only: no LaTeX class comments, no preamble
    body = raw.split("\\begin{document}", 1)[-1]
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("%"))
    text = body
    lines = body.splitlines()

    # ---------------------------------------------------------------- spelling
    uk = r"\b(neighbourhood|behaviour|analyse[sd]?|normalise[sd]?|normalis\w+|"
    uk += r"optimis\w+|parameterm?isation|modelling|labelled|labelling|centre\w*|"
    uk += r"colour\w*|favour\w*|summaris\w+|characteris\w+|recognis\w+|generalis\w+)\b"
    us = r"\b(neighborhood|behavior|analyz\w+|normaliz\w+|optimiz\w+|"
    us += r"parameterization|modeling|labeled|labeling|center\w*|color\w*|"
    us += r"favor\w+|summariz\w+|characteriz\w+|recogniz\w+|generaliz\w+)\b"
    uk_rows, us_rows = find(text, uk), find(text, us)
    print("=" * 96)
    print("SPELLING VARIANTS IN USE")
    print("=" * 96)
    for name, pat in (("UK", uk), ("US", us)):
        counts = Counter()
        for _i, line in find(text, pat):
            for m in re.finditer(pat, line, re.IGNORECASE):
                counts[m.group(0).lower()] += 1
        print(f"  {name}: {sum(counts.values())} occurrence(s)  {dict(counts)}")

    # ------------------------------------------------------- over-claiming words
    report("OVER-CLAIMING / STRONG LANGUAGE",
           find(text, r"\b(obviously|clearly|undoubtedly|certainly|remarkabl\w+|"
                       r"dramatic\w+|huge\w*|massive\w*|excellent|perfect\w*|"
                       r"groundbreak\w+|state-of-the-art|best-ever|"
                       r"unprecedented\w*|the first ever|proves?)\b"))

    report("SIGNIFICANT USED WITHOUT A TEST NEARBY",
           find(text, r"\bsignificant(ly)?\b")[:0] or
           [(i, l) for i, l in find(text, r"\bsignificant(ly)?\b")
            if not re.search(r"p[<=>]|CI|interval|Wilcoxon|\\pm|percent|"
                             r"pp\b|standard deviation|95\\%", l, re.IGNORECASE)])

    report("MODAL VERBS THAT PRESCRIBE",
           find(text, r"\b(must|should|shall|needs? to|has to|have to|ought to)\b"))

    report("FIRST PERSON",
           find(text, r"\b(we|our|ours|us)\b"))

    report("HEDGES AND QUALIFIERS",
           find(text, r"\b(appears?|seems?|suggests?|likely|probably|"
                       r"may|might|could|arguably|presumably|roughly|"
                       r"approximately|about|around)\b"))

    # ------------------------------------------------------- numeric conventions
    report("PER CENT SPELLED OUT",
           find(text, r"\bper cent\b|\bpercent\b(?!ile)"))
    report("RANGE FORMATTING (en dash vs hyphen)",
           find(text, r"\d--\d"))
    report("PP VS PERCENT IN PROSE",
           find(text, r"\d+\s*pp\b"))
    report("LEADING-ZERO NUMBERS",
           find(text, r"(?<![\d.])\.\d+"))
    report("MAGNUM / BIG NUMBERS IN PROSE",
           find(text, r"\b(ten|eleven|twelve|thirteen|fourteen|fifteen|"
                       r"sixteen|seventeen|eighteen|nineteen|twenty)\b"))

    # ------------------------------------------------------- terms and capitalisation
    report("TERMS THAT MAY NEED ONE NAME",
           find(text, r"\b(block-routed|block routed|gated fusion|mixture of experts|"
                       r"MoE|specialist)\b"))
    report("ATTACK CLASS NAMES",
           find(text, r"\b(on--off|on-off|on off|periodic attacker|intermittent attacker)\b"))
    report("FIRST-PERSON CLAIM VERBS",
           find(text, r"\b(demonstrates?|shows?|proves?|establishes?|"
                       r"confirms?|verifies?|reveals?)\b"))
    report("CITATION PLACEMENT MARKERS",
           find(text, r"\(see |as shown in|compared with|compared to|"
                       r"in contrast to|by contrast,"))

    # ------------------------------------------------------- structure
    print()
    print("=" * 96)
    print("STRUCTURE")
    print("=" * 96)
    labels = re.findall(r"\\label\{(tab:[^}]+|fig:[^}]+)\}", text)
    print(f"  labels defined: {len(labels)}")
    for lab in labels:
        n = len(re.findall(re.escape(lab) + r"\}", text)) - 1
        # count references excluding the definition itself
        refs = len(re.findall(r"\\ref\{" + re.escape(lab) + r"\}", text))
        if refs == 0:
            print(f"    NEVER REFERENCED: {lab}")
    cites = re.findall(r"\\cite\{([^}]*)\}", text)
    keys = Counter()
    for c in cites:
        for k in c.split(","):
            keys[k.strip()] += 1
    print(f"  distinct citation keys used: {len(keys)}")
    unused = [k for k, v in keys.items() if v == 1]
    print(f"  keys cited exactly once: {len(unused)}")
    bib = ROOT / "paper" / "template.bib"
    if bib.exists():
        btext = bib.read_text(encoding="utf-8")
        declared = set(re.findall(r"@\w+\{([^,]+),", btext))
        missing = sorted(k for k in keys if k not in declared)
        print(f"  citation keys missing from the .bib: {missing}")
        uncited = sorted(declared - set(keys))
        print(f"  .bib entries never cited ({len(uncited)}): {uncited}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
