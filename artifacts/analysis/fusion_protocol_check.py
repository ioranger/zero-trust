"""Per-class detection rates for the fusion control arm.

The fusion arm is the one in which the learned baselines receive exactly the
same 23-dimensional vector as the proposed model
(`fairness.learned_baselines_get_spatial_block = true`). It is therefore the
arm that answers the question the main protocol deliberately does not ask:
what happens to the spatial advantage once the control is not information-
starved.

Everything is read from the arm's own per-seed attack-type log.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ATTACK_ORDER = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]
METHODS = ["S-TIM", "MLP-Trust", "LR-Trust", "MFA", "FUBA", "GALTrust",
           "GDM-DTM", "AHP-Entropy"]
POPS = {"constant": 52, "dormant": 53, "on-off": 53,
        "position-inconsistent": 82, "benign": 560}

ARMS = {
    "spatial_position_23dim": r"F:\zero trust\zero-trust\artifacts\runs\spatial_position_23dim\logs\per_seed_attack_type_metrics.csv",
    "spatial_position_fusion": r"F:\zero trust\zero-trust\artifacts\runs\spatial_position_fusion\logs\per_seed_attack_type_metrics.csv",
}


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    df["seed"] = df["seed"].astype(int)
    df["detection_rate"] = df["detection_rate"].astype(float)
    return (df.groupby(["seed", "method", "attack_type", "n_uavs",
                        "malicious_ratio"], as_index=False)["detection_rate"].mean())


def rates(df: pd.DataFrame, method: str) -> dict:
    out = {}
    for c in ATTACK_ORDER:
        sub = df[(df["method"] == method) & (df["attack_type"] == c)]
        out[c] = float(sub["detection_rate"].mean()) * 100 if len(sub) else float("nan")
    return out


def paired(a: pd.DataFrame, b: pd.DataFrame, method: str, cls: str):
    sa = a[(a["method"] == method) & (a["attack_type"] == cls)].set_index("seed")["detection_rate"]
    sb = b[(b["method"] == method) & (b["attack_type"] == cls)].set_index("seed")["detection_rate"]
    m = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
    d = m["a"] - m["b"]
    n = len(d)
    sd = d.std(ddof=1)
    if n < 2 or sd == 0:
        return None
    t = d.mean() / (sd / (n ** 0.5))
    try:
        from scipy import stats
        p = float(2.0 * stats.t.sf(abs(t), df=n - 1))
    except Exception:
        p = float("nan")
    return d.mean() * 100, t, p, n


def main() -> int:
    loaded = {}
    for name, path in ARMS.items():
        if not Path(path).exists():
            print(f"!! missing {name}: {path}")
            continue
        loaded[name] = load(path)

    print("=" * 104)
    print("MAIN PROTOCOL vs SAME-INPUT FUSION PROTOCOL -- per-class detection rate (%)")
    print("=" * 104)
    for name, df in loaded.items():
        print(f"\n--- {name} ---")
        print(f"{'method':<14}" + "".join(f"{c:>16}" for c in ATTACK_ORDER)
              + f"{'macro-4':>11}{'pop-wtd':>10}")
        for m in METHODS:
            if m not in set(df["method"]):
                continue
            r = rates(df, m)
            macro4 = sum(r[c] for c in ATTACK_ORDER[:4]) / 4.0
            pw = sum(POPS[c] * r[c] for c in ATTACK_ORDER) / 800.0
            print(f"{m:<14}" + "".join(f"{r[c]:>16.1f}" for c in ATTACK_ORDER)
                  + f"{macro4:>11.1f}{pw:>10.1f}")

    if len(loaded) == 2:
        a = loaded["spatial_position_23dim"]
        b = loaded["spatial_position_fusion"]
        print()
        print("=" * 104)
        print("PAIRED: same-input fusion arm MINUS main-protocol arm, per method")
        print("=" * 104)
        print(f"{'method':<14}{'attack class':>22}{'delta pp':>12}{'t':>9}{'p':>10}{'n':>6}")
        for m in METHODS:
            if m not in set(a["method"]) or m not in set(b["method"]):
                continue
            for c in ATTACK_ORDER:
                res = paired(b, a, m, c)
                if res is None:
                    continue
                d, t, p, n = res
                pt = "<0.0001" if p < 1e-4 else f"{p:.4f}"
                print(f"{m:<14}{c:>22}{d:>12.1f}{t:>9.2f}{pt:>10}{n:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
