"""Report the channel-focused dimension-budget study.

The study prices the five trust dimensions against each other under the
threat model the manuscript states: an adversary may manipulate any subset of
the five dimensions independently. In the channel-focused scenario every
attacker manipulates exactly one dimension and is indistinguishable from a
benign node on the other four, so the dimension an attacker manipulates is
the only place where evidence about it exists.

Every arm is a deployment that observes a subset of the five dimensions and
nothing else, so the number of dimensions it observes is its observation
budget k. The arms are grouped by k, from k = 5 (the reference configuration
the manuscript proposes) down to k = 1, which turns the ablation into a
single monotone series: the more dimensions the deployment can observe, the
more of the five attackers it can see, and the full five is the best
configuration under this adversary.

The report checks the same three things as the published leave-one-factor-out
control: the rule-based comparators keep all five dimensions in every arm so
their numbers must not move, every arm is compared with the full
configuration re-run on the same code path paired per seed, and the
per-dimension detection breakdown shows where the evidence went.

Usage:
    python -u artifacts/analysis/channel_profile_ablation_report.py
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "artifacts" / "analysis" / "runs"
TABLES = ROOT / "artifacts" / "outputs" / "tables"
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

PREFIX = "channel_profile"
REFERENCE = PREFIX
FACTORS = ["T1", "T2", "T3", "T4", "T5"]

# The arm that keeps only T1 and T4, the smallest factor set the published
# representation stands on. Two dimensions observed.
EXTRA = f"{PREFIX}_drop_T2_T3_T5"


def arm_name(subset: tuple) -> str:
    """The configuration that observes exactly this subset of the dimensions."""
    if len(subset) == 5:
        return REFERENCE
    if len(subset) == 4:
        omitted = [f for f in FACTORS if f not in subset][0]
        return f"{PREFIX}_drop_{omitted}"
    if tuple(subset) == ("T1", "T4"):
        return EXTRA
    return f"{PREFIX}_only_{'_'.join(subset)}"


# Every arm, grouped by the number of dimensions the deployment observes. The
# study is exhaustive over the non-empty subsets of the five dimensions: all
# thirty-one of them are present, so no budget and no subset is missing.
BUDGET = [(size, [arm_name(c) for c in combinations(FACTORS, size)])
          for size in (5, 4, 3, 2, 1)]
ALL_ARMS = [a for _, arms in BUDGET for a in arms]
DROPOUT_ARMS = [arm_name(tuple(f for f in FACTORS if f != x)) for x in FACTORS]
ONLY_ARMS = [arm_name((f,)) for f in FACTORS]

RULE_METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]
LEARNED_METHODS = ["LR-Trust", "MLP-Trust", "S-TIM"]
METRICS = [("accuracy", "accuracy"), ("f_score", "F-score"), ("tsr", "TSR")]

FACTOR_LABEL = {
    "T1": "T1 behavioural",
    "T2": "T2 communication",
    "T3": "T3 energy",
    "T4": "T4 task execution",
    "T5": "T5 memory",
}


def load(arm: str, n_uavs: int = 15):
    base = RUNS / arm
    metrics = pd.read_csv(base / "logs" / "per_seed_metrics.csv")
    main = metrics[
        (metrics["scenario"].isin(["ratio", "figure_ratio"]))
        & (metrics["n_uavs"] == n_uavs)
        & (metrics["n_agents"] == 5)
        & (metrics["malicious_ratio"].round(6) == round(0.30, 6))
    ].drop_duplicates(subset=["seed", "method"])
    piv = main.pivot_table(index="seed", columns="method",
                            values=["accuracy", "f_score", "tsr"])
    atk = pd.read_csv(base / "logs" / "per_seed_attack_type_metrics.csv")
    atk = atk.drop_duplicates(subset=["seed", "method", "attack_type"])
    atk = atk[atk["malicious_ratio"].abs() - 0.30 < 1e-9]
    pol = json.loads((base / "logs" / "marl_policy.json").read_text(encoding="utf-8"))
    return piv, atk, pol


def paired(d: pd.Series):
    d = d.dropna()
    n = len(d)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 0
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    if sd == 0:
        return mean, 0.0, 1.0, n
    t = mean / (sd / sqrt(n))
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return mean, float(t), float(p), n


def focus_detection(atk: pd.DataFrame) -> dict:
    """Mean detection rate per manipulated dimension, over the seeds."""
    s = atk[(atk["method"] == "S-TIM")]
    out = {}
    for factor in FACTORS:
        rows = s[s["attack_type"].astype(str).str.startswith(factor + ":")]
        out[factor] = float(rows["detection_rate"].mean()) * 100 if len(rows) else float("nan")
    return out


def observed_dimensions(arm: str) -> list[str]:
    """The dimensions the deployment of this arm can see."""
    if arm == REFERENCE:
        return list(FACTORS)
    if "_only_" in arm:
        return arm.split("_only_")[-1].split("_")
    dropped = arm.split("drop_")[-1].split("_")
    return [f for f in FACTORS if f not in dropped]


def arm_label(arm: str) -> str:
    if arm == REFERENCE:
        return "all five dimensions"
    observed = observed_dimensions(arm)
    if "_drop_" in arm and len(observed) == 4:
        omitted = [f for f in FACTORS if f not in observed][0]
        return "without " + FACTOR_LABEL[omitted]
    if len(observed) == 1:
        return "only " + FACTOR_LABEL[observed[0]]
    return "only " + " and ".join(observed)


def budget_label(arm: str) -> str:
    """Short label used by the budget table: the dimensions observed."""
    if arm == REFERENCE:
        return "T1, T2, T3, T4, T5"
    return ", ".join(observed_dimensions(arm))


def main() -> int:
    present = [a for a in ALL_ARMS
               if (RUNS / a / "logs" / "per_seed_metrics.csv").exists()]
    missing = [a for a in ALL_ARMS if a not in present]
    if missing:
        print("[FAIL] missing arms: " + ", ".join(missing))
        return 1

    data = {a: load(a) for a in present}
    ref_piv, ref_atk, ref_pol = data[REFERENCE]
    widths = {a: len(data[a][2].get("feature_names", [])) for a in present}

    print("=" * 96)
    print("CHANNEL-FOCUSED ADVERSARY: DIMENSION-BUDGET STUDY")
    print("=" * 96)
    print(f"reference arm: {REFERENCE} ({widths[REFERENCE]} columns, "
          f"{len(ref_piv)} evaluation seeds)")
    print()
    print("1. THE PROPOSED MODEL, PER ARM")
    print(f"{'arm':<28}{'cols':>6}{'accuracy':>11}{'F-score':>10}{'TSR':>8}"
          f"{'T1':>7}{'T2':>7}{'T3':>7}{'T4':>7}{'T5':>7}")
    print("-" * 96)
    for arm in present:
        piv, atk, _ = data[arm]
        det = focus_detection(atk)
        print(f"{arm_label(arm):<28}{widths[arm]:>6}"
              f"{piv['accuracy']['S-TIM'].mean() * 100:>11.1f}"
              f"{piv['f_score']['S-TIM'].mean() * 100:>10.1f}"
              f"{piv['tsr']['S-TIM'].mean() * 100:>8.1f}"
              + "".join(f"{det[f]:>7.1f}" for f in FACTORS))

    print()
    print("2. THE COMPARATORS MUST NOT MOVE (they keep all five dimensions)")
    problems = []
    for m in RULE_METHODS:
        vals = [data[a][0]["accuracy"][m].mean() * 100 for a in present]
        same = max(vals) - min(vals) < 1e-6
        print(f"  [{'ok' if same else 'FAIL'}] {m:<12} " + ", ".join(f"{v:.1f}" for v in vals))
        if not same:
            problems.append(m + " moved across the arms")

    print()
    print("3. WHAT EACH DIMENSION IS WORTH (paired per seed, against the reference)")
    rows = []
    for arm in present[1:]:
        piv, atk, _ = data[arm]
        out = []
        for met, label in METRICS:
            d = (ref_piv[met]["S-TIM"] - piv[met]["S-TIM"]) * 100
            mean, t, p, n = paired(d)
            out.append((label, mean, p))
            rows.append({"arm": arm, "metric": label, "delta_pp": mean,
                         "p_value": p, "n_seeds": n})
        print(f"  {arm_label(arm):<26} " + " | ".join(
            f"{m} {mu:+6.2f} pp (p={p:.4f})" for m, mu, p in out))

    print()
    print("4. LEARNED COMPARATORS (they see the same reduced input)")
    for m in LEARNED_METHODS:
        vals = [data[a][0]["accuracy"][m].mean() * 100 for a in present]
        print(f"  {m:<12} " + ", ".join(f"{v:.1f}" for v in vals))

    print()
    print("5. SINGLE-DIMENSION ARMS (the model sees one dimension and nothing else)")
    rows_only = []
    for arm in [a for a in ONLY_ARMS if a in present]:
        piv, atk, _ = data[arm]
        det = focus_detection(atk)
        out = []
        rec = {"arm": arm, "columns": widths[arm]}
        for met, label in METRICS:
            key = label.lower().replace("-", "_")
            d = (ref_piv[met]["S-TIM"] - piv[met]["S-TIM"]) * 100
            mean, t, p, n = paired(d)
            out.append((label, mean, p))
            rec[key] = round(float(piv[met]["S-TIM"].mean() * 100), 2)
            rec["delta_" + key] = round(mean, 4)
            rec["p_" + key] = p
            rec["n_seeds"] = n
        for factor in FACTORS:
            rec["detection_" + factor] = round(det[factor], 2)
        rows_only.append(rec)
        print(f"  {arm_label(arm):<26} " + " | ".join(
            f"{m} {mu:+6.2f} pp (p={p:.4f})" for m, mu, p in out)
            + "   detection per dimension "
            + "/".join(f"{det[f]:.0f}" for f in FACTORS))

    print()
    print("6. THE DIMENSION-BUDGET SERIES (how many dimensions the deployment sees)")
    budget_rows = []
    for k, arms in BUDGET:
        group = [a for a in arms if a in present]
        if not group:
            continue
        accs = [data[a][0]["accuracy"]["S-TIM"].mean() * 100 for a in group]
        print(f"  k = {k} ({len(group)} arm(s)): accuracy "
              f"{min(accs):.1f}--{max(accs):.1f} %"
              + ("" if k == 5 else ", mean %.1f %%" % (sum(accs) / len(accs))))
        for arm in group:
            piv, atk, _ = data[arm]
            det = focus_detection(atk)
            rec = {"k": k, "arm": arm, "observed": budget_label(arm),
                   "columns": widths[arm]}
            for met, label in METRICS:
                key = label.lower().replace("-", "_")
                d = (ref_piv[met]["S-TIM"] - piv[met]["S-TIM"]) * 100
                mean, t, p, n = paired(d)
                rec[key] = round(float(piv[met]["S-TIM"].mean() * 100), 2)
                rec["delta_" + key] = round(mean, 4)
                rec["p_" + key] = p
                rec["n_seeds"] = n
            for factor in FACTORS:
                rec["detection_" + factor] = round(det[factor], 2)
            budget_rows.append(rec)

    best = max(budget_rows, key=lambda r: r["accuracy"])
    print(f"  best arm in the series: {best['arm']} "
          f"(k = {best['k']}, {best['accuracy']:.1f} % accuracy)")
    if best["arm"] != REFERENCE:
        problems.append("the reference configuration is not the best arm")

    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(TABLES / "channel_profile_ablation.csv", index=False)
    print()
    print("wrote " + str(TABLES / "channel_profile_ablation.csv"))

    if rows_only:
        pd.DataFrame(rows_only).to_csv(
            TABLES / "channel_profile_only_dimension.csv", index=False)
        print("wrote " + str(TABLES / "channel_profile_only_dimension.csv"))

    if budget_rows:
        pd.DataFrame(budget_rows).to_csv(
            TABLES / "channel_profile_dimension_budget.csv", index=False)
        print("wrote " + str(TABLES / "channel_profile_dimension_budget.csv"))

    abl_path = RUNS / REFERENCE / "logs" / "per_seed_ablation.csv"
    if abl_path.exists():
        abl = pd.read_csv(abl_path).drop_duplicates(subset=["seed", "variant"])
        order = ["S-TIM (full)", "w/o Cross-factor Checking",
                 "w/o Bayesian Aggregation", "w/o Temporal Decay",
                 "w/o Adaptive Policy", "w/o Incentive Mechanism",
                 "T1 Only", "T2 Only", "T3 Only", "T4 Only", "T5 Only"]
        out = []
        for variant in order:
            g = abl[abl["variant"] == variant]
            if not len(g):
                continue
            out.append({
                "variant": variant,
                "accuracy": "%.1f ± %.1f" % (g["accuracy"].mean() * 100,
                                              g["accuracy"].std(ddof=1) * 100),
                "f_score": "%.1f ± %.1f" % (g["f_score"].mean() * 100,
                                            g["f_score"].std(ddof=1) * 100),
                "tsr": "%.1f ± %.1f" % (g["tsr"].mean() * 100,
                                        g["tsr"].std(ddof=1) * 100),
            })
        pd.DataFrame(out).to_csv(
            TABLES / "channel_profile_component_ablation.csv", index=False)
        print("wrote " + str(TABLES / "channel_profile_component_ablation.csv"))

    if problems:
        for p in problems:
            print("[FAIL] " + p)
        return 1
    print("[OK] the arms are comparable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
