"""Recompute the spatial margins the manuscript quotes, from the arm logs.

The manuscript states the margin of the proposed model over the rule-based
comparators in the spatially inconsistent scenario. Which rule adapter is the
strongest differs by metric: GALTrust leads on accuracy, GDM-DTM on F-score
and TSR in the headline arm, and the identity of the best adapter changes
across the robustness sweep. This script therefore reports, for every arm and
every metric, the strongest rule adapter, the difference of the published
means and the paired per-seed difference, so the numbers in the prose can be
checked against the data and attributed to a named method.

The margins over the strongest rule adapter across the sweep are the ranges
the robustness paragraph quotes.

Usage:
    python -u artifacts/analysis/spatial_rule_margins.py
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

RUNS = Path(r"F:\zero trust\zero-trust\artifacts\runs")
ARMS = [
    ("headline", "spatial_position_23dim"),
    ("field amplitude 0.30", "spatial_position_field030"),
    ("field amplitude 0.60", "spatial_position_field060"),
    ("position ratio 0.20", "spatial_position_ratio020"),
    ("position ratio 0.50", "spatial_position_ratio050"),
]
RULES = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]
METRICS = ("accuracy", "f_score", "tsr")


def published(arm: str, method: str) -> dict:
    t = pd.read_csv(RUNS / arm / "tables" / "baseline_comparison.csv",
                    encoding="utf-8-sig").set_index("method")
    r = t.loc[method]
    out = {}
    for c in METRICS:
        s = str(r[c]).replace("\u00b1", "+-")
        out[c] = float(s.split("+-")[0].strip())
    return out


def per_seed(arm: str) -> pd.DataFrame:
    d = pd.read_csv(RUNS / arm / "logs" / "per_seed_metrics.csv")
    pairs = d[["n_uavs", "malicious_ratio"]].drop_duplicates()
    if len(pairs) > 1:
        ratio = float(pairs["malicious_ratio"].mode().iloc[0])
        cands = pairs[pairs["malicious_ratio"].round(6) == round(ratio, 6)]
        n = cands["n_uavs"].max()
        d = d[(d["n_uavs"] == n) &
              (d["malicious_ratio"].round(6) == round(ratio, 6))]
    d = d[d["scenario"] == d["scenario"].mode().iloc[0]]
    return d.drop_duplicates(subset=["seed", "method"])


def paired(a: pd.Series, b: pd.Series):
    m = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    d = m["a"] - m["b"]
    sd = d.std(ddof=1)
    if sd == 0:
        return d.mean(), 1.0
    t = d.mean() / (sd / math.sqrt(len(m)))
    try:
        from scipy import stats
        p = float(2.0 * stats.t.sf(abs(t), df=len(m) - 1))
    except Exception:
        p = math.erfc(abs(t) / math.sqrt(2.0))
    return d.mean(), p


def main() -> int:
    margins = {m: [] for m in METRICS}
    for label, arm in ARMS:
        stim = published(arm, "S-TIM")
        ps = per_seed(arm)
        print(f"--- {label} ---")
        for metric in METRICS:
            best = max(RULES, key=lambda r: published(arm, r)[metric])
            best_val = published(arm, best)[metric]
            margin = stim[metric] - best_val
            margins[metric].append(margin)
            sa = ps[ps["method"] == "S-TIM"].set_index("seed")[metric] * 100
            sb = ps[ps["method"] == best].set_index("seed")[metric] * 100
            diff, p = paired(sa, sb)
            print(f"  {metric:<9} strongest rule adapter {best:<12}"
                  f"({best_val:5.1f})   proposed model {stim[metric]:5.1f}"
                  f"   margin {margin:+6.1f} pp   paired {diff:+6.1f} pp"
                  f"  (p={p:.6f})")
        print()
    print("margin over the strongest rule adapter across the sweep:")
    for metric in METRICS:
        m = margins[metric]
        print(f"  {metric:<9} +{min(m):.1f} to +{max(m):.1f} pp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
