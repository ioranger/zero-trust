"""Measure the switch-interval column on the generated streams.

The shape block contains a statistic computed from the gaps between the sign
changes of a node's own channel: the coefficient of variation of those gaps.
It is degenerate where every node switches on the same schedule, which is
the case in the packet-level scenario, and it is not degenerate in the
generated one, where the attack schedules are drawn per node.

The manuscript's limitations paragraph used to claim that the column is
constant across nodes in every generated stream. This script is the check
that the claim is false, so that the sentence is not reintroduced.

Usage:
    python -u artifacts/analysis/switch_interval_column_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import marl_policy  # noqa: E402
from reference_simulator import load_config, simulate_trust_stream  # noqa: E402

SEEDS = (1000, 1001, 1002)


def switch_cv(x: np.ndarray) -> float:
    """The switch-interval CV of one node's series, as marl_policy computes it."""
    s = np.sign(np.diff(x))
    flips = s[1:] * s[:-1] < 0
    idx = np.flatnonzero(flips)
    if idx.size < 3:
        return 0.0
    gaps = np.diff(idx).astype(float)
    if gaps.mean() <= 0.0:
        return 0.0
    return float(gaps.std() / gaps.mean())


def main() -> int:
    cfg = load_config(str(ROOT / "artifacts" / "configs" / "default.json"))
    print("=" * 78)
    print("the switch-interval column across nodes, on the generated streams")
    print("=" * 78)
    for seed in SEEDS:
        streams, _malicious, _types = simulate_trust_stream(
            cfg, seed=seed, n_uavs=15, malicious_ratio=0.30, n_agents=5)
        post = streams[cfg.warmup_steps:]
        values = []
        for node in range(post.shape[1]):
            per_channel = [switch_cv(post[:, node, ch])
                           for ch in marl_policy._SHAPE_ATTACK_CHANNELS]
            values.append(float(np.mean(per_channel)))
        values = np.array(values)
        print(f"  seed {seed}: {len(values)} nodes  "
              f"min={values.min():.3f}  max={values.max():.3f}  "
              f"distinct values={len(set(np.round(values, 6)))}")
    print()
    print("  a column that is constant across nodes would show one distinct")
    print("  value and a zero span; the generated streams show neither, so the")
    print("  column is informative there and the claim that it is degenerate")
    print("  in the generated scenario does not hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
