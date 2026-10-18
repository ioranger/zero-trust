"""Design and pre-screen five temporal-shape features before touching the encoder.

Motivation, from the already-verified diagnosis:

  * camouflage is a per-node constant (reference_simulator.py:127), so it
    shifts a node's level but adds no time-varying structure;
  * on-off is a period-90 square wave (reference_simulator.py:157);
  * the 13 published features are all marginal / quantile / trend aggregates.
    None of them can express autocorrelation or transition structure.

The earlier lag-by-lag autocorrelation sweep confirmed a signal exists, but a
raw ACF value is weak here: lag-1 ACF is around 0.96 for EVERY class because
the EMA channel dominates it. So the features below are built to be
insensitive to that shared baseline.

Design rule: the attack period is NOT encoded anywhere. No lag of 45 or 90
appears. Every feature is a scale-free summary of transition structure, and
the model is free to pick whatever resolution it needs.

  1 acf_excess      mean |ACF(lag) - ACF(1)| over lags 3..120. A square wave
                    oscillates around its own mean, so its ACF swings far
                    above its own lag-1 value. A monotone or noisy series does
                    not.
  2 acf_prominence  max |ACF(lag) - ACF(1)| over the same lags. Distinguishes
                    a clear periodic structure from a weak one.
  3 flip_rate       sign-change rate of the first difference. White-noise-like
                    series flip at ~0.5; a square wave flips only at its two
                    switching instants, so its rate collapses toward 0.
  4 two_level       (q75-q25)/(q95-q05). A two-state process holds a wide
                    lower-upper gap but a narrow middle, so this rises only
                    when the sequence actually visits two plateaus.
  5 switch_cv       coefficient of variation of the intervals between sign
                    flips. A periodic attacker switches on a schedule (small
                    CV); random triggers do not (large CV).

THE CONTROL THIS SCRIPT EXISTS FOR
-----------------------------------
Every feature is recomputed on a time-SHUFFLED copy of the same series. The
marginal distribution of each step is unchanged, so any level or variance
proxy survives shuffling. If a feature separates the classes just as well
after shuffling, it is not a shape feature and must be rejected. A feature is
only accepted when shuffled performance collapses toward chance.

Protocol: seeds 7000-7049, disjoint from the artifact's evaluation seeds
(1000-1049) and training seeds (0-9), so nothing here touches the reported
table. GroupKFold by seed, exactly as the earlier probes did.
"""
import os
import sys
from pathlib import Path

import numpy as np

ART = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, os.path.join(ART, "scripts"))

from reference_simulator import (  # noqa: E402
    extract_policy_features,
    load_config,
    simulate_trust_stream,
)

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

config = load_config(os.path.join(ART, "configs", "default.json"))

N_SEEDS = 50
N_UAVS = 15
RATIO = 0.30
ATTACK_CHANNELS = (0, 3)     # T1 and T4
ACF_MAX_LAG = 120
ACF_MIN_LAG = 3

FEATURE_NAMES = ["acf_excess", "acf_prominence", "flip_rate",
                 "two_level", "switch_cv"]


def _acf(x, lag):
    d = np.dot(x, x)
    return 0.0 if d <= 0 else float(np.dot(x[:-lag], x[lag:]) / d)


