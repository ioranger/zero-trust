"""Five-arm comparison for the spatial scenario: 13-dim, published 18-dim,
18-dim risk-only, published 23-dim, and 23-dim gated.

Nothing is recomputed from scratch. Every number comes from the per-arm
per-seed attack-type log (`logs/per_seed_attack_type_metrics.csv`) and the
per-arm summary table (`tables/baseline_comparison.csv`).

The per-seed attack-type log carries duplicate rows for every
(seed, method, attack_type) key, so every mean here is computed after
collapsing those rows, exactly as `modality_complementarity.py` does.

Two summaries are reported side by side because they answer different
questions and disagree:

  * the class-macro-average over the four attack classes (equal weight),
    which says how good a detector is on the classes that are actually hard;
  * the population-weighted accuracy over all 800 nodes, which is what the
    headline table reports and which is dominated by the 560 benign nodes.

The class populations are read from the log itself (`n_nodes` per class) and
cross-checked against the published 52/53/53/82/560 split.

Usage:
    python -u artifacts/analysis/spatial_arms_final_compare.py \
        --arm "label=path/to/per_seed_attack_type_metrics.csv" ...
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

ATTACK_ORDER = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]
METHODS = ["S-TIM", "MLP-Trust", "LR-Trust", "MFA", "FUBA", "GALTrust",
           "GDM-DTM", "AHP-Entropy"]

# Published class populations of the spatial scenario (800 UAVs, 30% malicious).
DECLARED_POP = {"constant": 52, "dormant": 53, "on-off": 53,
                "position-inconsistent": 82, "benign": 560}

# Acceptance lines set before the gated arm was launched.
ACCEPTANCE = {"constant": 90.8, "dormant": 95.6, "on-off": 88.0,
              "position-inconsistent": 83.6, "benign": 97.4}


def load_arm(path: Path) -> pd.DataFrame:
    """Load one arm's attack-type log and collapse the duplicated keys."""
    df = pd.read_csv(path)
    df = df.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    df["seed"] = df["seed"].astype(int)
    df["detection_rate"] = df["detection_rate"].astype(float)
    return (df.groupby(["seed", "method", "attack_type", "n_uavs",
                        "malicious_ratio"], as_index=False)["detection_rate"].mean())


def class_populations(path: Path) -> dict:
    """Read the class populations from the raw log.

    `load_arm` drops `n_nodes` because a groupby aggregation keeps only the
    grouping columns, so the populations are read from the file directly.
    """
    raw = pd.read_csv(path)
    pops = {}
    for c, g in raw.groupby("attack_type"):
        vals = sorted(set(g["n_nodes"].dropna().astype(int))) if "n_nodes" in g else []
        if vals:
            pops[c] = int(vals[0])
    return pops


