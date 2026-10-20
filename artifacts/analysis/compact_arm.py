"""Extract the four files the analysis scripts actually read from a run
snapshot into artifacts/analysis/runs/<arm>/, so the evidence is committed
without committing the 44 MB of regenerable intermediates.

Per arm:
    logs/per_seed_metrics.csv
    logs/per_seed_attack_type_metrics.csv
    logs/marl_policy.json
    tables/baseline_comparison.csv

Usage:
    python -u artifacts/analysis/compact_arm.py <snapshot_dir> [<snapshot_dir> ...]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
OUT_ROOT = ROOT / "artifacts" / "analysis" / "runs"

FILES = [
    ("logs", "per_seed_metrics.csv"),
    ("logs", "per_seed_attack_type_metrics.csv"),
    ("logs", "marl_policy.json"),
    ("tables", "baseline_comparison.csv"),
]


def compact(snapshot: Path) -> int:
    arm = snapshot.name
    dst_root = OUT_ROOT / arm
    missing = []
    for sub, name in FILES:
        src = snapshot / sub / name
        if not src.exists():
            missing.append(f"{sub}/{name}")
            continue
        dst = dst_root / sub / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    total = sum(p.stat().st_size for p in dst_root.rglob("*") if p.is_file())
    if missing:
        print(f"[{arm}] MISSING: {', '.join(missing)}")
    print(f"[{arm}] -> {dst_root}  ({total/1024/1024:.2f} MB)")
    return 1 if missing else 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rc = 0
    for arg in sys.argv[1:]:
        rc |= compact(Path(arg))
    return rc


if __name__ == "__main__":
    sys.exit(main())
