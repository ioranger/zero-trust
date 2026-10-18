"""Duty-cycle sweep: how the blind spot depends on how intermittent the attacker is.

The claim under test is not "our detector is better". It is that an aggregator
which summarises each channel over a fixed window is blind to a node whose
adversarial activity is intermittent, and that this blindness should worsen as
the on-off duty cycle falls, while a block that encodes sequence order should
degrade more gracefully.

Design notes that matter for reading the result:

* Same seed, same node assignment, same camouflage, same observation noise at
  every duty. `onoff_duty` is excluded from `stable_rng` precisely so that the
  only thing varying across a row is the phase length. This is a paired design.
* n_uavs = 30 rather than 15. At 15 UAVs and a 30% ratio only ONE node per
  seed is on-off, so a per-seed rate can only be 0 or 1 and the reported
  standard deviation is binomial noise rather than a property of any method.
  At 30 UAVs there are three on-off nodes per seed.
* Detection is POOLED over on-off nodes across all seeds, which removes the
  per-seed binary variance entirely. A pooled binomial interval is reported.
* The trained checkpoints are the ones the manuscript reports. They were
  trained at the default 50% duty, so a rise at low duty is not memorisation
  of the training duty; a fall at low duty is not a train/test mismatch either,
  since the on-off period and phase are the only thing changing.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

import numpy as np

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / "scripts"))

from reference_simulator import (  # noqa: E402
    load_config,
    method_predictions,
    simulate_trust_stream,
)

config = load_config(ART / "configs" / "default.json")
policy = json.loads(
    (ART / "outputs" / "logs" / "marl_policy.json").read_text(encoding="utf-8"))
policy["learned_baselines"] = json.loads(
    (ART / "outputs" / "logs" / "learned_baselines.json").read_text(encoding="utf-8"))

SEEDS = list(range(1000, 1050))
N_UAVS = 30
RATIO = 0.30
N_AGENTS = int(config.raw["network"]["default_thinker_agents"])
DUTIES = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
METHODS = ["S-TIM", "MLP-Trust", "LR-Trust", "GDM-DTM"]


def wilson(k, n, z=1.96):
    """Wilson score interval; behaves correctly at 0 and 1."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (100.0 * (c - h) / d, 100.0 * (c + h) / d)


def sweep(duty, method):
    hit = tot = 0
    benign_hit = benign_tot = 0
    for seed in SEEDS:
        streams, malicious, types = simulate_trust_stream(
            config, seed=seed, n_uavs=N_UAVS, malicious_ratio=RATIO,
            n_agents=N_AGENTS, onoff_duty=duty)
        pred, _ = method_predictions(config, streams, method, policy, seed,
                                     N_UAVS, RATIO, N_AGENTS)
        pred = np.asarray(pred).astype(bool)
        mask = np.array([str(t) == "on-off" for t in types]) & malicious
        if mask.any():
            hit += int(pred[mask].sum())
            tot += int(mask.sum())
        bm = ~malicious
        benign_hit += int((~pred[bm]).sum())
        benign_tot += int(bm.sum())
    return hit, tot, benign_hit, benign_tot


def main():
    print("=" * 96)
    print("duty-cycle sweep: on-off detection vs how intermittent the attack is")
    print(f"seeds={SEEDS[0]}..{SEEDS[-1]} ({len(SEEDS)})  n_uavs={N_UAVS}  "
          f"malicious={RATIO:.0%}  period=90 steps")
    print("paired: identical node assignment, camouflage and noise at every duty")
    print("pooled over on-off nodes; Wilson 95% interval")
    print("=" * 96)

    results = {}
    for duty in DUTIES:
        for m in METHODS:
            results[(duty, m)] = sweep(duty, m)

    print()
    print("on--off detection rate (%), pooled")
    print("-" * 96)
    print(f"{'duty':>6s} " + "".join(f"{m:>22s}" for m in METHODS))
    for duty in DUTIES:
        row = f"{duty:6.2f} "
        for m in METHODS:
            h, t, _, _ = results[(duty, m)]
            lo, hi = wilson(h, t)
            row += f"{100.0 * h / max(1, t):9.1f} [{lo:4.0f},{hi:4.0f}]"
        print(row)

    print()
    print("absolute gap, shape-block learners minus rule aggregator (pp)")
    print("-" * 96)
    print(f"{'duty':>6s} {'S-TIM-GDM':>10s} {'MLP-GDM':>10s} {'LR-GDM':>10s}")
    for duty in DUTIES:
        vals = []
        for m in ("S-TIM", "MLP-Trust", "LR-Trust"):
            h, t, _, _ = results[(duty, m)]
            g, gt, _, _ = results[(duty, "GDM-DTM")]
            vals.append(100.0 * h / max(1, t) - 100.0 * g / max(1, gt))
        print(f"{duty:6.2f} {vals[0]:10.1f} {vals[1]:10.1f} {vals[2]:10.1f}")

    print()
    print("benign false-negative share (benign nodes NOT flagged), %")
    print("-" * 96)
    print(f"{'duty':>6s} " + "".join(f"{m:>16s}" for m in METHODS))
    for duty in DUTIES:
        row = f"{duty:6.2f} "
        for m in METHODS:
            _, _, bh, bt = results[(duty, m)]
            row += f"{100.0 * bh / max(1, bt):16.1f}"
        print(row)

    print()
    print("sample counts per row (on-off nodes pooled)")
    print("-" * 96)
    for duty in DUTIES:
        h, t, _, _ = results[(duty, "S-TIM")]
        print(f"  duty {duty:.2f}: {t} on-off nodes pooled, {h} detected")

    out = HERE / "duty_sweep.txt"
    with out.open("w", encoding="utf-8") as fh:
        fh.write(f"seeds={SEEDS[0]}..{SEEDS[-1]} n_uavs={N_UAVS} ratio={RATIO}\n")
        fh.write("on-off detection pooled (%)\n")
        fh.write("duty " + " ".join(METHODS) + "\n")
        for duty in DUTIES:
            fh.write(f"{duty:.2f} " + " ".join(
                f"{100.0 * results[(duty, m)][0] / max(1, results[(duty, m)][1]):.1f}"
                for m in METHODS) + "\n")


if __name__ == "__main__":
    main()