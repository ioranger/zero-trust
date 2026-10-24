"""List the self-positioning sentences that name the two framings.

The manuscript contrasts itself with the two framings in order to say what it
is not, which is what invites the misreading the author wants to avoid. This
script lists the sentences that do that, so each can be restated as a
statement of what the paper does rather than as a denial.

The related work and the system model are not listed: they state what the
field does, which is a different register and is kept.

Usage:
    python -u artifacts/analysis/list_marl_zeros.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# the contrasts: the paper set against the two framings
CONTRAST = re.compile(
    r"(overstate what was implemented|"
    r"rather than a deployment-ready|"
    r"rather than a validated MARL|"
    r"deployment-ready zero-trust|"
    r"narrower than a full|"
    r"not reinforcement learning|"
    r"no reward return|"
    r"not an offline or online|"
    r"is deliberately narrower|"
    r"not a multi-task supervised|"
    r"the intended system|"
    r"not implemented in the current|"
    r"intended architecture|"
    r"intended deployment|"
    r"does not emulate decentralized|"
    r"no closed state-feedback|"
    r"no on-board agents)", re.IGNORECASE)


def main() -> int:
    lines = TEX.read_text(encoding="utf-8").splitlines()
    print("=" * 78)
    print("the self-positioning contrasts")
    print("=" * 78)
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("%"):
            continue
        m = CONTRAST.search(line)
        if not m:
            continue
        s = max(0, m.start() - 260)
        e = min(len(line), m.end() + 260)
        print(f"  L{i}: ...{line[s:e]}...")
        print()
    print("=" * 78)
    print("the keyword line")
    print("=" * 78)
    for i, line in enumerate(lines, 1):
        if "\\keyword{" in line:
            print(f"  L{i}: {line.strip()}")
    print()
    print("=" * 78)
    print("the two related-work subsection headings (kept)")
    print("=" * 78)
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("\\subsection{") and ("Zero-Trust" in s or "MARL" in s):
            print(f"  L{i}: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
