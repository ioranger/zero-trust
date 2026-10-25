"""Fail if the manuscript or the figure sources mention an agent.

The main figure no longer shows agents, so no sentence and no drawn label may
describe them either. This is the guard for that rule: it scans the manuscript
body and the TikZ sources of the figures and reports every hit.

Reference titles are listed but do not fail the check: a published title is
original text and cannot be rewritten.

Usage:
    python -u artifacts/analysis/check_no_agent_terms.py
"""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(r"F:\zero trust\zero-trust\paper")
TEX = PAPER / "template.tex"

# the words that carry the agent framing
PATTERNS = {
    "agent (any form)": r"[Aa]gents?\b",
    "Thinker Agent": r"Thinker\s+[Aa]gents?",
    "Intelligent Decision Agent": r"Intelligent\s+Decision\s+[Aa]gent",
    "on-board agent": r"on-board\s+[Aa]gents?",
    "multi-agent": r"multi-agent",
    "Thinker (any form)": r"\bThinkers?\b",
}

# a caption may not describe an agent either
FIGTEX = sorted(PAPER.glob("figures/*.tex"))


def hits(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, text):
            out.append((name, m.group(0)))
    return out


def main() -> int:
    raw = TEX.read_bytes().decode("utf-8")
    lines = raw.split("\n")

    # the bibliography starts at the first \bibitem
    first_bib = next((i for i, l in enumerate(lines) if "\\bibitem{" in l), len(lines))

    failures = 0

    print("=" * 78)
    print("manuscript body")
    print("=" * 78)
    for i, line in enumerate(lines[:first_bib], 1):
        if line.lstrip().startswith("%"):
            continue
        for name, word in hits(line):
            print(f"  L{i}: [{name}] {word}")
            failures += 1
    print(f"  {failures} hit(s)")

    print()
    print("=" * 78)
    print("figure sources")
    print("=" * 78)
    fig_failures = 0
    for path in FIGTEX:
        # a LaTeX comment is not drawn, so it does not reach the reader
        text = "\n".join(
            l for l in path.read_bytes().decode("utf-8").split("\n")
            if not l.lstrip().startswith("%")
        )
        for name, word in hits(text):
            print(f"  {path.name}: [{name}] {word}")
            fig_failures += 1
    print(f"  {fig_failures} hit(s) in {len(FIGTEX)} file(s)")
    failures += fig_failures

    print()
    print("=" * 78)
    print("reference titles (listed, not a failure)")
    print("=" * 78)
    n = 0
    for line in lines[first_bib:]:
        if line.lstrip().startswith("%"):
            continue
        for name, word in hits(line):
            print(f"  [{name}] {word}")
            n += 1
    print(f"  {n} hit(s)")

    print()
    if failures:
        print(f"[FAIL] {failures} agent mention(s) in the manuscript or the figures")
        return 1
    print("[OK] no agent mention in the manuscript body or the figure sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
