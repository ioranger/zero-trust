"""Evaluate the focal-loss arm against its pre-registered acceptance lines.

The acceptance lines are those in
`artifacts/analysis/FOCAL_ARM_PREREGISTRATION.md`, which was committed before
the arm was run. This script reads nothing but the two arms' own logs, so it
cannot move a line after the fact.

Reference arm: `spatial_position_23dim`, the published spatial configuration.
Arm under test: `spatial_position_focal`.

    python -u artifacts/analysis/evaluate_focal_arm.py
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
ARM = "spatial_position_focal"

CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]
POPS = {"constant": 52, "dormant": 53, "on-off": 53,
        "position-inconsistent": 82, "benign": 560}

# The pre-registered acceptance lines, verbatim from the pre-registration.
ACCEPTANCE = [
    ("class mean over the four attack classes", "ge", 90.0),
    ("aggregate accuracy", "ge", 93.3),
    ("constant", "ge", 90.8),
    ("dormant", "ge", 95.6),
    ("on--off", "ge", 91.7),
    ("position-inconsistent", "ge", 83.6),
    ("benign specificity", "ge", 93.0),
]
# no attack class may regress by more than 1.0 pp against the published arm
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


def paired(a: pd.DataFrame, b: pd.DataFrame, method: str, cls: str):
    return paired_two(a, method, b, method, cls)


def paired_two(a: pd.DataFrame, method_a: str, b: pd.DataFrame,
               method_b: str, cls: str):
    """Paired t-test between two methods that may live in different arms."""
    sa = a[(a["method"] == method_a) & (a["attack_type"] == cls)].set_index("seed")["detection_rate"]
    sb = b[(b["method"] == method_b) & (b["attack_type"] == cls)].set_index("seed")["detection_rate"]
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


def baseline_table(run: str, method: str) -> dict:
    f = RUNS / run / "tables" / "baseline_comparison.csv"
    d = pd.read_csv(f, encoding="utf-8-sig").set_index("method")
    out = {}
    for col in ("accuracy", "f_score", "tsr"):
        s = str(d.loc[method, col]).replace("\u00b1", "+-").replace("卤", "+-")
        out[col] = float(s.split("+-")[0].strip())
    return out


def main() -> int:
    if not (RUNS / ARM / "logs" / "per_seed_attack_type_metrics.csv").exists():
        print(f"!! the arm has not been run yet: {RUNS / ARM}")
        return 2
    ref = load(REFERENCE)
    new = load(ARM)
    ref_base = baseline_table(REFERENCE, "S-TIM")
    new_base = baseline_table(ARM, "S-TIM")
    new_mlp = baseline_table(ARM, "MLP-Trust")
    ref_mlp = baseline_table(REFERENCE, "MLP-Trust")

    r_ref = rates(ref, "S-TIM")
    r_new = rates(new, "S-TIM")
    m_ref = rates(ref, "MLP-Trust")
    m_new = rates(new, "MLP-Trust")

    macro_ref = sum(r_ref[c] for c in CLASSES) / 4.0
    macro_new = sum(r_new[c] for c in CLASSES) / 4.0
    macro_mlp_new = sum(m_new[c] for c in CLASSES) / 4.0
    macro_mlp_ref = sum(m_ref[c] for c in CLASSES) / 4.0

    print("=" * 96)
    print(f"FOCAL ARM EVALUATION -- {ARM} against {REFERENCE}")
    print("=" * 96)
    print(f"{'quantity':<38}{'published':>12}{'focal':>12}{'delta':>10}"
          f"{'focal MLP':>14}")
    print("-" * 96)
    rows = [
        ("accuracy", ref_base["accuracy"], new_base["accuracy"], new_mlp["accuracy"]),
        ("F-score", ref_base["f_score"], new_base["f_score"], new_mlp["f_score"]),
        ("TSR proxy", ref_base["tsr"], new_base["tsr"], new_mlp["tsr"]),
        ("class mean (four attack classes)", macro_ref, macro_new, macro_mlp_new),
    ]
    for c in CLASSES:
        rows.append((f"detection, {c}", r_ref[c], r_new[c], m_new[c]))
    rows.append(("benign specificity", r_ref["benign"], r_new["benign"], m_new["benign"]))
    for label, a, b, m in rows:
        print(f"{label:<38}{a:>12.1f}{b:>12.1f}{b - a:>+10.1f}{m:>14.1f}")

    print()
    print("=" * 96)
    print("PAIRED PER-SEED TESTS (same 19 evaluation seeds)")
    print("=" * 96)
    print(f"{'comparison':<46}{'class':>22}{'delta pp':>10}{'t':>8}{'p':>10}")
    print("-" * 96)
    for label, a, ma, b, mb in (
            ("focal S-TIM minus published S-TIM", new, "S-TIM", ref, "S-TIM"),
            ("focal S-TIM minus focal MLP-Trust", new, "S-TIM", new, "MLP-Trust"),
            ("focal MLP-Trust minus published MLP-Trust", new, "MLP-Trust", ref, "MLP-Trust"),
            ("published S-TIM minus published MLP-Trust", ref, "S-TIM", ref, "MLP-Trust")):
        for c in CLASSES + ["benign"]:
            res = paired_two(a, ma, b, mb, c)
            if res is None:
                continue
            d, t, p, n = res
            pt = "<0.0001" if p == p and p < 1e-4 else f"{p:.4f}"
            print(f"{label:<46}{c:>22}{d:>10.1f}{t:>8.2f}{pt:>10}")

    print()
    print("=" * 96)
    print("ACCEPTANCE LINES (pre-registered)")
    print("=" * 96)
    results = []
    values = {
        "class mean over the four attack classes": macro_new,
        "aggregate accuracy": new_base["accuracy"],
        "constant": r_new["constant"],
        "dormant": r_new["dormant"],
        "on--off": r_new["on-off"],
        "position-inconsistent": r_new["position-inconsistent"],
        "benign specificity": r_new["benign"],
    }
    for label, _op, need in ACCEPTANCE:
        got = values[label]
        ok = got >= need
        results.append((label, got, need, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<44} {got:>7.1f}  (needs >= {need:.1f})")
    for c in CLASSES:
        drop = r_ref[c] - r_new[c]
        ok = drop <= MAX_REGRESSION
        results.append((f"no regression > {MAX_REGRESSION} pp on {c}", -drop, 0.0, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {'no regression on ' + c:<44} "
              f"{drop:>7.1f}  (may drop at most {MAX_REGRESSION:.1f})")

    passed = all(ok for *_x, ok in results)
    print()
    print(f"  VERDICT: {'PASS' if passed else 'FAIL'} "
          f"({sum(1 for r in results if r[3])}/{len(results)} lines met)")
    print()
    print("  The comparator in the same run, for the record:")
    print(f"    MLP-Trust, published configuration : accuracy {ref_mlp['accuracy']:.1f}, "
          f"F-score {ref_mlp['f_score']:.1f}, class mean {macro_mlp_ref:.1f}")
    print(f"    MLP-Trust, focal objective         : accuracy {new_mlp['accuracy']:.1f}, "
          f"F-score {new_mlp['f_score']:.1f}, class mean {macro_mlp_new:.1f}")
    print("    The comparator is trained with the same objective inside the same run,")
    print("    so a difference between the two is a difference in the evidence, not in")
    print("    the training signal. Whatever this arm shows, it is reported with that")

    verdict = {
        "arm": ARM,
        "reference": REFERENCE,
        "pass": passed,
        "lines": [{"line": lab, "value": v, "required": n, "ok": ok}
                  for lab, v, n, ok in results],
        "published": ref_base,
        "focal": new_base,
        "focal_mlp": new_mlp,
        "class_mean": {"published": macro_ref, "focal": macro_new,
                       "focal_mlp": macro_mlp_new, "published_mlp": macro_mlp_ref},
    }
    out = ROOT / "artifacts" / "analysis" / "focal_arm_verdict.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    print(f"    comparison written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
