"""Robustness of the spatial scenario's separation.

The spatial scenario is the manuscript's headline detector result, so the
separation it reports has to hold outside the parameter point it was measured
at. Each arm of the sweep changes exactly one parameter of the headline
configuration and leaves the generator, the attack mix, the seeds and the
thresholds alone, so a difference is attributable to that parameter.

    python -u artifacts/analysis/robustness_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "analysis" / "runs"

# (label, arm, field amplitude, position-attack ratio)
ARMS = [
    ("headline", "spatial_position_23dim", 0.45, 0.34),
    ("field 0.30", "spatial_position_field030", 0.30, 0.34),
    ("field 0.60", "spatial_position_field060", 0.60, 0.34),
    ("ratio 0.20", "spatial_position_ratio020", 0.45, 0.20),
    ("ratio 0.50", "spatial_position_ratio050", 0.45, 0.50),
]


def baseline_table(arm: str) -> dict:
    f = RUNS / arm / "tables" / "baseline_comparison.csv"
    if not f.exists():
        return {}
    d = pd.read_csv(f, encoding="utf-8-sig").set_index("method")
    out = {}
    for m in d.index:
        row = {}
        for col in ("accuracy", "f_score", "tsr"):
            s = str(d.loc[m, col]).replace("\u00b1", "+-").replace("卤", "+-")
            row[col] = float(s.split("+-")[0].strip())
        out[m] = row
    return out


def atk_table(arm: str) -> dict:
    f = RUNS / arm / "logs" / "per_seed_attack_type_metrics.csv"
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    d = d.drop_duplicates(subset=["seed", "method", "attack_type"])
    d = d[d["malicious_ratio"].round(6) == 0.30]
    out = {}
    for m in d["method"].unique():
        out[m] = {}
        for t in d["attack_type"].unique():
            sub = d[(d["method"] == m) & (d["attack_type"] == t)]
            if len(sub):
                out[m][t] = float(sub["detection_rate"].mean()) * 100
    return out


def main() -> int:
    print("=" * 116)
    print("ROBUSTNESS OF THE SPATIAL SEPARATION -- one parameter moved at a time")
    print("=" * 116)
    print(f"{'configuration':<15}{'field':>7}{'ratio':>7}"
          f"{'S-TIM acc':>11}{'S-TIM F1':>10}{'MLP acc':>9}{'MLP F1':>9}"
          f"{'rule acc':>10}{'S-TIM pos.':>12}{'MLP pos.':>10}")
    print("-" * 116)
    for label, arm, amp, ratio in ARMS:
        base = baseline_table(arm)
        atk = atk_table(arm)
        if not base or not atk:
            print(f"{label:<15}{amp:>7.2f}{ratio:>7.2f}   [no arm log]")
            continue
        rule = [base[m]["accuracy"] for m in
                ("MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy")
                if m in base]
        rule_hi = max(rule) if rule else float("nan")
        print(f"{label:<15}{amp:>7.2f}{ratio:>7.2f}"
              f"{base['S-TIM']['accuracy']:>11.1f}{base['S-TIM']['f_score']:>10.1f}"
              f"{base['MLP-Trust']['accuracy']:>9.1f}{base['MLP-Trust']['f_score']:>9.1f}"
              f"{rule_hi:>10.1f}"
              f"{atk['S-TIM'].get('position-inconsistent', float('nan')):>12.1f}"
              f"{atk['MLP-Trust'].get('position-inconsistent', float('nan')):>10.1f}")
    print("-" * 116)
    print("rule acc   the best of the five rule adapters, which is the "
          "strongest traditional comparator")
    print("pos.       detection rate on the position-inconsistent attackers")
    print()
    print("The per-node baselines never receive the neighbourhood block, in "
          "accordance with the")
    print("main protocol, so the S-TIM minus MLP-Trust columns are the "
          "representation separation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
