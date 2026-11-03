#!/usr/bin/env python3
"""Generate the LaTeX body of the dimension-budget table.

Reads artifacts/outputs/tables/channel_profile_dimension_budget.csv and
writes the tabular body of Table "dimension_budget" as a .tex fragment, so
that the numbers in the manuscript and the numbers in the replication
package come from the same file.

Usage:
    python -u artifacts/analysis/make_budget_table.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "artifacts" / "outputs" / "tables" / "channel_profile_dimension_budget.csv"
OUT = ROOT / "artifacts" / "outputs" / "tables" / "channel_profile_dimension_budget.tex"

FACTORS = ["T1", "T2", "T3", "T4", "T5"]
GROUP = {
    5: "The proposed configuration (five observed dimensions)",
    4: "Four observed dimensions",
    3: "Three observed dimensions",
    2: "Two observed dimensions",
    1: "One observed dimension",
}


def rng(values: list[float]) -> str:
    vals = [v for v in values if not pd.isna(v)]
    if not vals:
        return "--"
    lo, hi = min(vals), max(vals)
    if abs(hi - lo) < 0.05:
        return "%.0f" % lo
    return "%.0f--%.0f" % (lo, hi)


def main() -> int:
    df = pd.read_csv(TABLE)
    df["_obs"] = df["observed"].apply(
        lambda s: [FACTORS.index(f.strip()) for f in str(s).split(",")])
    df = df.sort_values(by="k", ascending=False)
    df = df.assign(_key=df["_obs"].apply(tuple))
    df = df.sort_values(by="_key", kind="stable")
    df = df.drop(columns=["_obs", "_key"])

    lines = []
    lines.append("  \\begin{tabular}{l c c c c c c c}")
    lines.append("    \\toprule")
    lines.append("    Dimensions observed & columns & accuracy (\\%) & F-score (\\%) "
                 "& TSR (\\%) & detection, observed (\\%) & detection, unobserved (\\%) "
                 "& $\\Delta$ accuracy (pp) \\\\")
    lines.append("    \\midrule")
    for k in sorted(df["k"].unique(), reverse=True):
        group = df[df["k"] == k]
        lines.append("    \\multicolumn{8}{@{}l}{\\emph{%s}} \\\\" % GROUP[k])
        for _, row in group.iterrows():
            observed = [f.strip() for f in str(row["observed"]).split(",")]
            det_obs = [row["detection_" + f] for f in observed]
            det_un = [row["detection_" + f] for f in FACTORS if f not in observed]
            if k == 5:
                acc = "\\textbf{%.1f}" % row["accuracy"]
                fs = "\\textbf{%.1f}" % row["f_score"]
                tsr = "\\textbf{%.1f}" % row["tsr"]
                delta = "--"
            else:
                acc = "%.1f" % row["accuracy"]
                fs = "%.1f" % row["f_score"]
                tsr = "%.1f" % row["tsr"]
                delta = "$+%0.1f$ ($p<0.0001$)" % row["delta_accuracy"]
            lines.append(
                "    %s & %d & %s & %s & %s & %s & %s & %s \\\\"
                % (", ".join(observed), int(row["columns"]), acc, fs, tsr,
                   rng(det_obs), rng(det_un) if det_un else "--", delta))
        if k != 1:
            lines.append("    \\midrule")
    lines.append("    \\bottomrule")
    lines.append("  \\end{tabular}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote " + str(OUT))

    for k in sorted(df["k"].unique(), reverse=True):
        group = df[df["k"] == k]
        print("k=%d  accuracy %.1f--%.1f  mean %.1f   F %.1f--%.1f   TSR %.1f--%.1f"
              % (k, group["accuracy"].min(), group["accuracy"].max(),
                 group["accuracy"].mean(),
                 group["f_score"].min(), group["f_score"].max(),
                 group["tsr"].min(), group["tsr"].max()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
