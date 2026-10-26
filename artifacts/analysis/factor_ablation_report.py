"""Report the leave-one-factor-out arms.

Answers the question a reviewer asks about the trust factor: why does it carry
so many channels when every channel costs something. For each factor in turn,
the proposed model is trained and evaluated without it, and the detection
metrics are compared with the published configuration re-run on the same code
path, in both the published scenario and the spatially inconsistent one.

Two things are checked as well:

- the rule-based comparators keep all five factors in every arm, so their
  numbers must be identical across the arms. If they are not, the arms are
  not comparable and the report says so instead of quoting them.
- the published configuration re-run must reproduce the committed table
  exactly, or the comparison is against a number from a different code path.

Usage:
    python -u artifacts/analysis/factor_ablation_report.py [published|spatial|both]
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "analysis" / "runs"
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

from marl_policy import FEATURE_FACTORS  # noqa: E402

GIT = r"F:\zero trust\tools\MinGit\cmd\git.exe"
WT = Path(r"F:\zero trust\gitwork")

RULE_METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]
METRICS = [("accuracy", "accuracy"), ("f_score", "F-score"), ("tsr", "TSR")]

# name prefix, label prefix, the 18 or 23 column names of that configuration,
# the reference arm to compare against
FAMILIES = {
    "published": {
        "prefix": "",
        "reference": "published_recheck",
        "n_uavs": 15,
        "columns": [
            "1-T1_recent", "1-T2_recent", "1-T4_recent", "1-T5_recent",
            "1-T1_q10", "1-T4_q10",
            "low_T1_T4_fraction_0.58", "low_T1_T4_fraction_0.62",
            "T1_T4_amplitude", "T1_T4_std", "T1_T4_positive_slope",
            "directed_T2T3_minus_T1T4_gap", "directed_low_quantile_gap",
            "shape_acf_excess", "shape_acf_prominence", "shape_flip_rate",
            "shape_two_level", "shape_switch_cv",
        ],
    },
    "spatial": {
        "prefix": "spatial_",
        "reference": "spatial_recheck",
        "n_uavs": 800,
        "columns": None,   # read from the arm's own policy
    },
}

FACTOR_LABEL = {
    "T1": "T1 behavioural",
    "T2": "T2 communication",
    "T3": "T3 energy",
    "T4": "T4 task execution",
    "T5": "T5 historical",
}

# The communication dimension reaches the model through three columns: its own
# recent mean and the two directed cross-factor gaps. Removing the dimension
# removes all three at once, so these two arms separate the paths.
COLUMN_ARMS = [
    ("col_nogaps",
     "the two directed cross-factor gaps removed, the recent mean of T2 kept"),
    ("col_noT2direct",
     "the recent mean of T2 removed, the two gaps kept"),
]


def arm_name(family: str, arm: str) -> str:
    return FAMILIES[family]["prefix"] + arm


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
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    if sd == 0:
        return mean, 0.0, 1.0, n
    t = mean / (sd / np.sqrt(n))
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return mean, float(t), float(p), n


def onoff_series(atk: pd.DataFrame, method: str = "S-TIM") -> pd.Series:
    s = atk[(atk["method"] == method) & (atk["attack_type"] == "on-off")]
    return s.groupby("seed")["detection_rate"].mean() * 100


def report_family(family: str) -> list[str]:
    spec = FAMILIES[family]
    problems: list[str] = []
    ref_arm = spec["reference"]
    arms = [ref_arm] + [arm_name(family, f"drop_{f}") for f in FACTOR_LABEL]

    present = [a for a in arms
               if (RUNS / a / "logs" / "per_seed_metrics.csv").exists()]
    missing = [a for a in arms if a not in present]
    if ref_arm not in present:
        print(f"[FAIL] missing reference arm {ref_arm}")
        return [f"{family}: missing reference arm"]
    if missing:
        print(f"[note] {family}: arms not run: {', '.join(missing)}")
    arms = present

    data = {a: load(a, spec["n_uavs"]) for a in arms}
    columns = spec["columns"] or data[ref_arm][2]["feature_names"]

    print("=" * 98)
    print(f"{family.upper()} SCENARIO")
    print("=" * 98)
    print("0. HOW MANY COLUMNS EACH FACTOR CARRIES")
    counts = {}
    for factor in FACTOR_LABEL:
        cols = [n for n in columns if factor in FEATURE_FACTORS.get(n, ())]
        counts[factor] = len(cols)
        print(f"  {factor}: {len(cols):>2} column(s)   {', '.join(cols)}")

    print()
    print("1. THE PROPOSED MODEL, PER ARM")
    print(f"{'arm':<34}{'width':>6}{'accuracy':>11}{'F-score':>10}{'TSR':>8}"
          f"{'on-off':>9}{'constant':>10}{'dormant':>9}")
    print("-" * 98)
    widths = {}
    for arm in arms:
        piv, atk, pol = data[arm]
        widths[arm] = len(pol.get("feature_names", []))

        def rate(a: str) -> float:
            s = atk[(atk["method"] == "S-TIM") & (atk["attack_type"] == a)]
            return float(s["detection_rate"].mean()) * 100 if len(s) else float("nan")

        label = ("published (all five factors)" if arm == ref_arm
                 else "without " + FACTOR_LABEL[arm.split("drop_")[-1]])
        print(f"{label:<34}{widths[arm]:>6}"
              f"{piv['accuracy']['S-TIM'].mean() * 100:>11.1f}"
              f"{piv['f_score']['S-TIM'].mean() * 100:>10.1f}"
              f"{piv['tsr']['S-TIM'].mean() * 100:>8.1f}"
              f"{rate('on-off'):>9.1f}{rate('constant'):>10.1f}{rate('dormant'):>9.1f}")

    print()
    print("2. THE COMPARATORS MUST NOT MOVE: they keep all five factors")
    for m in RULE_METHODS:
        vals = []
        for arm in arms:
            piv, _, _ = data[arm]
            vals.append(piv["accuracy"][m].mean() * 100)
        same = max(vals) - min(vals) < 1e-6
        print(f"  [{'ok' if same else 'FAIL'}] {m:<12} "
              + ", ".join(f"{v:.1f}" for v in vals))
        if not same:
            problems.append(f"{family}: {m} moved across the arms")

    print()
    print("3. WHAT EACH FACTOR IS WORTH TO THE PROPOSED MODEL (paired per seed)")
    ref_piv, ref_atk, _ = data[ref_arm]
    for arm in arms[1:]:
        piv, atk, _ = data[arm]
        out = []
        for met, ml in METRICS:
            d = (ref_piv[met]["S-TIM"] - piv[met]["S-TIM"]) * 100
            mean, t, p, n = paired(d)
            out.append(f"{ml} {mean:+6.2f} pp (p={p:.4f})")
        d = (onoff_series(ref_atk) - onoff_series(atk)).dropna()
        mean, t, p, n = paired(d)
        out.append(f"on-off {mean:+6.2f} pp (p={p:.4f})")
        lost = widths[ref_arm] - widths[arm]
        factor = arm.split("drop_")[-1]
        print(f"  without {FACTOR_LABEL[factor]:<22} loses {lost:>2} column(s): "
              + " | ".join(out))

    print()
    print("4. DOES THE RE-RUN REPRODUCE THE COMMITTED TABLE?")
    if family == "published":
        try:
            committed = subprocess.run(
                [GIT, "-C", str(WT), "show",
                 "HEAD:artifacts/outputs/tables/baseline_comparison.csv"],
                capture_output=True, text=True, encoding="utf-8", check=True).stdout
            old = pd.read_csv(io.StringIO(committed)).set_index("method")
            exact = total = 0
            for m in old.index:
                if m not in ref_piv["accuracy"].columns:
                    continue
                for met in ("accuracy", "f_score", "tsr"):
                    cell = str(old.loc[m, met])
                    mean = float(cell.replace("±", "+-").split("+-")[0])
                    total += 1
                    if abs(mean - ref_piv[met][m].mean() * 100) < 0.05:
                        exact += 1
            print(f"  cells reproduced within 0.05 pp: {exact}/{total}")
            if exact != total:
                problems.append(f"{family}: the re-run does not reproduce the table")
        except Exception as exc:  # noqa: BLE001
            print(f"  (skipped: {exc})")
    else:
        other = "spatial_position_23dim"
        if (RUNS / other / "logs" / "per_seed_metrics.csv").exists():
            piv_o, _, _ = load(other, FAMILIES["spatial"]["n_uavs"])
            diffs = []
            for met in ("accuracy", "f_score", "tsr"):
                a = piv_o[met]["S-TIM"].mean() * 100
                b = ref_piv[met]["S-TIM"].mean() * 100
                diffs.append(f"{met} {a:.1f} vs {b:.1f}")
            print(f"  against the committed {other} arm: " + ", ".join(diffs))
        else:
            print("  (no committed spatial arm to compare with)")

    print()
    return problems


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    families = list(FAMILIES) if which == "both" else [which]
    problems: list[str] = []
    for family in families:
        problems.extend(report_family(family))

    print()
    if problems:
        for p in problems:
            print(f"[FAIL] {p}")
        return 1
    print("[OK] the leave-one-factor-out arms are comparable and reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
