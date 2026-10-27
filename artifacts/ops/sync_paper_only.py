"""Copy the manuscript and the analysis files from the development tree into
the git worktree, without touching artifacts/outputs.

The staging script copies artifacts/outputs as well, and the leave-one-factor
arms are being built in the worktree at the moment, so a full staging would
overwrite the files the running job is producing. This copies only what the
commit needs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

DEV = Path(r"F:\zero trust\zero-trust")
GIT = Path(r"F:\zero trust\gitwork")

FILES = [
    "paper/template.tex",
    "paper/template.pdf",
    "artifacts/scripts/marl_policy.py",
    "artifacts/scripts/train_marl_pytorch.py",
    "artifacts/analysis/factor_ablation_report.py",
    "artifacts/analysis/column_diagnostic_report.py",
    "artifacts/analysis/make_factor_ablation_configs.py",
    "artifacts/analysis/run_factor_ablation.ps1",
    "artifacts/analysis/verify_new_tables.py",
    "artifacts/analysis/paper_consistency_check.py",
    "artifacts/analysis/README.md",
]

ARMS = ["published_recheck", "drop_T1", "drop_T2", "drop_T3", "drop_T4", "drop_T5", "spatial_recheck", "spatial_drop_T1", "spatial_drop_T2", "spatial_drop_T3", "spatial_drop_T4", "spatial_drop_T5", "col_nogaps", "col_noT2direct"]


def main() -> int:
    for rel in FILES:
        src = DEV / rel
        dst = GIT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"copied {rel}")

    for png in sorted((DEV / "artifacts" / "analysis" / "paper_pages").glob("*.png")):
        dst = GIT / "artifacts" / "analysis" / "paper_pages" / png.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(png, dst)
    print("copied the page snapshots")

    for cfg in sorted((DEV / "artifacts" / "configs").glob("*factor_ablation*.json")):
        shutil.copy2(cfg, GIT / "artifacts" / "configs" / cfg.name)
    print("copied the ablation configurations")

    for arm in ARMS:
        src = DEV / "artifacts" / "analysis" / "runs" / arm
        dst = GIT / "artifacts" / "analysis" / "runs" / arm
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    print("copied the six published-scenario arms")

    print()
    print("artifacts/outputs was not touched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
