"""Check that every qualitative claim in the abstract holds on the data.

The abstract describes the method's performance in words rather than in
figures, which is only defensible if each statement is true of the data. This
script reads the abstract and checks the claims it makes against the tables
the paper is built on:

- the five rule-based comparators all lose accuracy as the malicious share
  grows from 10% to 50%
- the proposed model does not lose accuracy over the same grid
- the proposed model is more accurate than every rule-based comparator in the
  published scenario
- the proposed model leads every rule adapter in the spatial scenario

It also reports the numbers behind each claim, so a reader can see what the
wording rests on.

Usage:
    python -u artifacts/analysis/check_abstract_claims.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"
TABLES = ROOT / "artifacts" / "outputs" / "tables"

RATIO_CSV = TABLES / "multi_ratio.csv"
BASE_CSV = TABLES / "baseline_comparison.csv"

RULE_METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]


def ratio_table() -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    lines = RATIO_CSV.read_text(encoding="utf-8").splitlines()
    header = [h.strip() for h in lines[0].split(",")]
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        acc = {}
        for col, p in zip(header[1:], parts[1:]):
            m = re.match(r"([\d.]+)", p)
            if m:
                acc[col] = float(m.group(1))
        rows[parts[0]] = acc
    return rows


def csv_accuracy(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = [p.strip() for p in line.split(",")]
        m = re.match(r"([\d.]+)", parts[1]) if len(parts) > 1 else None
        if m:
            out.setdefault(parts[0], float(m.group(1)))
    return out


def spatial_accuracy() -> dict[str, float]:
    text = TEX.read_bytes().decode("utf-8")
    lab = text.find(r"\label{tab:spatial_main}")
    if lab < 0:
        return {}
    block = text[text.rfind(r"\begin{table", 0, lab): text.find(r"\end{table}", lab)]
    out: dict[str, float] = {}
    for m in re.finditer(r"^\s*(S-TIM|MFA|FUBA|GALTrust|GDM-DTM|AHP-Entropy)"
                         r"(?:\s*\(ours\))?\s*&\s*(?:\\textbf\{)?([\d.]+)", block, re.M):
        out.setdefault(m.group(1), float(m.group(2)))
    return out


def abstract_text() -> str:
    text = TEX.read_bytes().decode("utf-8")
    m = re.search(r"\\abstract\{(.*?)\}\s*\n", text, re.S)
    return m.group(1).strip() if m else ""


def main() -> int:
    ab = abstract_text()
    ratios = ratio_table()
    pub = csv_accuracy(BASE_CSV)
    spa = spatial_accuracy()
    bad: list[str] = []

    print("=" * 78)
    print("the claims the abstract makes")
    print("=" * 78)
    for m in re.finditer(r"[^.]*\b(degrade|falls away|more accurate|leads every)\b[^.]*\.",
                         ab):
        print(f"  - {m.group(0).strip()}")

    print()
    print("=" * 78)
    print("1. the five rule adapters lose accuracy as the malicious share grows")
    print("=" * 78)
    for m in RULE_METHODS:
        r = ratios.get(m, {})
        ok = r and r.get("accuracy_50pct", 100) < r.get("accuracy_10pct", 0)
        print(f"  [{'ok' if ok else 'FAIL'}] {m:<12} "
              f"10%: {r.get('accuracy_10pct')}  ->  50%: {r.get('accuracy_50pct')}")
        if not ok:
            bad.append(f"{m} does not degrade from 10% to 50%")

    print()
    print("=" * 78)
    print("2. the proposed model holds its accuracy over the same grid")
    print("=" * 78)
    s = ratios.get("S-TIM", {})
    accs = [v for k, v in s.items() if k.startswith("accuracy_")]
    spread = max(accs) - min(accs) if accs else 999
    ok = spread <= 5.0
    print(f"  [{'ok' if ok else 'FAIL'}] S-TIM accuracy over the grid: "
          f"{', '.join(f'{v}' for v in accs)} (spread {spread:.1f} pp)")
    if not ok:
        bad.append(f"S-TIM accuracy varies by {spread:.1f} pp over the ratio grid")

    print()
    print("=" * 78)
    print("3. the proposed model beats every rule adapter in the published scenario")
    print("=" * 78)
    for m in RULE_METHODS:
        ok = m in pub and "S-TIM" in pub and pub[m] < pub["S-TIM"]
        print(f"  [{'ok' if ok else 'FAIL'}] {m:<12} {pub.get(m)}  vs  "
              f"S-TIM {pub.get('S-TIM')}")
        if not ok:
            bad.append(f"{m} is not below S-TIM in the published scenario")

    print()
    print("=" * 78)
    print("4. the proposed model leads every rule adapter in the spatial scenario")
    print("=" * 78)
    for m in RULE_METHODS:
        ok = m in spa and "S-TIM" in spa and spa[m] < spa["S-TIM"]
        print(f"  [{'ok' if ok else 'FAIL'}] {m:<12} {spa.get(m)}  vs  "
              f"S-TIM {spa.get('S-TIM')}")
        if not ok:
            bad.append(f"{m} is not below S-TIM in the spatial scenario")

    print()
    if bad:
        for b in bad:
            print(f"[FAIL] {b}")
        return 1
    print("[OK] every qualitative claim in the abstract holds on the data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
