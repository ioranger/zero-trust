"""The spatial scenario's main comparison table.

The published table cannot separate the method classes because every learned
method reaches about 97% on it: the training split of that generator is
perfectly separable, so the aggregate metric compresses the classes and the
proposed model sits inside the same band as its feature-matched control.

The spatially inconsistent scenario does not have that property, because it
contains an attack class that the per-node learners cannot resolve at all.
This script builds the same comparison as the published table, over the same
eight methods, in that scenario, from the committed arm logs:

    python -u artifacts/analysis/spatial_main_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "analysis" / "runs"

PROTOCOL_ARM = "spatial_position_23dim"   # per-node baselines, main protocol
FUSION_ARM = "spatial_position_fusion"     # every learner gets the same vector
METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy",
           "LR-Trust", "MLP-Trust", "S-TIM"]


def baseline_table(arm: str) -> dict:
    f = RUNS / arm / "tables" / "baseline_comparison.csv"
    d = pd.read_csv(f, encoding="utf-8-sig").set_index("method")
    out = {}
    for m in d.index:
        row = {}
        for col in ("accuracy", "f_score", "tsr"):
            s = str(d.loc[m, col]).replace("\u00b1", "+-").replace("卤", "+-")
            parts = s.split("+-")
            row[col] = float(parts[0].strip())
            row[col + "_sd"] = float(parts[1].strip()) if len(parts) > 1 else 0.0
        out[m] = row
    return out


def atk_table(arm: str) -> dict:
    f = RUNS / arm / "logs" / "per_seed_attack_type_metrics.csv"
    d = pd.read_csv(f)
    d = d.drop_duplicates(subset=["seed", "method", "attack_type"])
    d = d[d["malicious_ratio"].abs() - 0.30 < 1e-9]
    out = {}
    for m in d["method"].unique():
        out[m] = {}
        for t in d["attack_type"].unique():
            sub = d[(d["method"] == m) & (d["attack_type"] == t)]
            out[m][t] = float(sub["detection_rate"].mean()) * 100
    return out


def main() -> int:
    base = baseline_table(PROTOCOL_ARM)
    atk = atk_table(PROTOCOL_ARM)
    fus_base = baseline_table(FUSION_ARM)
    fus_atk = atk_table(FUSION_ARM)

    print("=" * 108)
    print("SPATIAL SCENARIO -- the published comparison, in a scenario that can "
          "discriminate")
    print(f"protocol arm: {PROTOCOL_ARM}    fusion arm: {FUSION_ARM}")
    print("=" * 108)
    print(f"{'method':<14}{'accuracy':>10}{'F-score':>10}{'TSR':>8}"
          f"{'constant':>10}{'dormant':>10}{'on-off':>9}{'position-inc.':>15}")
    print("-" * 108)
    for m in METHODS:
        b = base[m]
        a = atk[m]
        print(f"{m:<14}{b['accuracy']:>10.1f}{b['f_score']:>10.1f}{b['tsr']:>8.1f}"
              f"{a.get('constant', float('nan')):>10.1f}{a.get('dormant', float('nan')):>10.1f}"
              f"{a.get('on-off', float('nan')):>9.1f}"
              f"{a.get('position-inconsistent', float('nan')):>15.1f}")
    print("-" * 108)
    print("with the neighbourhood block also given to the per-node baselines:")
    print(f"{'method':<14}{'accuracy':>10}{'F-score':>10}{'TSR':>8}"
          f"{'constant':>10}{'dormant':>10}{'on-off':>9}{'position-inc.':>15}")
    print("-" * 108)
    for m in METHODS:
        b = fus_base[m]
        a = fus_atk[m]
        print(f"{m:<14}{b['accuracy']:>10.1f}{b['f_score']:>10.1f}{b['tsr']:>8.1f}"
              f"{a.get('constant', float('nan')):>10.1f}{a.get('dormant', float('nan')):>10.1f}"
              f"{a.get('on-off', float('nan')):>9.1f}"
              f"{a.get('position-inconsistent', float('nan')):>15.1f}")
    print("-" * 108)
    print("Rows 1--8 of the first block are the main protocol, in which the "
          "per-node baselines never")
    print("receive the neighbourhood block. The second block is the "
          "fusion-mechanism ablation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
