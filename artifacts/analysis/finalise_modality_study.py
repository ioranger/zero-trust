"""Finalise the modality-complementarity study.

Compacts every arm's logs into artifacts/analysis/runs/<arm>/ and then builds

  1. the three-row modality ladder (13 / 18 / 23 features) over the four
     attack classes, and
  2. the fusion-mechanism ablation, which contrasts the same 23-dimensional
     vector fed to three different fusion mechanisms.

    python -u artifacts/analysis/finalise_modality_study.py
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


def run(cmd: list[str]) -> int:
    print("\n$ " + " ".join(str(c) for c in cmd))
    print("-" * 100)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    if rc != 0:
        print(f"!! exit code {rc}")
    return rc


def main() -> int:
    missing = [lab for lab, arm in ARMS.items()
               if not (RUNS / arm / "logs" / "per_seed_attack_type_metrics.csv").exists()]
    if missing:
        print(f"!! missing arms: {', '.join(missing)}")
        print("   run the arm drivers first; this script only finalises what exists.")
        return 2

    # 1. the modality ladder
    ladder_args = []
    for lab, arm in ARMS.items():
        if lab == "23d fusion ablation":
            continue
        ladder_args += ["--arm", f"{lab}={RUNS / arm / 'logs' / 'per_seed_attack_type_metrics.csv'}"]
    run([PY, "-u", str(ANALYSIS / "modality_complementarity.py"),
         *ladder_args,
         "--compare", "23d marginal+shape+spatial", "18d marginal+shape",
         "--out", str(ANALYSIS / "modality_ladder.txt")])

    # 2. the fusion-mechanism ablation: identical vector, three mechanisms
    fusion_args = []
    for lab, arm in ARMS.items():
        if lab == "13d marginal":
            continue
        fusion_args += ["--arm", f"{lab}={RUNS / arm / 'logs' / 'per_seed_attack_type_metrics.csv'}"]
    run([PY, "-u", str(ANALYSIS / "modality_complementarity.py"),
         *fusion_args,
         "--compare", "23d fusion ablation", "23d marginal+shape+spatial",
         "--out", str(ANALYSIS / "fusion_ablation.txt")])

    # 3. the published-table reproduction check
    run([PY, "-u", str(ANALYSIS / "compare_snapshot_to_published.py"),
         str(ROOT / "artifacts" / "runs" / "paper_18dim_recheck")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
