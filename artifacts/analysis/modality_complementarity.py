"""Modality-complementarity table for the real (trained) models.

The probe-level verdict said the three feature blocks cover disjoint attack
classes: the marginal block catches constant/dormant attackers, the shape block
closes on-off, and the spatial block is the only thing that sees a
telemetry-replaying attacker whose behaviour channels are indistinguishable
from benign traffic. This script asks the same question of the real trained
models, not of a logistic probe.

Inputs are the per-seed attack-type logs written by each arm:

    artifacts/analysis/runs/<arm>/logs/per_seed_attack_type_metrics.csv

Two things the raw file forces on us:

  * It carries duplicate rows for every (seed, method, attack_type) key, so
    every mean here is computed after collapsing those rows.
  * The official main-table slice is (n_uavs == default_n, n_agents ==
    default_agents, malicious_ratio == main_ratio). The attack-type log does
    not carry n_agents, but it does carry n_uavs and malicious_ratio, so the
    slice is applied on the (n_uavs, malicious_ratio) pair the arm produced.

Usage:
    python -u artifacts/analysis/modality_complementarity.py \
        --arm "label=path/to/per_seed_attack_type_metrics.csv" \
        --compare "label_a" "label_b" \
        --out artifacts/analysis/modality_complementarity.txt
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

ATTACK_ORDER = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]
ALL_METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy",
               "LR-Trust", "MLP-Trust", "S-TIM"]


def load_arm(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    df["seed"] = df["seed"].astype(int)
    df["detection_rate"] = df["detection_rate"].astype(float)
    # Collapse the duplicated rows the log carries: one mean per
    # (seed, method, attack_type). n_uavs / malicious_ratio are part of the
    # grouping key so the main-table slice can still be applied afterwards.
    return (df.groupby(["seed", "method", "attack_type", "n_uavs", "malicious_ratio"],
                       as_index=False)["detection_rate"].mean())


def main_slice(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the official main-table slice to the attack-type log."""
    if df.empty:
        return df
    pairs = df[["n_uavs", "malicious_ratio"]].drop_duplicates()
    if len(pairs) == 1:
        return df
    target_ratio = float(pairs["malicious_ratio"].mode().iloc[0])
    cands = pairs[pairs["malicious_ratio"].round(6) == round(target_ratio, 6)]
    target_n = cands["n_uavs"].max()
    return df[(df["n_uavs"] == target_n) &
              (df["malicious_ratio"].round(6) == round(target_ratio, 6))]


def paired_test(a: pd.Series, b: pd.Series):
    """Paired t-test on the common seeds; returns (diff, t, p, d, n)."""
    m = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    n = len(m)
    if n < 2:
        return None
    d = m["a"] - m["b"]
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


def pct(x: float) -> str:
    return f"{100.0 * x:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="label=path/to/per_seed_attack_type_metrics.csv")
    ap.add_argument("--compare", nargs=2, default=None,
                    help="two arm labels to compare per attack class")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    arms: dict[str, pd.DataFrame] = {}
    for spec in args.arm:
        label, _, path = spec.partition("=")
        p = Path(path)
        if not p.exists():
            print(f"!! missing arm log: {p}", file=sys.stderr)
            continue
        df = main_slice(load_arm(p))
        arms[label] = df
        seeds = df["seed"].nunique()
        types = sorted(df["attack_type"].unique().tolist())
        print(f"[load] {label}: {len(df)} rows, {seeds} seeds, types={types}")

    if not arms:
        print("no arms loaded", file=sys.stderr)
        return 2

    types = [t for t in ATTACK_ORDER
             if any(t in set(df["attack_type"]) for df in arms.values())]

    out: list[str] = []
    out.append("=" * 104)
    out.append("MODALITY COMPLEMENTARITY -- real trained models, per-attack-class detection rate (%)")
    out.append("=" * 104)

    for method in ALL_METHODS:
        if not any(method in set(df["method"]) for df in arms.values()):
            continue
        out.append("")
        out.append(f"--- {method} " + "-" * max(1, 90 - len(method)))
        out.append(f"{'arm':<32}" + "".join(f"{t:>18}" for t in types))
        out.append("-" * 104)
        for lab, df in arms.items():
            if method not in set(df["method"]):
                continue
            row = f"{lab:<32}"
            for t in types:
                sub = df[(df["method"] == method) & (df["attack_type"] == t)]
                row += f"{pct(sub['detection_rate'].mean()):>18}" if len(sub) else f"{'--':>18}"
            out.append(row)
        out.append("")

    if args.compare:
        a_label, b_label = args.compare
        if a_label in arms and b_label in arms:
            A, B = arms[a_label], arms[b_label]
            out.append("=" * 104)
            out.append(f"PAIRED COMPARISON: {a_label}   MINUS   {b_label}")
            out.append("same seeds, same configuration except the block under test")
            out.append("=" * 104)
            out.append(f"{'method':<13}{'attack class':>22}{'delta pp':>12}{'t':>10}"
                       f"{'p':>12}{'d':>10}{'n':>6}")
            out.append("-" * 104)
            cmp_types = [t for t in types
                         if t in set(A["attack_type"]) and t in set(B["attack_type"])]
            for method in ALL_METHODS:
                if method not in set(A["method"]) or method not in set(B["method"]):
                    continue
                for t in cmp_types:
                    sa = A[(A["method"] == method) &
                           (A["attack_type"] == t)].set_index("seed")["detection_rate"]
                    sb = B[(B["method"] == method) &
                           (B["attack_type"] == t)].set_index("seed")["detection_rate"]
                    res = paired_test(sa, sb)
                    if res is None:
                        continue
                    md, tt, pp, dd, n = res
                    out.append(f"{method:<13}{t:>22}{100*md:>12.1f}{tt:>10.2f}"
                               f"{pp:>12.4f}{dd:>10.2f}{n:>6d}")
            out.append("")

    text = "\n".join(out)
    print(text)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
