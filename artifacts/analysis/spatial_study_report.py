"""Consolidated report for the spatio-temporal complementarity study.

Runs, in order:

  1. the published-table reproduction check on the default.json re-run arm,
  2. the modality ladder over the four attack classes, with paired tests,
  3. the spatial-block effect (23 dims minus 18 dims, same seeds),
  4. the fusion-mechanism ablation (identical 23-dim vector, three learners),
  5. the rule-based threshold-transfer diagnostic,
  6. the spatial counterfactual sweep.

Everything it prints is derived from committed arm logs or from the generator
itself, so the numbers can be re-derived without re-running the training.

    python -u artifacts/analysis/spatial_study_report.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
ANALYSIS = ROOT / "artifacts" / "analysis"
RUNS = ANALYSIS / "runs"
PY = sys.executable

ARMS = {
    "13d marginal": "spatial_position_13dim",
    "18d marginal+shape": "spatial_position_18dim",
    "23d marginal+shape+spatial": "spatial_position_23dim",
    "23d fusion ablation": "spatial_position_fusion",
}


def run(cmd: list[str], title: str) -> None:
    print("\n" + "#" * 104)
    print(f"# {title}")
    print("#" * 104)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    if rc != 0:
        print(f"!! exit code {rc}")


def arm_arg(label: str) -> list[str]:
    arm = ARMS[label]
    return ["--arm", f"{label}={RUNS / arm / 'logs' / 'per_seed_attack_type_metrics.csv'}"]


def main() -> int:
    have = {lab: (RUNS / arm / "logs" / "per_seed_attack_type_metrics.csv").exists()
            for lab, arm in ARMS.items()}
    missing = [lab for lab, ok in have.items() if not ok]
    if missing:
        print(f"!! missing arms: {', '.join(missing)}")

    run([PY, "-u", str(ANALYSIS / "compare_snapshot_to_published.py"),
         str(ROOT / "artifacts" / "runs" / "paper_18dim_recheck")],
        "1. PUBLISHED TABLE REPRODUCTION (default.json re-run vs committed table)")

    if not missing:
        ladder = []
        for lab in ARMS:
            if lab != "23d fusion ablation":
                ladder += arm_arg(lab)
        run([PY, "-u", str(ANALYSIS / "modality_complementarity.py"), *ladder,
             "--compare", "23d marginal+shape+spatial", "18d marginal+shape",
             "--out", str(ANALYSIS / "modality_ladder.txt")],
            "2. MODALITY LADDER (13 / 18 / 23 features) AND THE SPATIAL-BLOCK EFFECT")

    if have.get("23d fusion ablation"):
        fusion = []
        for lab in ARMS:
            if lab != "13d marginal":
                fusion += arm_arg(lab)
        run([PY, "-u", str(ANALYSIS / "modality_complementarity.py"), *fusion,
             "--compare", "23d fusion ablation", "23d marginal+shape+spatial",
             "--out", str(ANALYSIS / "fusion_ablation.txt")],
            "3. FUSION-MECHANISM ABLATION (identical 23-dim vector, three learners)")

    run([PY, "-u", str(ANALYSIS / "diagnose_rule_threshold_transfer.py")],
        "4. RULE-BASED THRESHOLD TRANSFER (fixed threshold vs threshold-free AUC)")

    run([PY, "-u", str(ANALYSIS / "diagnose_spatial_counterfactuals.py")],
        "5. SPATIAL COUNTERFACTUAL SWEEP (what drives the rule-based collapse)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
