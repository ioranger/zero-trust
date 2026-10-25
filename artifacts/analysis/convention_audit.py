"""Academic-convention checks that are not spelling: abbreviations, numeric
formatting, float ordering and the like.

    python -u artifacts/analysis/convention_audit.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"

# abbreviation -> the expansion the manuscript should use at first mention
ABBREVIATIONS = {
    "S-TIM": "Spatio-Temporal Trust Inference Model",
    "AUC": "area under the curve",
    "FPR": "false positive rate",
    "TPR": "true positive rate",
    "F1": "F1 score",
    "CI": "confidence interval",
    "TSR": "task-success rate",
    "RL": "reinforcement learning",
    "FL": "federated learning",
    "SVD": "singular value decomposition",
    "MDP": "Markov decision process",
    "POMDP": "partially observable Markov decision process",
    "UAV": "unmanned aerial vehicle",
    "FANET": "flying ad hoc network",
    "GNSS": "global navigation satellite system",
    "GPS": "global positioning system",
    "RF": "radio frequency",
    "MAV": "multi-agent vehicle",
    "CPU": "central processing unit",
}


def main() -> int:
    raw = TEX.read_text(encoding="utf-8")
    body = raw.split("\\begin{document}", 1)[-1]
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("%"))
    # the bibliography is not prose: an expansion that only appears in a
    # reference title does not expand the abbreviation in the text
    body = body.split("\\bibitem{", 1)[0]
    lines = body.splitlines()

    print("=" * 96)
    print("1. ABBREVIATIONS: first use in the body")
    print("=" * 96)
    for abbr, expansion in ABBREVIATIONS.items():
        hits = [(i, l) for i, l in enumerate(lines, 1)
                if re.search(r"(?<![A-Za-z])" + abbr + r"s?(?![A-Za-z])", l)
                and not re.match(r"^\s*\\Title\{", l)]
        if not hits:
            continue
        first = hits[0][1]
        where = hits[0][0]
        # the expansion has to appear at the first use or shortly after it:
        # a heading that carries the abbreviation is normally expanded in the
        # sentence below it. The text is compared without line breaks, because
        # an expansion may straddle two lines.
        upto = " ".join(" ".join(lines[: where + 8]).split())
        expanded = expansion.lower() in upto.lower()
        print(f"  {abbr:<6} first at L{where:<5} "
              f"{'expanded nearby' if expanded else 'NOT expanded at first use'}")
        if not expanded:
            print(f"         {first.strip()[:140]}")

    print()
    print("=" * 96)
    print("2. NUMERIC FORMATTING")
    print("=" * 96)
    patterns = [
        ("threshold written as 0.6 and 0.60",
         r"(?<![0-9.])0\.6(?![0-9])"),
        ("percentage with a space before %", r"\d\s+\\%"),
        ("decimal without a leading zero", r"(?<![\d.])\.\d+"),
        ("two decimals on a percentage", r"\d\.\d{2}\\%"),
        ("t-value without a test name", r"\$t\s*="),
    ]
    for label, pat in patterns:
        rows = [(i, l) for i, l in enumerate(lines, 1) if re.search(pat, l)]
        # the bibliography and the tables carry their own conventions
        rows = [(i, l) for i, l in rows if "doi.org" not in l and "http" not in l]
        print(f"  {label:<42} {len(rows)} hit(s)")
        for i, l in rows[:4]:
            print(f"      L{i:<5} {l.strip()[:130]}")

    print()
    print("=" * 96)
    print("3. FLOAT ORDER: is every figure and table referenced before it floats?")
    print("=" * 96)
    for kind in ("figure", "table"):
        for m in re.finditer(r"\\begin\{" + kind + r"\}.*?\\label\{([^}]+)\}",
                             body, re.DOTALL):
            label = m.group(1)
            end = body.find("\\end{" + kind + "}", m.start())
            chunk = body[:m.start()]
            # the last mention before the float
            mentions = [mm.start() for mm in re.finditer(re.escape("\\ref{") + label + "}", chunk)]
            after = body[end:end + 4000]
            after_mentions = len(re.findall(re.escape("\\ref{") + label + "}", after))
            status = "referenced before" if mentions else (
                "referenced only after" if after_mentions else "NEVER REFERENCED")
            print(f"  {label:<28} {status}")

    print()
    print("=" * 96)
    print("4. ABBREVIATION AND PUNCTUATION SPOT CHECKS")
    print("=" * 96)
    for label, pat in (("e.g. / i.e. without a comma", r"(?<![,\s])(e\.g\.|i\.e\.)"),
                       ("etc. at the end of a clause", r"\betc\."),
                       ("very / really / quite", r"\b(very|really|quite)\b"),
                       ("obviously / clearly / of course", r"\b(obviously|clearly|of course)\b"),
                       ("we believe / we think", r"\bwe (believe|think|feel)\b"),
                       ("in our opinion", r"\bin our opinion\b")):
        rows = [(i, l) for i, l in enumerate(lines, 1) if re.search(pat, l, re.IGNORECASE)]
        print(f"  {label:<40} {len(rows)} hit(s)")
        for i, l in rows[:4]:
            print(f"      L{i:<5} {l.strip()[:130]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
