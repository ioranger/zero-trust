"""Set the bold cells of the manuscript's tables.

Two kinds of table carry bold, and they mean different things:

  * In the tables that compare methods (the main comparison, the method
    group table, the spatial main table), bold marks the proposed model's
    advantage. A baseline that leads a column must not carry the emphasis,
    because the reader takes it as an endorsement of the proposed model.
    Those tables bold only the proposed model's own row, and only where the
    proposed model is ahead.

  * In the tables that ablate the proposed model itself (the probe-level
    table over feature sets, the architecture control over auxiliary-loss
    settings, the spatial arms over block configurations), every row is a
    configuration of the proposed model and no baseline is present. Bold
    there keeps its usual meaning, the best value in the column, because
    that is the question the table asks; the point of the table is which
    configuration is best, and that is sometimes not the published one.

This script applies both rules and is idempotent.

Usage:
    python -u artifacts/analysis/bold_table_cells.py
"""

from __future__ import annotations

from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# ---- tables that compare methods: bold only the proposed model's lead ----
METHOD_TABLE_PATCHES = [
    # Table 3: the main comparison. GDM-DTM's accuracy is the best of the
    # five rule adapters, but the proposed model is ahead of it, so the
    # emphasis belongs to the proposed model alone.
    ("    GDM-DTM \\cite{hu2025gdm} & \\textbf{87.6\\%} $\\pm$ 8.0\\% & "
     "80.4\\% $\\pm$ 13.6\\% & 82.2\\% $\\pm$ 3.5\\% \\\\",
     "    GDM-DTM \\cite{hu2025gdm} & 87.6\\% $\\pm$ 8.0\\% & "
     "80.4\\% $\\pm$ 13.6\\% & 82.2\\% $\\pm$ 3.5\\% \\\\"),

    # Table 4: the method-group table. The rule-based row's range is the
    # baseline's, so it carries no emphasis.
    ("    Rule-based aggregation (marginal, quantile, weighted-mean "
     "summaries) & 48.0--96.0 & 18.0--82.0 & \\textbf{0.0--38.0} \\\\",
     "    Rule-based aggregation (marginal, quantile, weighted-mean "
     "summaries) & 48.0--96.0 & 18.0--82.0 & 0.0--38.0 \\\\"),
]

# ---- tables that ablate the proposed model: bold the best in the column ----
ABLATION_TABLE_PATCHES = [
    # Table 5: the probe-level table over feature sets.
    ("    13 marginal & 0.9724 & 91.6\\% & 85.6\\% & 93.2\\% & "
     "95.2\\% & 62.6\\% \\\\",
     "    13 marginal & 0.9724 & 91.6\\% & 85.6\\% & \\textbf{93.2\\%} & "
     "\\textbf{95.2\\%} & 62.6\\% \\\\"),
    ("    5 shape only & 0.8993 & 84.6\\% & 70.3\\% & 17.0\\% & 71.4\\% & "
     "93.2\\% \\\\",
     "    5 shape only & 0.8993 & 84.6\\% & 70.3\\% & 17.0\\% & 71.4\\% & "
     "\\textbf{93.2\\%} \\\\"),

    # Table 10: the spatial arms. Every row is a block configuration of the
    # proposed model.
    ("    S-TIM, 13 dims (marginal) & 90.8 & 95.6 & 79.1 & 5.1 & 95.1 & "
     "84.6 \\\\",
     "    S-TIM, 13 dims (marginal) & \\textbf{90.8} & \\textbf{95.6} & "
     "79.1 & 5.1 & 95.1 & 84.6 \\\\"),
    ("    S-TIM, 18 dims (marginal $+$ shape) & 82.1 & 92.2 & 89.3 & 2.1 & "
     "97.4 & 85.8 \\\\",
     "    S-TIM, 18 dims (marginal $+$ shape) & 82.1 & 92.2 & 89.3 & 2.1 & "
     "\\textbf{97.4} & 85.8 \\\\"),
    ("Bold marks the values of the published three-block configuration.",
     "Bold marks the best value in the column."),

    # Table 11: the architecture control. Every row is an auxiliary-loss
    # setting of the proposed model, and the control arm is ahead of the
    # published one on three columns, which is the table's finding.
    ("    Control (all auxiliary losses off) & off ($w=0$) & 0.154 (chance "
     "0.250) & 90.0 & 97.5 & 96.1 & 90.2 \\\\",
     "    Control (all auxiliary losses off) & off ($w=0$) & 0.154 (chance "
     "0.250) & \\textbf{90.0} & \\textbf{97.5} & \\textbf{96.1} & 90.2 \\\\"),
    ("    Modality head only ($w=0.30$) & on & 0.983 & 88.0 & 97.1 & 95.6 & "
     "90.2 \\\\",
     "    Modality head only ($w=0.30$) & on & \\textbf{0.983} & 88.0 & "
     "97.1 & 95.6 & 90.2 \\\\"),
    ("    All four heads ($w=0.30$) & on & 0.985 & 86.0 & 97.1 & 95.6 & "
     "90.2 \\\\",
     "    All four heads ($w=0.30$) & on & \\textbf{0.985} & 86.0 & 97.1 & "
     "95.6 & 90.2 \\\\"),
    ("    Published (value, weight, action on) & off ($w=0$) & 0.143 (chance "
     "0.250) & \\textbf{88.0} & \\textbf{97.1} & \\textbf{95.7} & "
     "\\textbf{90.4} \\\\",
     "    Published (value, weight, action on) & off ($w=0$) & 0.143 (chance "
     "0.250) & 88.0 & 97.1 & 95.7 & 90.4 \\\\"),
]


def apply(text: str, patches, title: str) -> str:
    for old, new in patches:
        if text.count(old) == 1:
            text = text.replace(old, new)
            print(f"  [{title}] applied: {old[:58]}...")
        elif text.count(new) == 1:
            print(f"  [{title}] already in place: {new[:58]}...")
        else:
            print(f"!! [{title}] neither form found: {old[:70]}...")
            raise SystemExit(1)
    return text


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    text = apply(text, METHOD_TABLE_PATCHES, "methods")
    text = apply(text, ABLATION_TABLE_PATCHES, "ablation")
    TEX.write_text(text, encoding="utf-8", newline="")
    print("template.tex written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