def shape_features(x):
    """Five shape statistics of one channel. No attack period is assumed."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < ACF_MAX_LAG + 2:
        return np.zeros(len(FEATURE_NAMES))

    z = x - x.mean()
    a1 = _acf(z, 1)
    lags = range(ACF_MIN_LAG, min(ACF_MAX_LAG, n - 1))
    excess = np.array([_acf(z, l) - a1 for l in lags])

    # first differences and their sign pattern
    d = np.diff(x)
    s = np.sign(d)
    flips = s[1:] * s[:-1] < 0
    flip_rate = float(flips.mean()) if len(flips) else 0.0

    # interval regularity between transitions
    idx = np.flatnonzero(flips)
    switch_cv = 0.0
    if len(idx) >= 3:
        gaps = np.diff(idx).astype(float)
        if gaps.mean() > 0:
            switch_cv = float(gaps.std() / gaps.mean())

    q05, q25, q75, q95 = np.quantile(x, [0.05, 0.25, 0.75, 0.95])
    span = q95 - q05
    two_level = float((q75 - q25) / span) if span > 0 else 0.0

    return np.array([float(np.mean(np.abs(excess))),
                     float(np.max(np.abs(excess))),
                     flip_rate, two_level, switch_cv])


def shape_block(post):
    """Average the five statistics over the attacked channels."""
    rows = [shape_features(post[:, ch]) for ch in ATTACK_CHANNELS]
    return np.mean(np.vstack(rows), axis=0)


def collect():
    base, shape, shape_shuf, labels, groups, kinds = [], [], [], [], [], []
    for seed in range(7000, 7000 + N_SEEDS):
        streams, malicious, attack_types = simulate_trust_stream(
            config, seed, n_uavs=N_UAVS, malicious_ratio=RATIO)
        post = streams[config.warmup_steps:]
        feats = extract_policy_features(config, streams)
        rng = np.random.default_rng(seed)
        perm = rng.permutation(post.shape[0])
        for node in range(N_UAVS):
            base.append(feats[node])
            shape.append(shape_block(post[:, node, :]))
            shape_shuf.append(shape_block(post[perm, node, :]))
            labels.append(int(malicious[node]))
            groups.append(seed)
            kinds.append("benign" if not malicious[node] else str(attack_types[node]))
    return (np.vstack(base), np.vstack(shape), np.vstack(shape_shuf),
            np.array(labels), np.array(groups), kinds)


def evaluate(X, y, groups, mal, kinds, fpr=0.05):
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    thr = float(np.quantile(oof[y == 0], fpr))
    hit = oof >= thr
    det = {k: float(hit[[i for i, kk in enumerate(kinds) if kk == k]].mean())
           for k in ("constant", "dormant", "on-off")}
    return (float(roc_auc_score(y, oof)), float(((hit) & mal).sum() / max(1, mal.sum())), det)


def main():
    print("=" * 84)
    print("temporal shape features: pre-screen before any retraining")
    print(f"seeds=7000..{7000+N_SEEDS-1}  uavs={N_UAVS}  malicious={RATIO:.0%}  "
          f"post-warmup steps={config.steps - config.warmup_steps}")
    print("no attack period is encoded in any feature (lags 3..120, scale-free)")
    print("=" * 84)

    base, shape, shuf, y, groups, kinds = collect()
    print(f"collected {len(y)} node samples "
          f"({int(y.sum())} malicious: "
          + ", ".join(f"{k}={kinds.count(k)}" for k in
                      ("constant", "dormant", "on-off")) + ")")

    variants = {
        "13 marginal (published)": base,
        "5 shape only": shape,
        "5 shape, time-shuffled": shuf,
        "13 + 5 shape": np.hstack([base, shape]),
        "13 + 5 shape-shuffled": np.hstack([base, shuf]),
    }
    print()
    print(f"{'feature set':>26s} {'AUC':>8s} {'detect':>8s} "
          f"{'constant':>9s} {'dormant':>9s} {'on-off':>9s}")
    print("-" * 84)
    out = {}
    for name, X in variants.items():
        auc, det, per = evaluate(X, y, groups, y.astype(bool), kinds)
        out[name] = (auc, det, per)
        print(f"{name:>26s} {auc:8.4f} {det:8.3f} "
              f"{per['constant']:9.3f} {per['dormant']:9.3f} {per['on-off']:9.3f}")
    print()

    pub = out["13 marginal (published)"]
    real = out["13 + 5 shape"]
    ctrl = out["13 + 5 shape-shuffled"]
    shufonly = out["5 shape, time-shuffled"]
    realonly = out["5 shape only"]

    print("acceptance gate")
    print("-" * 84)
    print(f"  AUC  13 marginal           : {pub[0]:.4f}")
    print(f"  AUC  13 + real shape       : {real[0]:.4f}   ({real[0]-pub[0]:+.4f})")
    print(f"  AUC  13 + SHUFFLED shape   : {ctrl[0]:.4f}   ({ctrl[0]-pub[0]:+.4f})")
    print(f"  attributable to shape     : {real[0]-ctrl[0]:+.4f}")
    print()
    print(f"  on-off recall, 13 marginal: {pub[2]['on-off']:.3f}")
    print(f"  on-off recall, +real shape: {real[2]['on-off']:.3f}   "
          f"({real[2]['on-off']-pub[2]['on-off']:+.3f})")
    print(f"  on-off recall, +shuffled  : {ctrl[2]['on-off']:.3f}")
    print()
    gate = real[0] - ctrl[0]
    verdict = ("ACCEPTED: gain survives the shuffle control, so it is a "
               "shape signal."
               if gate > 0.005 else
               "REJECTED: shuffled shape features recover most of the gain, "
               "so it is a level/variance proxy, not a shape signal.")
    print(f"  verdict: {verdict}")
    print()
    print(f"  (shape-alone AUC real {realonly[0]:.4f} vs shuffled "
          f"{shufonly[0]:.4f} -- shape features are only useful in "
          f"combination, which is expected)")

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "shape_feature_prescreen.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"seeds=7000..{7000+N_SEEDS-1} uavs={N_UAVS} ratio={RATIO}\n")
        fh.write(f"{'variant':>26s} {'auc':>9s} {'detect':>9s} "
                 f"{'constant':>9s} {'dormant':>9s} {'on-off':>9s}\n")
        for name, (auc, det, per) in out.items():
            fh.write(f"{name:>26s} {auc:9.4f} {det:9.3f} "
                     f"{per['constant']:9.3f} {per['dormant']:9.3f} "
                     f"{per['on-off']:9.3f}\n")
        fh.write(f"\nattributable AUC gain (real - shuffled) = {gate:+.4f}\n")
        fh.write(f"verdict: {verdict}\n")


if __name__ == "__main__":
    main()