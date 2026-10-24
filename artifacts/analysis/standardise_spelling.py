"""Standardise the manuscript's spelling.

The source mixes British and American forms of the same words (behaviour and
behavior, neighbourhood and neighborhood, normalised and normalized, and so
on). This script rewrites the body to British English, which is the house
style of the MDPI class the manuscript uses and which the terms the paper
itself introduces already follow.

Only the body is touched: the preamble is left alone, comment lines are left
alone, and a word immediately preceded by a backslash is never rewritten, so
LaTeX macros such as \\centering keep their names.

    python -u artifacts/analysis/standardise_spelling.py [--dry]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"

# British form <- the forms that must go
REPLACEMENTS: list[tuple[str, str]] = [
    ("behaviors", "behaviours"),
    ("behavioral", "behavioural"),
    ("behavior", "behaviour"),
    ("neighborhood-relative", "neighbourhood-relative"),
    ("neighborhoods", "neighbourhoods"),
    ("neighborhood", "neighbourhood"),
    ("normalized", "normalised"),
    ("normalizing", "normalising"),
    ("normalization", "normalisation"),
    ("modeled", "modelled"),
    ("modeling", "modelling"),
    ("optimization", "optimisation"),
    ("optimizer", "optimiser"),
    ("optimized", "optimised"),
    ("optimizing", "optimising"),
    ("optimize", "optimise"),
    ("summarization", "summarisation"),
    ("summarized", "summarised"),
    ("summarizes", "summarises"),
    ("summarize", "summarise"),
    ("characterization", "characterisation"),
    ("characterized", "characterised"),
    ("characterize", "characterise"),
    ("generalization", "generalisation"),
    ("generalized", "generalised"),
    ("generalize", "generalise"),
    ("labeled", "labelled"),
    ("labeling", "labelling"),
    ("favorable", "favourable"),
    ("unfavorable", "unfavourable"),
    ("favor", "favour"),
    ("recognizes", "recognises"),
    ("recognize", "recognise"),
    ("recognized", "recognised"),
    ("toward ", "towards "),
    ("analyzed", "analysed"),
    ("analyze", "analyse"),
]


def main() -> int:
    dry = "--dry" in sys.argv
    raw = TEX.read_text(encoding="utf-8")
    head, sep, body = raw.partition("\\begin{document}")
    if not sep:
        print("!! the document body marker was not found")
        return 2

    out_lines = []
    changes: list[tuple[int, str, str]] = []
    for n, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith("%"):
            out_lines.append(line)
            continue
        new = line
        for us, uk in REPLACEMENTS:
            pattern = re.compile(r"(?<!\\)\b" + re.escape(us) + r"\b")
            def sub(m: re.Match) -> str:
                changes.append((n, m.group(0), uk))
                return uk
            new = pattern.sub(sub, new)
        out_lines.append(new)

    print("=" * 92)
    print("SPELLING STANDARDISATION (British English)")
    print("=" * 92)
    counts: dict[tuple[str, str], int] = {}
    for _n, was, now in changes:
        counts[(was, now)] = counts.get((was, now), 0) + 1
    for (was, now), c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {was:<26} -> {now:<26} {c:>3}x")
    print(f"  total replacements: {len(changes)}")
    if dry:
        print("  (dry run, nothing written)")
        return 0

    TEX.write_text(head + sep + "\n".join(out_lines), encoding="utf-8")
    print(f"  written to {TEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
