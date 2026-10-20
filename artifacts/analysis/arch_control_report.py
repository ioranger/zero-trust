"""Four-arm architecture control: does making every S-TIM head participate help?

Four arms, all on configs/default.json (18-dim input, N=15, 60 train seeds,
180 epochs, 50 evaluation seeds). The encoder, the input width, the optimiser
and the early-stopping rule are identical in every arm; the only difference is
which auxiliary loss terms are active.

  paper_18dim_check : the published configuration (value 0.10, trust-weight
                      0.25, action 0.20, modality 0.00)
  heads_risk_only   : control, all four auxiliary loss weights 0
  heads_mod_only    : only the modality head supervised (weight 0.30)
  heads_full        : all four auxiliary heads supervised

The modality head is the auxiliary head that should be able to help: its
target (benign / constant / dormant / on-off) is the one auxiliary label the
binary risk label cannot express, since constant, dormant and on-off attackers
all carry y = 1. The script reports whether that head actually learned and
whether the detection metrics moved.

Run from the repository root:
    python -u artifacts/analysis/arch_control_report.py
"""

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "artifacts" / "analysis" / "runs"

ARMS = [
    ("paper_18dim_check", "published (value/weight/action ON, modality OFF)"),
    ("heads_risk_only", "control (ALL four aux OFF)"),
    ("heads_mod_only", "modality head ON only"),
    ("heads_full", "all four aux ON"),
]

METRICS = [("accuracy", "acc"), ("f_score", "F1"), ("tsr", "TSR")]


def paired(d):
    d = d.dropna()
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    if sd == 0:
        return mean, float("inf"), 0.0, n
    t = mean / (sd / np.sqrt(n))
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return mean, float(t), float(p), n


def load(name):
    base = RUNS / name
    metrics = pd.read_csv(base / "logs" / "per_seed_metrics.csv")
    main = metrics[
        (metrics["scenario"].isin(["ratio", "figure_ratio"]))
        & (metrics["n_uavs"] == 15)
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


def onoff(atk, method):
    s = atk[(atk["method"] == method) & (atk["attack_type"] == "on-off")]
    return float(s["detection_rate"].mean()) * 100 if len(s) else float("nan")


print("=" * 96)
print("1. MAIN TABLE PER ARM   (mean over 50 evaluation seeds)")
print("=" * 96)
print(f"{'arm':<46}{'S-TIM acc':>11}{'MLP acc':>10}{'S-TIM F1':>11}"
      f"{'MLP F1':>9}{'S-TIM TSR':>12}{'on-off':>9}")
print("-" * 96)
data = {}
for name, label in ARMS:
    piv, atk, pol = load(name)
    data[name] = (piv, atk, pol)
    s, b = piv["accuracy"]["S-TIM"], piv["accuracy"]["MLP-Trust"]
    sf, bf = piv["f_score"]["S-TIM"], piv["f_score"]["MLP-Trust"]
    st = piv["tsr"]["S-TIM"]
    print(f"{label:<46}{s.mean()*100:>11.1f}{b.mean()*100:>10.1f}"
          f"{sf.mean()*100:>11.1f}{bf.mean()*100:>9.1f}{st.mean()*100:>12.1f}"
          f"{onoff(atk, 'S-TIM'):>9.1f}")

print()
print("=" * 96)
print("2. DID THE AUXILIARY HEADS ACTUALLY LEARN?")
print("=" * 96)
for name, label in ARMS:
    piv, atk, pol = data[name]
    ms = pol.get("modality_supervision", {})
    w = pol.get("auxiliary_loss_weights", {})
    acc = ms.get("validation_accuracy")
    chance = ms.get("chance_accuracy", 0.25)
    acc_s = f"{acc:.4f}" if isinstance(acc, (int, float)) else "n/a"
    print(f"  {label:<46} modality w={w.get('modality', '?')!s:<5} "
          f"val_acc={acc_s}  (chance {chance})")
    print(f"      auxiliary weights: {({k: v for k, v in w.items() if k != 'risk'})}")

print()
print("=" * 96)
print("3. WITHIN-ARM PAIRED TEST  S-TIM minus MLP-Trust")
print("=" * 96)
for name, label in ARMS:
    piv, atk, pol = data[name]
    out = []
    for met, ml in METRICS:
        d = (piv[met]["S-TIM"] - piv[met]["MLP-Trust"]) * 100
        mean, t, p, n = paired(d)
        out.append(f"{ml} {mean:+.2f}pp (p={p:.4f})")
    print(f"  {label:<46} " + " | ".join(out))

print()
print("=" * 96)
print("4. CROSS-ARM PAIRED TESTS   S-TIM(arm) minus S-TIM(reference)")
print("=" * 96)


def cross(ref_name, arm_name, ref_label, arm_label):
    rpiv = data[ref_name][0]
    apiv = data[arm_name][0]
    print(f"\n  {arm_label}  minus  {ref_label}")
    for met, ml in METRICS:
        d = (apiv[met]["S-TIM"] - rpiv[met]["S-TIM"]) * 100
        mean, t, p, n = paired(d)
        ties = int((d.abs() < 1e-9).sum())
        print(f"    {ml:<4} {mean:+6.2f}pp   p={p:.4f}   ties={ties}/{n}   "
              f"sd={d.std(ddof=1):.2f}")


cross("heads_risk_only", "paper_18dim_check",
      "control (all aux off)", "published (value/weight/action on)")
cross("heads_risk_only", "heads_mod_only",
      "control (all aux off)", "modality only")
cross("heads_risk_only", "heads_full",
      "control (all aux off)", "all four heads")
cross("paper_18dim_check", "heads_full",
      "published (modality off)", "all four heads")

print()
print("=" * 96)
print("5. EQUIVALENCE CHECK: published arm vs git HEAD table")
print("=" * 96)
GIT = r"F:\zero trust\tools\MinGit\cmd\git.exe"
WT = Path(r"F:\zero trust\gitwork")
if (WT / ".git").exists() or (WT / "HEAD").exists():
    committed = subprocess.run(
        [GIT, "-C", str(WT), "show",
         "HEAD:artifacts/outputs/tables/baseline_comparison.csv"],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout

    def parse(txt):
        df = pd.read_csv(io.StringIO(txt)).set_index("method")
        out = {}
        for m, row in df.iterrows():
            out[m] = {}
            for col in ("accuracy", "f_score", "tsr"):
                pp = str(row[col]).replace("±", "+-").split("+-")
                out[m][col] = (float(pp[0]), float(pp[1]) if len(pp) > 1 else 0.0)
        return out

    old = parse(committed)
    fresh = parse((ROOT / "artifacts" / "outputs" / "tables" / "baseline_comparison.csv")
                  .read_text(encoding="utf-8-sig"))
    exact = total = 0
    for m in old:
        for col in ("accuracy", "f_score", "tsr"):
            total += 1
            if (abs(old[m][col][0] - fresh[m][col][0]) < 1e-9
                    and abs(old[m][col][1] - fresh[m][col][1]) < 1e-9):
                exact += 1
    print(f"  exact cell matches: {exact}/{total}")
else:
    print("  (no git worktree available; skipped)")
