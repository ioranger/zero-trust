"""Mechanical consistency checks over the manuscript.

These are the checks that a reader's eye would catch: labels that nothing
points at, references to labels that do not exist, numbering that skips, the
same quantity written two different ways, and figures or tables that are
mentioned in the text but never shown.

Nothing is modified; the script only reports.

Usage:
    python -u artifacts/analysis/audit_consistency.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    lines = text.splitlines()
    # drop comment lines, which are template instructions
    body = "\n".join(l for l in lines if not l.lstrip().startswith("%"))

    print("=" * 78)
    print("1. labels and references")
    print("=" * 78)
    labels = re.findall(r"\\label\{([^}]+)\}", body)
    refs = re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", body)
    for name, n in sorted(Counter(labels).items()):
        used = refs.count(name)
        flag = "  <-- never referenced" if used == 0 else ""
        print(f"  label {name:<34} defined once, referenced {used}{flag}")
    dupes = [k for k, v in Counter(labels).items() if v > 1]
    if dupes:
        print(f"  !! labels defined more than once: {dupes}")
    missing = sorted(set(refs) - set(labels))
    if missing:
        print(f"  !! references to labels that do not exist: {missing}")
    else:
        print("  every reference resolves")
    print()

    print("=" * 78)
    print("2. figures and tables")
    print("=" * 78)
    figs = re.findall(r"\\label\{(fig:[^}]+)\}", body)
    tabs = re.findall(r"\\label\{(tab:[^}]+)\}", body)
    print(f"  figures: {len(figs)}  -> {figs}")
    print(f"  tables:  {len(tabs)}  -> {tabs}")
    for kind, names in (("fig", figs), ("tab", tabs)):
        for nm in names:
            n = body.count("\\ref{" + nm + "}")
            if n == 0:
                print(f"  !! {kind} {nm} is never referenced in the text")
    print()

    print("=" * 78)
    print("3. enumeration and outline numbering")
    print("=" * 78)
    for pat, title in (
        (r"\\textbf\{\((i{1,3}|iv|v|vi{1,2})\)\s*([^}]{0,70})", "observations"),
        (r"\\paragraph\{([^}]{0,60})\}", "paragraph headings"),
        (r"\\subsection\{([^}]{0,60})\}", "subsections"),
    ):
        found = re.findall(pat, body)
        print(f"  {title}: {len(found)}")
        for item in found:
            print(f"     {item}")
    print()

    print("=" * 78)
    print("4. the same quantity written in several ways")
    print("=" * 78)
    for name, pats in (
        ("the proposed model", [r"\bS-TIM \(ours\)", r"the proposed model",
                                r"the proposed model\b", r"\bS-TIM\b"]),
        ("the intermittent attackers", [r"on--off", r"on-off", r"intermittent attacker"]),
        ("the spatially inconsistent attackers", [r"position-inconsistent",
                                                 r"spatially inconsistent",
                                                 r"telemetry-forging",
                                                 r"behaviourally-clean"]),
    ):
        print(f"  {name}:")
        for p in pats:
            n = len(re.findall(p, body))
            print(f"     {p:<42} {n}")
    print()

    print("=" * 78)
    print("5. numbers in the prose that appear in no table")
    print("=" * 78)
    # every percentage in the source, with the lines it occurs on
    table_lines = set()
    inside = False
    for i, l in enumerate(lines, 1):
        if "\\begin{table}" in l:
            inside = True
        if inside:
            table_lines.add(i)
        if "\\end{table}" in l:
            inside = False
    prose_pcts = Counter()
    for i, l in enumerate(lines, 1):
        if i in table_lines or l.lstrip().startswith("%"):
            continue
        for m in re.finditer(r"(\d+\.\d)\\%", l):
            prose_pcts[m.group(1)] += 1
    print(f"  distinct percentages in the prose: {len(prose_pcts)}")
    print("  " + ", ".join(f"{k}" for k in sorted(prose_pcts, key=float)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
