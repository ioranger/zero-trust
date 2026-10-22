"""Measure where the manuscript's length goes.

The paper is long. Before anything is cut, the question has to be answered
with counts rather than impressions: how many words each section carries,
how many tables there are, and how often the same claim is stated in
different places. A claim repeated in six places is redundancy; a claim
stated once in six sentences is an argument.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

SECTION_RE = re.compile(r"\\(section|subsection|paragraph)\*?\{([^}]*)\}")
TABLE_RE = re.compile(r"\\begin\{table\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")


def strip_tex(s: str) -> str:
    s = re.sub(r"%.*", "", s)
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\ref\{[^}]*\}", "", s)
    s = re.sub(r"\\texttt\{[^}]*\}", "CODE", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", s)
    s = re.sub(r"[{}$&\\~^]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    body = text[text.find("\\begin{document}"):]

    # --- word count per structural section ---------------------------
    marks = [(m.start(), m.group(1), m.group(2)) for m in SECTION_RE.finditer(body)]
    marks.append((len(body), "END", ""))
    print("=" * 100)
    print("WORDS PER SECTION")
    print("=" * 100)
    total = 0
    rows = []
    for i in range(len(marks) - 1):
        start, kind, title = marks[i]
        end = marks[i + 1][0]
        chunk = body[start:end]
        words = len(strip_tex(chunk).split())
        total += words
        rows.append((kind, title, words, chunk.count("\\begin{table}")))
    for kind, title, words, tables in rows:
        if kind == "section" or words > 400:
            print(f"  {kind:<10} {title[:58]:<60}{words:>7} words"
                  f"{tables:>4} tables")
    print("-" * 100)
    print(f"  {'TOTAL':<10} {'':<60}{total:>7} words")

    # --- table inventory ---------------------------------------------
    print()
    print("=" * 100)
    print("TABLE INVENTORY")
    print("=" * 100)
    labels = []
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", body, re.S):
        blk = m.group(1)
        lab = LABEL_RE.search(blk)
        cap = re.search(r"\\caption\{(.*?)\}\s*\n", blk, re.S)
        cap_txt = strip_tex(cap.group(1))[:70] if cap else "(no caption)"
        labels.append((lab.group(1) if lab else "?", cap_txt,
                       len(strip_tex(blk).split())))
    for i, (lab, cap, w) in enumerate(labels, 1):
        print(f"  T{i:<3} {lab:<32}{w:>5}w  {cap}")
    print("-" * 100)
    print(f"  {len(labels)} tables, "
          f"{sum(w for _, _, w in labels)} words inside table environments")

    # --- repeated claims ---------------------------------------------
    print()
    print("=" * 100)
    print("HOW OFTEN THE SAME CLAIM IS RESTATED")
    print("=" * 100)
    probes = {
        "the representation, not the network, is what matters":
            "attributable to the \\emph{input representation}",
        "the classifier is not the binding constraint":
            "binding constraint",
        "the neighbourhood / spatial block":
            "neighbourhood-relative",
        "the shape block":
            "shape block",
        "rule adapters are blind to on-off attackers":
            "0.0--38",
        "the spatial scenario is where the methods separate":
            "spatially inconsistent scenario",
        "the benchmark is saturated":
            "perfectly separable",
        "the methods are compared on the same evidence":
            "same features",
    }
    for label, needle in probes.items():
        n = body.count(needle)
        print(f"  {n:>3}x  {label}")

    # --- where the same numbers are quoted ----------------------------
    print()
    print("=" * 100)
    print("REPEATED NUMERIC CLAIMS")
    print("=" * 100)
    for num in ["83.6", "93.8", "2.1", "+81.5", "96.7", "97.1", "87.6",
                "88.0--92.0", "0.0--38", "2.1\\%", "+4.5", "0.966"]:
        n = len(re.findall(re.escape(num), body))
        print(f"  {n:>3}x  {num}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
