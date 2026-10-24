"""Why does the ratio sweep separate S-TIM from LR-Trust so little?

The sweep in Figure 4(a) runs in the published scenario, where the training
split is perfectly separable. This script prints the per-method accuracy at
every malicious ratio from the run's own per-seed metrics, and contrasts it
with the spatially inconsistent scenario, where the same methods are scored
on the same seeds.

    python -u artifacts/analysis/ratio_sweep_gap.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUN = ROOT / "artifacts" / "runs" / "paper_18dim_recheck"
SPATIAL = ROOT / "artifacts" / "runs" / "spatial_position_23dim"
METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy",
           "LR-Trust", "S-TIM"]


def main() -> int:
    m = pd.read_csv(RUN / "logs" / "per_seed_metrics.csv")
    print("=" * 96)
    print("published scenario, the ratio sweep of Figure 4(a)")
    print("=" * 96)
    ratio = m[(m["scenario"] == "figure_ratio")]
    piv = (ratio.groupby(["malicious_ratio", "method"])["accuracy"].mean() * 100)
    tbl = piv.unstack()
    cols = [c for c in METHODS if c in tbl.columns]
    print(tbl[cols].round(1).to_string())
    print()
    if "S-TIM" in cols and "LR-Trust" in cols:
        gap = tbl["S-TIM"] - tbl["LR-Trust"]
        print("  S-TIM minus LR-Trust:")
        for r, g in gap.items():
            print(f"    ratio {r:.2f}: {g:+.1f} pp")
        print(f"    mean gap {gap.mean():+.1f} pp, range {gap.min():+.1f} to {gap.max():+.1f}")
        best_rule = tbl[[c for c in cols if c not in ("S-TIM", "LR-Trust")]].max(axis=1)
        print()
        print("  S-TIM minus the best rule adapter (the gap the figure is about):")
        for r in tbl.index:
            print(f"    ratio {r:.2f}: {tbl.loc[r, 'S-TIM'] - best_rule[r]:+.1f} pp")

    print()
    print("=" * 96)
    print("spatially inconsistent scenario, same methods, same seeds")
    print("=" * 96)
    s = pd.read_csv(SPATIAL / "logs" / "per_seed_attack_type_metrics.csv")
    s = s.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    s = (s.groupby(["seed", "method", "attack_type"])["detection_rate"]
         .mean().reset_index())
    main_slice = s[(s["attack_type"] != "benign")]
    per_class = (main_slice.groupby(["method", "attack_type"])["detection_rate"]
                 .mean() * 100)
    print(per_class.unstack().round(1).to_string())

    print()
    print("  the four attack classes, class mean per method:")
    means = main_slice.groupby("method")["detection_rate"].mean() * 100
    for name in [c for c in METHODS if c in means.index]:
        print(f"    {name:<14}{means[name]:.1f}")

    print()
    print("=" * 96)
    print("per-seed spread of the published scenario (why the two learned")
    print("methods cannot be separated there)")
    print("=" * 96)
    main_rows = m[(m["scenario"] == "main") & (m["n_uavs"] == 15)]
    for name in ("S-TIM", "LR-Trust"):
        sub = main_rows[main_rows["method"] == name]["accuracy"] * 100
        if len(sub):
            print(f"  {name:<10} mean {sub.mean():.1f}  std {sub.std(ddof=1):.1f}"
                  f"  min {sub.min():.1f}  max {sub.max():.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
