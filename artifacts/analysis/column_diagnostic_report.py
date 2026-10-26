"""Paired per-seed statistics for the column-level diagnostic arms.

The communication dimension reaches the model through three columns: its own
recent mean and the two directed cross-factor gaps. This prints the paired
difference of each arm against the published configuration re-run, for the
aggregate metrics and for the intermittent-attack detection rate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "analysis" / "runs"

ARMS = [
    ("published_recheck", "published configuration"),
    ("col_nogaps", "the two directed cross-factor gaps removed"),
    ("col_noT2direct", "the recent mean of T2 removed"),
    ("drop_T3", "the energy dimension removed"),
    ("drop_T2", "the whole communication dimension removed"),
]


def load(arm: str):
    m = pd.read_csv(RUNS / arm / "logs" / "per_seed_metrics.csv")
    m = m[(m["scenario"].isin(["ratio", "figure_ratio"]))
          & (m["n_uavs"] == 15) & (m["n_agents"] == 5)
          & (m["malicious_ratio"].round(6) == round(0.30, 6))]
    m = m[m["method"] == "S-TIM"].drop_duplicates(subset=["seed"])
    a = pd.read_csv(RUNS / arm / "logs" / "per_seed_attack_type_metrics.csv")
    a = a.drop_duplicates(subset=["seed", "method", "attack_type"])
    a = a[(a["method"] == "S-TIM") & (a["attack_type"] == "on-off")
          & (a["malicious_ratio"].round(6) == round(0.30, 6))]
    return (m.set_index("seed")[["accuracy", "f_score", "tsr"]] * 100,
            a.groupby("seed")["detection_rate"].mean() * 100)


def paired(d: pd.Series):
    d = d.dropna()
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    if sd == 0:
        return mean, 1.0, n
    t = mean / (sd / np.sqrt(n))
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return mean, float(p), n


def main() -> int:
    data = {arm: load(arm) for arm, _ in ARMS}
    ref = data["published_recheck"]
    print("=" * 92)
    print("COLUMN-LEVEL DIAGNOSTIC, PUBLISHED SCENARIO (arm minus the reference)")
    print("=" * 92)
    for arm, label in ARMS:
        m, on = data[arm]
        d_acc = (m["accuracy"] - ref[0]["accuracy"]).dropna()
        d_on = (on - ref[1]).dropna()
        ma, pa, n = paired(d_acc)
        mo, po, _ = paired(d_on)
        print(f"  {label:<42} accuracy {ma:+6.2f} pp (p={pa:.4f}, n={n})"
              f"   on-off {mo:+6.2f} pp (p={po:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