def main_slice(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the official main-table slice (largest n_uavs at the modal ratio)."""
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


def class_rates(df: pd.DataFrame, method: str) -> dict:
    """Mean detection rate per attack class for one method."""
    out = {}
    for c in ATTACK_ORDER:
        sub = df[(df["method"] == method) & (df["attack_type"] == c)]
        out[c] = float(sub["detection_rate"].mean()) * 100 if len(sub) else float("nan")
    return out


def fmt_p(p: float) -> str:
    if p < 1e-4:
        return "<0.0001"
    return f"{p:.4f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="label=path/to/per_seed_attack_type_metrics.csv")
    ap.add_argument("--arm-table", action="append", default=[],
                    help="label=path/to/baseline_comparison.csv (summary table)")
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
        print(f"[load] {label}: {len(df)} rows, {df['seed'].nunique()} seeds, "
              f"methods={sorted(df['method'].unique())}")

    tables: dict[str, pd.DataFrame] = {}
    for spec in args.arm_table:
        label, _, path = spec.partition("=")
        p = Path(path)
        if not p.exists():
            print(f"!! missing arm table: {p}", file=sys.stderr)
            continue
        tables[label] = pd.read_csv(p)

    if not arms:
        print("no arms loaded", file=sys.stderr)
        return 2

    out: list[str] = []
    out.append("=" * 108)
    out.append("FIVE-ARM SPATIAL COMPARISON -- per-class detection rate (%) and the two summaries")
    out.append("=" * 108)

    # ---------------------------------------------------------------- class 1
    out.append("")
    out.append("1. class populations in the spatial scenario (read from the log)")
    out.append("-" * 108)
    any_arm = next(iter(arms.values()))
    pops = {}
    for spec in args.arm:
        label, _, path = spec.partition("=")
        if label not in arms:
            continue
        pops = class_populations(Path(path))
        break
    total = sum(pops.get(c, 0) for c in ATTACK_ORDER)
    for c in ATTACK_ORDER:
        n = pops.get(c, 0)
        flag = "" if n == DECLARED_POP[c] else f"  <-- declared {DECLARED_POP[c]}"
        out.append(f"   {c:<24}{n:>6} nodes   {n / total * 100:>6.1f}% of population{flag}")
    out.append(f"   {'TOTAL':<24}{total:>6} nodes")
    out.append("")
    out.append("   the headline table weights by population share; the macro-average weights")
    out.append("   the four attack classes equally. The two disagree because benign is 70%")
    out.append("   of the population and the attack classes are only 30%.")

    # ---------------------------------------------------------------- class 2
    out.append("")
    out.append("=" * 108)
    out.append("2. per-class detection rate (%) for every method, per arm")
    out.append("=" * 108)
    for method in METHODS:
        if not any(method in set(df["method"]) for df in arms.values()):
            continue
        out.append("")
        out.append(f"--- {method} " + "-" * max(1, 96 - len(method)))
        head = f"{'arm':<22}" + "".join(f"{c:>15}" for c in ATTACK_ORDER)
        out.append(head)
        out.append("-" * 108)
        for lab, df in arms.items():
            if method not in set(df["method"]):
                continue
            r = class_rates(df, method)
            row = f"{lab:<22}"
            for c in ATTACK_ORDER:
                row += f"{r[c]:>15.1f}" if not math.isnan(r[c]) else f"{'--':>15}"
            out.append(row)

    # ---------------------------------------------------------------- class 3
    out.append("")
    out.append("=" * 108)
    out.append("3. the two summaries: class-macro-average (4 attack classes) vs population-weighted accuracy")
    out.append("=" * 108)
    out.append(f"{'arm':<22}{'method':<12}{'macro-4':>10}{'macro-5':>10}"
               f"{'pop-weighted':>15}{'table acc':>12}")
    out.append("-" * 108)
    summary: dict[str, dict] = {}
    for lab, df in arms.items():
        for method in ("S-TIM", "MLP-Trust", "LR-Trust"):
            if method not in set(df["method"]):
                continue
            r = class_rates(df, method)
            macro4 = sum(r[c] for c in CLASSES) / 4.0
            macro5 = sum(r[c] for c in ATTACK_ORDER) / 5.0
            pw = sum(pops[c] * r[c] for c in ATTACK_ORDER) / total
            tab_acc = float("nan")
            if lab in tables and method in set(tables[lab]["method"]):
                tab_acc = float(tables[lab].loc[tables[lab]["method"] == method,
                                                "accuracy"].iloc[0].split(" ")[0])
            summary.setdefault(lab, {})[method] = {"rates": r, "macro4": macro4,
                                                    "macro5": macro5, "pw": pw,
                                                    "tab_acc": tab_acc}
            out.append(f"{lab:<22}{method:<12}{macro4:>10.1f}{macro5:>10.1f}"
                       f"{pw:>15.1f}{tab_acc:>12.1f}")
    out.append("")
    out.append("   macro-4 = equal weight over constant / dormant / on-off / position-inconsistent")
    out.append("   macro-5 = equal weight over all five classes including benign")
    out.append("   pop-weighted = sum(pop_c * rate_c) / 800, reconstructed from the per-class rates")
    out.append("   table acc = accuracy column of the arm's own tables/baseline_comparison.csv")

    # ---------------------------------------------------------------- class 4
    out.append("")
    out.append("=" * 108)
    out.append("4. paired S-TIM minus MLP-Trust, within each arm (same seeds)")
    out.append("=" * 108)
    out.append(f"{'arm':<22}{'attack class':>22}{'delta pp':>12}{'t':>9}{'p':>10}{'n':>6}")
    out.append("-" * 108)
    for lab, df in arms.items():
        if "S-TIM" not in set(df["method"]) or "MLP-Trust" not in set(df["method"]):
            continue
        for c in ATTACK_ORDER:
            sa = df[(df["method"] == "S-TIM") & (df["attack_type"] == c)].set_index("seed")["detection_rate"]
            sb = df[(df["method"] == "MLP-Trust") & (df["attack_type"] == c)].set_index("seed")["detection_rate"]
            res = paired_test(sa, sb)
            if res is None:
                continue
            md, t, p, _dz, n = res
            out.append(f"{lab:<22}{c:>22}{100 * md:>12.1f}{t:>9.2f}{fmt_p(p):>10}{n:>6}")

    # ---------------------------------------------------------------- class 5
    out.append("")
    out.append("=" * 108)
    out.append("5. paired S-TIM, arm minus arm (same seeds)")
    out.append("=" * 108)
    labels = list(arms.keys())
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            la, lb = labels[i], labels[j]
            A, B = arms[la], arms[lb]
            if "S-TIM" not in set(A["method"]) or "S-TIM" not in set(B["method"]):
                continue
            out.append(f"   {la}  MINUS  {lb}")
            out.append(f"   {'attack class':>22}{'delta pp':>12}{'t':>9}{'p':>10}{'n':>6}")
            for c in ATTACK_ORDER:
                sa = A[(A["method"] == "S-TIM") & (A["attack_type"] == c)].set_index("seed")["detection_rate"]
                sb = B[(B["method"] == "S-TIM") & (B["attack_type"] == c)].set_index("seed")["detection_rate"]
                res = paired_test(sa, sb)
                if res is None:
                    continue
                md, t, p, _dz, n = res
                out.append(f"   {c:>22}{100 * md:>12.1f}{t:>9.2f}{fmt_p(p):>10}{n:>6}")
            out.append("")

    # ---------------------------------------------------------------- class 6
    if "gated" in summary:
        out.append("=" * 108)
        out.append("6. acceptance lines for the gated arm (S-TIM)")
        out.append("=" * 108)
        out.append(f"{'attack class':>22}{'gated':>10}{'required':>11}{'result':>10}")
        out.append("-" * 108)
        r = summary["gated"]["S-TIM"]["rates"]
        for c in ATTACK_ORDER:
            need = ACCEPTANCE[c]
            got = r[c]
            ok = got >= need
            out.append(f"{c:>22}{got:>10.1f}{need:>11.1f}"
                       f"{('PASS' if ok else f'FAIL {got - need:+.1f}pp'):>10}")
        out.append("")
        out.append(f"   macro-4 {summary['gated']['S-TIM']['macro4']:.1f}   "
                   f"pop-weighted {summary['gated']['S-TIM']['pw']:.1f}   "
                   f"table accuracy {summary['gated']['S-TIM']['tab_acc']:.1f}")

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
