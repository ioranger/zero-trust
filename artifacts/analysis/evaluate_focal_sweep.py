"""Evaluate every arm of the focal gamma sweep against its pre-registered
acceptance lines.

The pre-registration is in
`artifacts/analysis/FOCAL_GAMMA_SWEEP_PREREGISTRATION.md`. This script reads
only the arms' own logs, so no line can move after the fact.

Arms: the published spatial configuration, the focal arm at gamma = 2, and
the two sweep arms at gamma = 0.5 and gamma = 1.0.

    python -u artifacts/analysis/evaluate_focal_sweep.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "runs"
REFERENCE = "spatial_position_23dim"
ARMS = [
    ("spatial_position_focal", 2.0),
    ("spatial_position_focal_g10", 1.0),
    ("spatial_position_focal_g05", 0.5),
]
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]

# the acceptance lines of the sweep pre-registration, plus the strict
# constant line from the original focal pre-registration
ACCEPTANCE = [
    ("class mean over the four attack classes", 89.0),
    ("aggregate accuracy", 93.3),
    ("constant", 87.2),
    ("constant (strict line of the first pre-registration)", 90.8),
    ("dormant", 93.4),
    ("on--off", 91.7),
    ("position-inconsistent", 83.6),
    ("benign specificity", 93.0),
]
MAX_REGRESSION = 1.0


def load(run: str) -> pd.DataFrame:
    df = pd.read_csv(RUNS / run / "logs" / "per_seed_attack_type_metrics.csv")
    df = df.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    df["seed"] = df["seed"].astype(int)
    df["detection_rate"] = df["detection_rate"].astype(float)
    return (df.groupby(["seed", "method", "attack_type", "n_uavs",
                        "malicious_ratio"], as_index=False)["detection_rate"].mean())


def rates(df: pd.DataFrame, method: str) -> dict:
    out = {}
    for c in CLASSES + ["benign"]:
        sub = df[(df["method"] == method) & (df["attack_type"] == c)]
        out[c] = float(sub["detection_rate"].mean()) * 100 if len(sub) else float("nan")
    return out


def paired_two(a: pd.DataFrame, ma: str, b: pd.DataFrame, mb: str, cls: str):
    sa = a[(a["method"] == ma) & (a["attack_type"] == cls)].set_index("seed")["detection_rate"]
    sb = b[(b["method"] == mb) & (b["attack_type"] == cls)].set_index("seed")["detection_rate"]
    m = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
    if len(m) < 2:
        return None
    d = m["a"] - m["b"]
    sd = d.std(ddof=1)
    if sd == 0:
        return (d.mean() * 100, 0.0, 1.0, len(m))
    t = d.mean() / (sd / math.sqrt(len(m)))
    try:
        from scipy import stats
        p = float(2.0 * stats.t.sf(abs(t), df=len(m) - 1))
    except Exception:
        p = float("nan")
    return (d.mean() * 100, t, p, len(m))


def base_row(run: str, method: str) -> dict:
    f = RUNS / run / "tables" / "baseline_comparison.csv"
    d = pd.read_csv(f, encoding="utf-8-sig").set_index("method")
    out = {}
    for col in ("accuracy", "f_score", "tsr"):
        s = str(d.loc[method, col]).replace("\u00b1", "+-").replace("卤", "+-")
        out[col] = float(s.split("+-")[0].strip())
    return out


def main() -> int:
    ref = load(REFERENCE)
    ref_s = rates(ref, "S-TIM")
    ref_m = rates(ref, "MLP-Trust")
    ref_base = base_row(REFERENCE, "S-TIM")
    ref_macro = sum(ref_s[c] for c in CLASSES) / 4.0

    print("=" * 108)
    print("FOCAL GAMMA SWEEP -- published arm and the three focal arms")
    print("=" * 108)
    print(f"{'quantity':<40}{'published':>11}{'gamma 2.0':>11}{'gamma 1.0':>11}"
          f"{'gamma 0.5':>11}")
    print("-" * 108)

    arms = {}
    for run, gamma in ARMS:
        if not (RUNS / run / "logs" / "per_seed_attack_type_metrics.csv").exists():
            print(f"!! missing arm: {run}")
            continue
        df = load(run)
        s = rates(df, "S-TIM")
        m = rates(df, "MLP-Trust")
        b = base_row(run, "S-TIM")
        arms[gamma] = (run, df, s, m, b)

    def row(label, published, *vals):
        print(f"{label:<40}{published:>11.1f}" + "".join(f"{v:>11.1f}" for v in vals))

    gammas = sorted(arms.keys(), reverse=True)
    row("accuracy", ref_base["accuracy"], *[arms[g][4]["accuracy"] for g in gammas])
    row("F-score", ref_base["f_score"], *[arms[g][4]["f_score"] for g in gammas])
    row("TSR proxy", ref_base["tsr"], *[arms[g][4]["tsr"] for g in gammas])
    row("class mean (four attack classes)", ref_macro,
        *[sum(arms[g][2][c] for c in CLASSES) / 4.0 for g in gammas])
    for c in CLASSES:
        row(f"detection, {c}", ref_s[c], *[arms[g][2][c] for g in gammas])
    row("benign specificity", ref_s["benign"], *[arms[g][2][c] for c in ["benign"] for g in gammas])

    print()
    print("=" * 108)
    print("THE PROPOSED MODEL AGAINST THE FEATURE-MATCHED CONTROL, EACH ARM")
    print("     (same objective on both sides, same run)")
    print("=" * 108)
    print(f"{'arm':<32}{'class':>22}{'delta pp':>10}{'t':>8}{'p':>10}")
    print("-" * 108)
    ctrl = {}
    for g in gammas:
        run, df, s, m, b = arms[g]
        print(f"{'published (BCE)':<32}")
        for c in CLASSES + ["benign"]:
            res = paired_two(ref, "S-TIM", ref, "MLP-Trust", c)
            if res is None:
                continue
            d, t, p, n = res
            pt = "<0.0001" if p < 1e-4 else f"{p:.4f}"
            print(f"{'':<32}{c:>22}{d:>10.1f}{t:>8.2f}{pt:>10}")
        ctrl[g] = {}
        for c in CLASSES + ["benign"]:
            res = paired_two(df, "S-TIM", df, "MLP-Trust", c)
            if res is None:
                continue
            d, t, p, n = res
            ctrl[g][c] = (d, p)
            pt = "<0.0001" if p < 1e-4 else f"{p:.4f}"
            print(f"{'focal gamma ' + str(g):<32}{c:>22}{d:>10.1f}{t:>8.2f}{pt:>10}")

    print()
    print("=" * 108)
    print("ACCEPTANCE LINES, PER ARM (pre-registered)")
    print("=" * 108)
    verdicts = {}
    for g in gammas:
        run, df, s, m, b = arms[g]
        macro = sum(s[c] for c in CLASSES) / 4.0
        values = {
            "class mean over the four attack classes": macro,
            "aggregate accuracy": b["accuracy"],
            "constant": s["constant"],
            "constant (strict line of the first pre-registration)": s["constant"],
            "dormant": s["dormant"],
            "on--off": s["on-off"],
            "position-inconsistent": s["position-inconsistent"],
            "benign specificity": s["benign"],
        }
        print(f"--- gamma {g} ---")
        lines = []
        for label, need in ACCEPTANCE:
            got = values[label]
            ok = got >= need
            lines.append((label, got, need, ok))
            print(f"  [{'PASS' if ok else 'FAIL'}] {label:<58} {got:>7.1f}  (needs >= {need:.1f})")
        for c in CLASSES:
            drop = ref_s[c] - s[c]
            ok = drop <= MAX_REGRESSION
            lines.append((f"no regression on {c}", -drop, 0.0, ok))
            print(f"  [{'PASS' if ok else 'FAIL'}] {'no regression on ' + c:<58} "
                  f"{drop:>7.1f}  (may drop at most {MAX_REGRESSION:.1f})")
        lead = [c for c in ("constant", "dormant") if ctrl[g].get(c, (0, 1))[0] > 0
                and ctrl[g][c][1] < 0.05]
        ok = len(lead) == 2
        lines.append(("leads the control on the level classes at p<0.05", 0.0, 0.0, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {'leads the control on constant and dormant':<58} "
              f"{'':>7}  (significant on {len(lead)} of 2)")
        passed = all(x[3] for x in lines)
        print(f"  VERDICT for gamma {g}: {'PASS' if passed else 'FAIL'} "
              f"({sum(1 for x in lines if x[3])}/{len(lines)})")
        print()
        verdicts[g] = {"arm": run, "pass": passed,
                       "lines": [{"line": l, "value": v, "required": n, "ok": ok}
                                 for l, v, n, ok in lines],
                       "rates": s, "class_mean": macro, "baseline": b}

    out = ROOT / "artifacts" / "analysis" / "focal_sweep_verdict.json"
    out.write_text(json.dumps(verdicts, indent=2), encoding="utf-8")
    print(f"verdicts written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
