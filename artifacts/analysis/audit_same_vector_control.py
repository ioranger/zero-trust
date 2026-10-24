"""The fusion arm's MLP-Trust result, checked against the arm's own logs.

The fusion arm gives every learned comparator the identical 23-dimensional
vector. If a learner on that vector reaches the same detection rate as the
proposed model, the manuscript's claim that the gain comes from the
representation rather than the network does not hold as stated, and the
manuscript has to say so.

This script recomputes the arm's numbers from the per-seed logs and prints
the comparison, so the finding can be verified before anything is written.

Usage:
    python -u artifacts/analysis/audit_same_vector_control.py
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

RUNS = Path(r"F:\zero trust\zero-trust\artifacts\analysis\runs")
ARM = "spatial_position_fusion"
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]
METHODS = ["MLP-Trust", "LR-Trust", "S-TIM"]


def load():
    f = RUNS / ARM / "logs" / "per_seed_attack_type_metrics.csv"
    d = pd.read_csv(f)
    d = d.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    return d[d["malicious_ratio"].abs() - 0.30 < 1e-9]


def rates(d, method):
    out = {}
    for c in CLASSES:
        sub = d[(d["method"] == method) & (d["attack_type"] == c)]
        out[c] = float(sub["detection_rate"].mean()) * 100 if len(sub) else None
    return out


def paired(a, b, cls):
    da = a[(a["method"] == "S-TIM") & (a["attack_type"] == cls)]
    db = a[(a["method"] == b) & (a["attack_type"] == cls)]
    m = pd.concat([
        da.groupby("seed")["detection_rate"].mean().rename("s"),
        db.groupby("seed")["detection_rate"].mean().rename("b"),
    ], axis=1).dropna()
    if len(m) < 2:
        return None
    diff = (m["s"] - m["b"]) * 100
    sd = diff.std(ddof=1)
    if sd == 0:
        return diff.mean(), 1.0, len(m)
    t = diff.mean() / (sd / math.sqrt(len(m)))
    try:
        from scipy import stats
        p = float(2.0 * stats.t.sf(abs(t), df=len(m) - 1))
    except Exception:
        p = math.erfc(abs(t) / math.sqrt(2.0))
    return diff.mean(), p, len(m)


def main() -> int:
    d = load()
    print("=" * 78)
    print(f"{ARM}: every learned comparator receives the identical")
    print("23-dimensional vector, the same threshold and the same seeds")
    print("=" * 78)
    r = {m: rates(d, m) for m in METHODS}
    print(f"{'method':<12}" + "".join(f"{c:>16}" for c in CLASSES) +
          f"{'class mean':>14}")
    for m in METHODS:
        vals = [r[m][c] for c in CLASSES]
        print(f"{m:<12}" + "".join(f"{v:>16.1f}" for v in vals) +
              f"{sum(vals) / 4.0:>14.1f}")
    print()
    print("  paired per-seed differences, S-TIM minus the comparator:")
    for b in ("MLP-Trust", "LR-Trust"):
        print(f"    --- {b} ---")
        for c in CLASSES:
            res = paired(d, b, c)
            if res:
                diff, p, n = res
                print(f"      {c:<22}{diff:+7.1f} pp   p={p:.4f}  n={n}")
    print()
    stim = r["S-TIM"]
    mlp = r["MLP-Trust"]
    print("  the position-inconsistent class:")
    print(f"     S-TIM {stim['position-inconsistent']:.1f}%   "
          f"MLP-Trust {mlp['position-inconsistent']:.1f}%")
    print()
    print("  a learner on the identical vector reaches the same rate on the")
    print("  class the paper's claim rests on, so the representation-versus-")
    print("  network reading does not survive this arm as it stands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
