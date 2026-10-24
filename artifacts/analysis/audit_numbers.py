"""Cross-check the numbers the manuscript quotes against one another.

The prose states the same quantities in several places: the abstract, the
contributions, the results, the tables and the conclusions. A claim that
changes value between two of those places is a logical inconsistency even
when each place is individually true.

This script collects the recurring quantities and reports every occurrence
with its line, so the values can be compared.

Usage:
    python -u artifacts/analysis/audit_numbers.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# quantity -> the regular expression that finds it in the prose
QUANTITIES = {
    "S-TIM accuracy, published scenario": r"97\.1\\?%",
    "S-TIM F-score, published scenario": r"95\.7\\?%",
    "S-TIM proxy, published scenario": r"90\.4\\?%",
    "margin over the strongest rule adapter, accuracy": r"\+49\.8",
    "margin over the strongest rule adapter, F-score": r"\+43\.9",
    "margin over the strongest rule adapter, proxy": r"\+13\.0",
    "margin over GDM-DTM, published scenario, accuracy": r"\+9\.0",
    "margin over GDM-DTM, published scenario, F-score": r"\+15\.0",
    "spatial accuracy": r"93\.8\\?%",
    "spatial F-score": r"89\.4\\?%",
    "spatial proxy": r"88\.9\\?%",
    "spatial class mean": r"89\.0\\?%",
    "rule adapters' spatial accuracy range": r"39\.7--44\.0",
    "rule adapters' spatial F-score range": r"44\.9--45\.5",
    "rule adapters' spatial proxy range": r"74\.5--75\.9",
    "forger detection with the neighbourhood block": r"83\.6\\?%",
    "forger detection without it": r"2\.1\\?%",
    "on--off detection, proposed model": r"88\.0\\?%",
    "on--off detection, rule adapters": r"0\.0--38",
    "on--off detection without the shape block": r"72\.0\\?%",
    "paired spatial gain": r"\+81\.5",
    "auxiliary target recoverable from the features": r"96\.7\\?%",
    "modality head validation accuracy": r"0\.9(8[35])",
    "benign specificity of the rule adapters, spatial": r"20\.7--30\.3",
    "benign specificity of the rule adapters, published": r"91\.8--99\.8",
    "duty sweep, S-TIM at a 20% duty": r"68\.0",
    "duty sweep, GDM-DTM at a 20% duty": r"2\.0\\?%",
    "duty sweep, GDM-DTM at a 5% duty": r"0\.0\\?%",
    "robustness accuracy advantage, low": r"\+46\.6",
    "robustness accuracy advantage, high": r"\+52\.3",
    "robustness F-score advantage, low": r"\+41\.7",
    "robustness F-score advantage, high": r"\+44\.5",
    "forger detection across the sweep, low": r"72\.9",
    "forger detection across the sweep, high": r"88\.0\\?%",
}


def main() -> int:
    lines = TEX.read_text(encoding="utf-8").splitlines()
    for title, pat in QUANTITIES.items():
        hits = []
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("%"):
                continue
            for m in re.finditer(pat, line):
                hits.append(i)
        places = ", ".join(str(h) for h in hits)
        print(f"{title:<52} {len(hits):>2}x  lines {places}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
