"""Is the rule-based collapse in the spatial scenario a threshold-transfer
failure or an information failure?

In the telemetry-forging scenario the five rule-based methods score around
40% accuracy with a benign specificity near 20-30%. That number alone cannot
be read as "the rule baselines cannot see this attack", because their
thresholds are fixed constants and their scores are built around the
generator's absolute channel-reference level (the five rule adapters embed
the reference profile 0.80 / 0.76 / 0.72 / 0.80 / 0.75 directly), while the
spatial scenario shifts that level (the `reference_shift` that keeps the field
clipping symmetric).

This script separates the two explanations for each rule-based method:

  * fixed threshold    -- the number that appears in the tables.
  * AUC                -- threshold-free ranking quality. If the AUC is high,
                           the score still separates benign from malicious and
                           only the operating point is wrong.
  * best-F1            -- the F1 reachable when the operating point is
                           recalibrated on the same seed. It is the ceiling for
                           any method that produces that score.

All five adapters return a trust value where LOW means malicious.

    python -u artifacts/analysis/diagnose_rule_threshold_transfer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(r"F:\zero trust\zero-trust\artifacts\scripts")
sys.path.insert(0, str(SCRIPTS))

from baseline_reimplementations import (  # noqa: E402
    ahp_entropy, fuba, galtrust, gdm_dtm, mfa)
from reference_simulator import (  # noqa: E402
    BaselineConfig, load_config, simulate_trust_stream)

ROOT = Path(r"F:\zero trust\zero-trust")
CONFIG = ROOT / "artifacts/configs/spatial_position_nofeat.json"
SEEDS = [1000, 1001, 1002, 1003, 1004]
METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]


def auc_low_is_malicious(trust: np.ndarray, malicious: np.ndarray) -> float:
    """Mann-Whitney AUC where LOW trust means malicious.

    u_pos counts the (malicious, benign) pairs in which the malicious node has
    the lower trust, i.e. the hits. The AUC is therefore 1 - u_pos/(n_pos*n_neg),
    not u_pos/(n_pos*n_neg): a perfect detector has every malicious node below
    every benign node, which gives u_pos = 0 and an AUC of 1.
    """
    n = len(trust)
    order = np.argsort(trust, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    ranks[order] = np.arange(1, n + 1)
    # average ranks over ties
    vals = trust[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[j + 1] == vals[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    n_pos = int(malicious.sum())
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    u_pos = ranks[malicious].sum() - n_pos * (n_pos + 1) / 2.0
    return float(1.0 - u_pos / (n_pos * n_neg))


def best_f1(trust: np.ndarray, malicious: np.ndarray) -> float:
    """Largest F1 reachable by moving the operating point on this seed."""
    best = 0.0
    cand = np.unique(np.quantile(trust, np.linspace(0.005, 0.995, 199)))
    for t in cand:
        pred = trust < t
        tp = int(np.sum(pred & malicious))
        fp = int(np.sum(pred & ~malicious))
        fn = int(np.sum(~pred & malicious))
        if tp == 0:
            continue
        prec = tp / (tp + fp)
        rec = tp / (tp + fn)
        best = max(best, 2 * prec * rec / (prec + rec))
    return best


def main() -> int:
    cfg = load_config(str(CONFIG))
    thr = cfg.raw["classification"]
    bcfg = BaselineConfig(
        mfa_threshold=float(thr["mfa_threshold"]),
        fuba_threshold=float(thr["fuba_threshold"]),
        galtrust_threshold=float(thr["galtrust_threshold"]),
        gdm_dtm_threshold=float(thr["gdm_dtm_threshold"]),
        ahp_entropy_threshold=float(thr.get("ahp_entropy_threshold", 0.62)),
        ahp_entropy_lambda=float(thr.get("ahp_entropy_lambda", 0.5)),
    )
    n = int(cfg.raw["network"]["default_uavs"])
    ratio = float(cfg.raw["experiments"]["main_ratio"])

    acc: dict[str, dict[str, list]] = {
        m: {"fixed": [], "auc": [], "best": [], "benign": [], "pos": []}
        for m in METHODS}

    for seed in SEEDS:
        streams, malicious, types = simulate_trust_stream(
            cfg, seed=seed, n_uavs=n, malicious_ratio=ratio,
            n_agents=int(cfg.raw["network"]["default_thinker_agents"]))
        noise = np.zeros(n)
        is_pos = types == "position-inconsistent"
        for m in METHODS:
            if m == "MFA":
                pred, trust = mfa(streams, cfg.warmup_steps, bcfg, noise)
            elif m == "FUBA":
                pred, trust = fuba(streams, cfg.warmup_steps, bcfg, noise)
            elif m == "GALTrust":
                pred, trust = galtrust(streams, cfg.warmup_steps, bcfg, noise)
            elif m == "GDM-DTM":
                pred, trust = gdm_dtm(streams, cfg.warmup_steps, bcfg, noise)
            else:
                pred, trust = ahp_entropy(streams, cfg.warmup_steps, bcfg, noise)
            acc[m]["fixed"].append(float(np.mean(pred == malicious)))
            acc[m]["auc"].append(auc_low_is_malicious(trust, malicious))
            acc[m]["best"].append(best_f1(trust, malicious))
            acc[m]["benign"].append(float(np.mean(~pred[~malicious])))
            if is_pos.any():
                acc[m]["pos"].append(float(np.mean(pred[is_pos])))

    print("=" * 108)
    print("RULE-BASED THRESHOLD TRANSFER -- spatial scenario, "
          f"{len(SEEDS)} seeds, n={n}, ratio={ratio}")
    print("=" * 108)
    print(f"{'method':<13}{'accuracy':>10}{'benign spec':>13}{'AUC':>8}"
          f"{'best F1':>10}{'pos-incons.':>13}")
    print("-" * 108)
    for m in METHODS:
        d = acc[m]
        pos = 100 * np.mean(d["pos"]) if d["pos"] else float("nan")
        print(f"{m:<13}{100*np.mean(d['fixed']):>10.1f}"
              f"{100*np.mean(d['benign']):>13.1f}"
              f"{np.mean(d['auc']):>8.3f}"
              f"{100*np.mean(d['best']):>10.1f}{pos:>13.1f}")
    print("-" * 108)
    print("accuracy / benign spec / pos-incons. use the fixed thresholds from the config.")
    print("AUC is threshold-free ranking quality; best F1 is the ceiling after")
    print("recalibrating the operating point on the same data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
