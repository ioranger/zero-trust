"""Run the channel-focused leave-one-dimension-out study end to end.

Each arm is trained and evaluated in its own working tree, because the
checkpoint path of the training script is fixed relative to the root of the
configuration and every arm would otherwise overwrite the checkpoint of the
previous one. The outputs of an arm are copied to artifacts/analysis/runs/
before the next arm starts.

Usage:
    python -u artifacts/analysis/run_channel_profile_ablation.py \
        --work-root D:\\tmp\\zt_channel_profile
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "artifacts" / "analysis" / "runs"
SCRIPTS = ROOT / "artifacts" / "scripts"
CONFIGS = ROOT / "artifacts" / "configs"

PREFIX = "channel_profile"
ARMS = [PREFIX] + [f"{PREFIX}_drop_{f}" for f in ("T1", "T2", "T3", "T4", "T5")]

# The four files an analysis script actually reads, and the only ones kept
# for an arm. The per-step trust stream is 11 MB per arm and regenerable.
KEEP = [
    ("logs", "marl_policy.json"),
    ("logs", "per_seed_attack_type_metrics.csv"),
    ("logs", "per_seed_ablation.csv"),
    ("logs", "per_seed_metrics.csv"),
    ("tables", "baseline_comparison.csv"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the channel-profile leave-one-dimension-out arms.")
    parser.add_argument("--work-root", required=True,
                        help="scratch directory for the per-arm working trees")
    parser.add_argument("--arms", nargs="*", default=ARMS,
                        help="arms to run (default: every arm)")
    parser.add_argument("--device", default="cpu", choices=["auto", "cpu", "mps"])
    return parser.parse_args()


def run(cmd: list[str], cwd: Path) -> None:
    print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def prepare(arm: str, work_root: Path) -> Path:
    work = work_root / arm
    (work / "artifacts" / "configs").mkdir(parents=True, exist_ok=True)
    (work / "artifacts" / "scripts").mkdir(parents=True, exist_ok=True)
    for script in SCRIPTS.glob("*.py"):
        shutil.copy2(script, work / "artifacts" / "scripts" / script.name)
    shutil.copy2(CONFIGS / f"{arm}.json", work / "artifacts" / "configs" / f"{arm}.json")
    return work


def main() -> int:
    args = parse_args()
    work_root = Path(args.work_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)

    for arm in args.arms:
        print(f"=== {arm} ===", flush=True)
        work = prepare(arm, work_root)
        cfg = work / "artifacts" / "configs" / f"{arm}.json"
        started = time.time()
        run([sys.executable, "-u", str(work / "artifacts" / "scripts" / "train_marl_pytorch.py"),
             "--config", str(cfg), "--device", args.device], work)
        run([sys.executable, "-u", str(work / "artifacts" / "scripts" / "run_reference_experiment.py"),
             "--config", str(cfg)], work)
        run([sys.executable, "-u", str(work / "artifacts" / "scripts" / "summarize_results.py"),
             "--config", str(cfg)], work)
        dest = RUNS / arm
        if dest.exists():
            shutil.rmtree(dest)
        for sub, name in KEEP:
            src = work / "artifacts" / "outputs" / sub / name
            if not src.exists():
                raise FileNotFoundError(src)
            (dest / sub).mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / sub / name)
        print(f"=== {arm} done in {time.time() - started:.0f} s -> {dest} ===",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
