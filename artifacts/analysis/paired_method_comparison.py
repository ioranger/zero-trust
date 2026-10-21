"""Paired comparison of the proposed model against its feature-matched control
inside each feature width.

The per-arm comparison in modality_complementarity.py varies the feature
blocks. This one varies the learner while the features are held fixed, which
is the only comparison that can say whether the proposed model is better than
the control that consumes the identical vector.

For every arm it pairs the per-seed metrics of S-TIM against each learned
baseline and reports the paired difference, the t statistic, the p value and
the effect size, per attack class and on the aggregate.

    python -u artifacts/analysis/paired_method_comparison.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "analysis" / "runs"

ARMS = [
    ("13d marginal only", "marginal_13dim"),
    ("18d marginal+shape (published)", "paper_18dim_check"),
    ("23d marginal+shape+spatial", "spatial_position_23dim"),
    ("23d, baselines get the block", "spatial_position_fusion"),
]

BASELINES = ["LR-Trust", "MLP-Trust"]


def paired(a: pd.Series, b: pd.Series):
    m = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    n = len(m)
    if n < 2:
        return None
    d = (m["a"] - m["b"])
    md = d.mean()
    sd = d.std(ddof=1)
    if sd == 0:
        return (md, math.inf if md else 0.0, 0.0 if md else 1.0, 0.0, n)
    t = md / (sd / math.sqrt(n))
    try:
        from scipy import stats  # type: ignore
        p = float(2.0 * stats.t.sf(abs(t), df=n - 1))
    except Exception:
        p = math.erfc(abs(t) / math.sqrt(2.0))
    return (md, t, p, md / sd, n)


def load_metrics(arm: str):
    f = RUNS / arm / "logs" / "per_seed_metrics.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    # Official main-table slice: the scenario rows at the arm's own default
    # node count, the default agent count and the main malicious ratio. The
    # node count is read from the log rather than assumed, because the spatial
    # arms run 800 nodes and the published arms run 15.
    default_n = int(d["n_uavs"].mode().iloc[0])
    d = d[(d["scenario"].isin(["ratio", "figure_ratio"]))
          & (d["n_uavs"] == default_n) & (d["n_agents"] == 5)
          & (d["malicious_ratio"].round(6) == 0.30)]
    return d.drop_duplicates(subset=["seed", "method"])


def load_atk(arm: str):
    f = RUNS / arm / "logs" / "per_seed_attack_type_metrics.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    d = d.drop_duplicates(subset=["seed", "method", "attack_type"])
    return d[d["malicious_ratio"].abs() - 0.30 < 1e-9]


def main() -> int:
    for label, arm in ARMS:
        met = load_metrics(arm)
        atk = load_atk(arm)
        if met is None or atk is None:
            print(f"\n--- {label}: no logs, skipped")
            continue
        print("\n" + "=" * 100)
        print(f"S-TIM minus each learned baseline, inside the arm {label!r} "
              f"(paired seeds)")
        print("=" * 100)
        print(f"{'baseline':<12}{'metric':<12}{'delta pp':>10}{'t':>9}"
              f"{'p':>11}{'d':>8}{'n':>5}")
        print("-" * 100)
        for base in BASELINES:
            if base not in set(met["method"]) or "S-TIM" not in set(met["method"]):
                continue
            for metric in ("accuracy", "f_score", "tsr"):
                a = met[met["method"] == "S-TIM"].set_index("seed")[metric] * 100
                b = met[met["method"] == base].set_index("seed")[metric] * 100
                res = paired(a, b)
                if res is None:
                    continue
                md, t, p, dd, n = res
                star = " *" if p < 0.05 else ""
                print(f"{base:<12}{metric:<12}{md:>10.2f}{t:>9.2f}"
                      f"{p:>11.4f}{dd:>8.2f}{n:>5d}{star}")
        print("-" * 100)
        print(f"{'baseline':<12}{'attack class':<22}{'delta pp':>10}{'t':>9}"
              f"{'p':>11}{'d':>8}{'n':>5}")
        print("-" * 100)
        for base in BASELINES:
            if base not in set(atk["method"]):
                continue
            for t_name in ("constant", "dormant", "on-off", "position-inconsistent"):
                sa = atk[(atk["method"] == "S-TIM") &
                         (atk["attack_type"] == t_name)].set_index("seed")["detection_rate"]
                sb = atk[(atk["method"] == base) &
                         (atk["attack_type"] == t_name)].set_index("seed")["detection_rate"]
                if not len(sa) or not len(sb):
                    continue
                res = paired(sa * 100, sb * 100)
                if res is None:
                    continue
                md, t, p, dd, n = res
                star = " *" if p < 0.05 else ""
                print(f"{base:<12}{t_name:<22}{md:>10.2f}{t:>9.2f}"
                      f"{p:>11.4f}{dd:>8.2f}{n:>5d}{star}")
    print("\n* marks p < 0.05 on the paired per-seed test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
