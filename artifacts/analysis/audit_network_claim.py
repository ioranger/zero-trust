"""Search for any remaining suggestion that a different network would not do.

The manuscript's remaining claim is that the representation, rather than the
rule aggregators' summarisation, is what closes the gap, and that the encoder
is not what closes it. A reader who takes either of those as "a different
network would not have helped" is reading more than the paper says. This
script lists the sentences that come closest to that reading, so the
downgrade can be checked for completeness.

Usage:
    python -u artifacts/analysis/audit_network_claim.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# phrases that would imply the network is irrelevant
PATTERNS = [
    r"not the classifier",
    r"deficiency of the classifier",
    r"choice of classifier stops mattering",
    r"rather than the network",
    r"the network is not",
    r"any classifier",
    r"every classifier",
    r"no classifier",
    r"the classifier",
    r"a classifier",
    r"the network\b",
    r"the encoder\b",
]


def main() -> int:
    lines = TEX.read_text(encoding="utf-8").splitlines()
    print("=" * 78)
    print("sentences mentioning a classifier or a network")
    print("=" * 78)
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("%"):
            continue
        for pat in PATTERNS:
            m = re.search(pat, line, re.IGNORECASE)
            if not m:
                continue
            s = max(0, m.start() - 150)
            e = min(len(line), m.end() + 200)
            print(f"  L{i} [{pat}]:")
            print(f"     ...{line[s:e]}...")
            print()
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
