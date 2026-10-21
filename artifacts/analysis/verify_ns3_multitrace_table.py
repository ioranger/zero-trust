"""Check the manuscript's packet-level table against the committed numbers.

Table `tab:ns3_multitrace` in the manuscript is the only result in the paper
that is measured on packet data, and it is the one table whose numbers were
produced by a harness that runs outside the generator: five ns-3 traces,
converted to trust streams and evaluated by the committed multi-trace driver.
A cell that drifts from the committed aggregate is therefore easy to miss and
worth a hard check.

The script does three things:

  1. parses the LaTeX table out of the manuscript and compares every cell
     against `artifacts/outputs/tables/ns3_multitrace.csv`,
  2. recomputes the paired over-trace differences and their t and p values
     from `artifacts/outputs/tables/ns3_multitrace_per_trace.csv` and
     compares them against the numbers in the prose,
  3. checks that the numbers the prose states in words are the numbers the
     data actually gives, including the adverse ones.

    python -u artifacts/analysis/verify_ns3_multitrace_table.py
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"
TABLE_CSV = ROOT / "artifacts" / "outputs" / "tables" / "ns3_multitrace.csv"
PER_TRACE_CSV = (ROOT / "artifacts" / "outputs" / "tables"
                  / "ns3_multitrace_per_trace.csv")

failures: list[str] = []
checks = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  [ok ] {label}")
    else:
        print(f"  [FAIL] {label}" + (f"  ({detail})" if detail else ""))
        failures.append(label)


def latex_table_rows(text: str, label: str) -> list[list[str]]:
    """Return the rows of the tabular that carries `label`."""
    start = text.find(f"\\label{{{label}}}")
    if start < 0:
        return []
    begin = text.find("\\begin{tabular}", start)
    end = text.find("\\end{tabular}", begin)
    if begin < 0 or end < 0:
        return []
    body = text[begin:end]
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line or "&" not in line:
            continue
        cells = [c.strip().rstrip("\\").strip() for c in line.split("&")]
        cells = [c for c in cells if c != ""]
        rows.append(cells)
    return rows


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    agg = pd.read_csv(TABLE_CSV).set_index("method")
    per_trace = pd.read_csv(PER_TRACE_CSV)

    # ------------------------------------------------------------- 1. cells
    print("=" * 100)
    print("1. the table in the manuscript matches the committed aggregate")
    print("=" * 100)
    rows = latex_table_rows(text, "tab:ns3_multitrace")
    if not rows:
        check(False, "the table tab:ns3_multitrace is present in the manuscript")
        return 1

    header = [h.strip() for h in rows[0]]
    expected_header = ["Method", "Accuracy", "F-score", "Recall", "AUC",
                       "constant", "dormant", "on--off"]
    check(header == expected_header, "the table header is the expected one",
          f"{header}")

    name_map = {"S-TIM (ours)": "S-TIM"}
    body = rows[1:]
    check(len(body) == len(agg), "the table has one row per method",
          f"{len(body)} rows vs {len(agg)} methods")

    cols = [("accuracy", 1), ("f_score", 2), ("recall", 3), ("auc", 4),
            ("detection_constant", 5), ("detection_dormant", 6),
            ("detection_on_off", 7)]
    for row in body:
        label = name_map.get(row[0], row[0])
        if label not in agg.index:
            check(False, f"method {row[0]} is in the committed aggregate")
            continue
        for key, idx in cols:
            try:
                printed = float(row[idx])
            except ValueError:
                check(False, f"{label}: {key} is a number", row[idx])
                continue
            actual = float(agg.loc[label, key])
            check(abs(printed - actual) < 5e-4,
                  f"{label}: {key} is {printed:.3f}",
                  f"aggregate says {actual:.6f}")

    # ------------------------------------------------- 2. the paired numbers
    print()
    print("=" * 100)
    print("2. the paired over-trace differences in the prose")
    print("=" * 100)
    for control, metric, want_delta, want_p in (
            ("MLP-Trust", "accuracy", 4.50, 0.0367),
            ("MLP-Trust", "f_score", 10.87, 0.0550),
            ("LR-Trust", "accuracy", 63.00, 0.0000),
            ("LR-Trust", "f_score", 40.13, 0.0004)):
        piv = per_trace.pivot_table(index="trace_name", columns="method",
                                    values=metric)
        diff = ((piv["S-TIM"] - piv[control]) * 100).dropna()
        sd = diff.std(ddof=1)
        t = diff.mean() / (sd / math.sqrt(len(diff)))
        p = 2.0 * stats.t.sf(abs(t), df=len(diff) - 1)
        check(abs(diff.mean() - want_delta) < 0.02,
              f"S-TIM vs {control} on {metric}: {diff.mean():+.2f} pp",
              f"expected {want_delta:+.2f}")
        check(abs(p - want_p) < 5e-4,
              f"S-TIM vs {control} on {metric}: p = {p:.4f}",
              f"expected {want_p:.4f}")

    # -------------------------------------------- 3. the numbers in the prose
    print()
    print("=" * 100)
    print("3. the numbers the prose states, including the adverse ones")
    print("=" * 100)
    prose_checks = [
        ("$+4.5$~pp accuracy", "the paired accuracy gain over MLP-Trust"),
        ("$+10.9$~pp F-score", "the paired F-score gain over MLP-Trust"),
        ("$p = 0.037$", "the paired accuracy p value"),
        ("$p = 0.055$", "the paired F-score p value"),
        ("$p=0.037$", "the paired accuracy p value, compact form"),
        ("$p=0.055$", "the paired F-score p value, compact form"),
        ("0.930 accuracy and 0.863 F-score", "S-TIM's packet accuracy and F-score"),
        ("0.885 and 0.754 for MLP-Trust", "MLP-Trust's packet accuracy and F-score"),
        ("0.966", "S-TIM's packet AUC"),
        ("0.767 at a precision of 1.000", "S-TIM's packet recall and precision"),
        ("0.510", "GALTrust's packet accuracy"),
        ("98 of the 140 benign nodes", "GALTrust's false-positive count"),
        ("decision threshold of 0.60", "the decision threshold that does not transfer"),
        ("four of the five rule aggregators", "the size of the competitive rule class"),
    ]
    for needle, what in prose_checks:
        check(needle in text, f"the prose states {what}", f"missing: {needle}")

    # The thresholds the prose names must be the ones the code uses.
    import json
    policy = json.loads((ROOT / "artifacts" / "outputs" / "logs"
                         / "marl_policy.json").read_text(encoding="utf-8"))
    check(float(policy["threshold"]) == 0.6,
          "S-TIM's threshold in marl_policy.json is 0.60",
          str(policy["threshold"]))

    # The gate must have accepted all five traces, or the table's "five" is
    # not the number of valid measurements.
    verdict_path = (ROOT / "artifacts" / "outputs" / "tables"
                    / "ns3_multitrace_verdict.json")
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    check(int(verdict["valid_measurements"]) == 5,
          "all five traces were valid measurements",
          str(verdict["valid_measurements"]))
    degenerate = sorted({c for t in verdict["traces"]
                         for c in t.get("degenerate_columns", [])})
    check(degenerate == ["shape_switch_cv"],
          "the only degenerate column is the switch-interval CV",
          str(degenerate))
    check("shape_switch_cv" in text
          or "coefficient of variation of the switch intervals" in text,
          "the prose discloses the degenerate column")

    # The old single-trace table must still be present and still be labelled
    # as a regime diagnosis rather than as a result.
    check("\\label{tab:ns3_trace_validation}" in text,
          "the single-trace table is still in the manuscript")
    check("as a regime diagnosis" in text or "regime diagnosis" in text,
          "the single-trace table is still described as a regime diagnosis")

    print()
    print("=" * 100)
    if failures:
        print(f"{len(failures)} of {checks} checks FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"all {checks} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
