"""Data-efficiency sweep: does the proposed model beat its feature-matched
control when the training set is small?

The published comparison cannot answer the question, because the generator's
training split is perfectly separable and every learned method reaches about
97% on it. The regime in which the architecture might matter is one in which
the training set is too small for the risk head to learn, on its own, which
attack class it is looking at: constant, dormant and on--off attackers all
carry y = 1, so the binary risk label gives the risk head no signal that
distinguishes them. The modality head is the only auxiliary target in the
network that is not a function of that label, so it is the only auxiliary
supervision that could carry new information.

This script assembles the sweep from the committed arm logs:

  K            number of training seeds (12, 24, 60)
  mod          the modality head supervised at weight 0.30, other auxiliaries off
  risk         every auxiliary loss off
  pub          the published configuration

    python -u artifacts/analysis/dataeff_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUNS = ROOT / "artifacts" / "analysis" / "runs"

# (training seeds, variant) -> arm directory
ARMS = {
    (12, "mod"): "dataeff_k12_mod",
    (12, "risk"): "dataeff_k12_risk",
    (12, "pub"): "dataeff_k12_pub",
    (24, "mod"): "dataeff_k24_mod",
    (24, "risk"): "dataeff_k24_risk",
    (24, "pub"): "dataeff_k24_pub",
    (60, "mod"): "heads_mod_only",
    (60, "risk"): "heads_risk_only",
    (60, "pub"): "paper_18dim_check",
}
VARIANT_LABEL = {"mod": "modality head supervised",
                 "risk": "all auxiliary losses off",
                 "pub": "published configuration"}
K_LABEL = {12: "12", 24: "24", 60: "60"}


def main() -> int:
    print("=" * 104)
    print("DATA-EFFICIENCY SWEEP -- proposed model against its feature-matched control")
    print("=" * 104)
    print(f"{'arm':<28}{'S-TIM acc':>11}{'F-score':>10}{'TSR':>8}"
          f"{'MLP acc':>10}{'delta':>9}{'modality head':>15}")
    print("-" * 104)

    for (k, variant), arm in ARMS.items():
        base = RUNS / arm / "tables" / "baseline_comparison.csv"
        pol = RUNS / arm / "logs" / "marl_policy.json"
        if not base.exists():
            print(f"{K_LABEL[k]} seeds, {VARIANT_LABEL[variant]:<28} [no arm log]")
            continue
        d = pd.read_csv(base, encoding="utf-8-sig").set_index("method")

        def val(method, col):
            s = str(d.loc[method, col]).replace("\u00b1", "+-").replace("卤", "+-")
            return float(s.split("+-")[0].strip())

        sacc, sf1, stsr = (val("S-TIM", c) for c in ("accuracy", "f_score", "tsr"))
        macc = val("MLP-Trust", "accuracy")
        modacc = "-"
        if pol.exists():
            import json
            p = json.loads(pol.read_text(encoding="utf-8"))
            modacc = f"{p['modality_supervision']['validation_accuracy']:.3f}"
        print(f"{K_LABEL[k]} seeds, {VARIANT_LABEL[variant]:<28}{sacc:>11.1f}{sf1:>10.1f}"
              f"{stsr:>8.1f}{macc:>10.1f}{sacc - macc:>9.1f}{modacc:>15}")

    print("-" * 104)
    print("MLP-Trust consumes the identical 18-dimensional feature vector and is")
    print("trained under the identical protocol, so it is the feature-matched")
    print("control. The modality-head column is the validation accuracy of the")
    print("four-class attack-modality head; a head whose loss weight is zero")
    print("receives no gradient and stays at its initialisation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
