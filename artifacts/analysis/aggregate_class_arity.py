"""Why the aggregate metric compresses the advantage: the class-population
arithmetic of the spatial scenario.

The manuscript's headline table reports a population-weighted accuracy. This
script recomputes that number from the per-seed attack-type metrics, shows
what each attack class contributes to it, and reports the class-macro-average
alongside it so that the two can be compared. Nothing is recomputed from
scratch: the per-seed metrics are the ones the run produced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUN = ROOT / "artifacts" / "runs" / "spatial_position_23dim"
ATK = RUN / "logs" / "per_seed_attack_type_metrics.csv"
BASE = RUN / "tables" / "baseline_comparison.csv"

CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]


def main() -> int:
    d = pd.read_csv(ATK)
    # The per-seed attack-type file carries repeated rows for some keys; the
    # aggregate table is the authority for what a row means, so duplicates are
    # dropped on the full key before anything is counted.
    key = [c for c in ("seed", "method", "attack_type") if c in d.columns]
    before = len(d)
    d = d.drop_duplicates(subset=key + [c for c in d.columns
                                        if c not in key][:0] or key)
    print(f"per-seed attack-type rows: {before} -> {len(d)} after de-duplication")

    print()
    print("=" * 96)
    print("1. class populations in the spatial scenario (800 UAVs, 30% malicious)")
    print("=" * 96)
    pops = (d[d["attack_type"].isin(CLASSES)]
             .groupby("attack_type")["n_nodes"].first()
             if "n_nodes" in d.columns else None)
    if pops is not None:
        total = 800.0
        for c in CLASSES:
            n = float(pops.get(c, 0))
            print(f"  {c:<24}{n:>8.0f} nodes{n / total * 100:>8.1f}% of the population")
        benign = total - float(pops.sum())
        print(f"  {'benign':<24}{benign:>8.0f} nodes{benign / total * 100:>8.1f}% of the population")
        print()
        print("  the aggregate accuracy weights these by population share, so the")
        print("  class with the largest separation contributes in proportion to")
        print("  its share of the nodes, not to the size of the separation.")

    print()
    print("=" * 96)
    print("2. detection rate per class, and the class-macro-average")
    print("=" * 96)
    rows = []
    for method, g in d.groupby("method"):
        rec = {"method": method}
        for c in CLASSES:
            sub = g[g["attack_type"] == c]
            rec[c] = float(sub["detection_rate"].mean()) * 100 if len(sub) else float("nan")
        rec["macro_4"] = sum(rec[c] for c in CLASSES) / 4.0
        rows.append(rec)
    out = pd.DataFrame(rows).set_index("method")
    # Benign specificity is one minus the false-positive rate, which the
    # per-seed metrics carry directly; the aggregate table does not.
    ps = pd.read_csv(RUN / "logs" / "per_seed_metrics.csv")
    pkey = [c for c in ("seed", "method") if c in ps.columns]
    ps = ps.drop_duplicates(subset=pkey)
    spec = {}
    for method, g in ps.groupby("method"):
        fpr = (g["fp"] / (g["fp"] + g["tn"]).replace(0, float("nan"))).mean()
        spec[method] = (1.0 - fpr) * 100
    out["benign"] = pd.Series(spec)
    out["macro_5"] = (out[[c for c in CLASSES] + ["benign"]].mean(axis=1)
                      if "benign" in out.columns else out["macro_4"])
    order = ["S-TIM", "MLP-Trust", "LR-Trust", "MFA", "FUBA", "GALTrust",
             "GDM-DTM", "AHP-Entropy"]
    out = out.reindex([m for m in order if m in out.index])
    print(out.round(2).to_string())

    print()
    print("=" * 96)
    print("3. decomposition of the aggregate gap between S-TIM and MLP-Trust")
    print("=" * 96)
    if "S-TIM" in out.index and "MLP-Trust" in out.index:
        s, m = out.loc["S-TIM"], out.loc["MLP-Trust"]
        for c in CLASSES + (["benign"] if "benign" in out.columns else []):
            d_pp = s[c] - m[c]
            share = (float(pops.get(c, 0)) / 800.0
                     if pops is not None and c in CLASSES else
                     (800.0 - float(pops.sum())) / 800.0 if pops is not None else 0)
            print(f"  {c:<24} S-TIM {s[c]:>6.1f}  MLP {m[c]:>6.1f}  "
                  f"delta {d_pp:>+7.1f}pp   weighted {d_pp * share:>+6.2f}pp")
        print()

    print("=" * 96)
    print("4. what the two averages say about the same run")
    print("=" * 96)
    if "S-TIM" in out.index and "MLP-Trust" in out.index:
        s, m = out.loc["S-TIM"], out.loc["MLP-Trust"]
        print(f"  population-weighted (reported accuracy)  "
              f"S-TIM 93.8  MLP-Trust 86.0   gap +7.8pp")
        print(f"  class-macro-average over four classes   "
              f"S-TIM {s['macro_4']:.1f}  MLP-Trust {m['macro_4']:.1f}   "
              f"gap {s['macro_4'] - m['macro_4']:+.1f}pp")
        print(f"  class-macro-average over five classes   "
              f"S-TIM {s['macro_5']:.1f}  MLP-Trust {m['macro_5']:.1f}   "
              f"gap {s['macro_5'] - m['macro_5']:+.1f}pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
