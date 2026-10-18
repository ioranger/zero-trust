"""Probe-level evaluation: the regime where the benchmark still discriminates.

Why this exists. The trained networks reach roughly 99% accuracy on both the
training and the evaluation split, so the aggregate metric is saturated and
every learned method ties within noise. That saturation is a property of model
capacity meeting an easy aggregate metric, not evidence that the task has no
structure: a plain logistic probe on the same 18 features reaches only about
90%, and on the on--off attack class the 13 marginal features manage about 47%
against roughly 87% once the shape block is added.

So this script reports the regime where the question "does the representation
matter?" is actually answerable, using the artifact's own feature extractors
and the artifact's own evaluation seeds. It is not a replacement for the
network results; it is the measurement that separates representation from
classifier.

Four arms, identical folds, seed-disjoint:

  marginal            the 13 published features
  marginal+shape      the 13 plus the 5 temporal-shape statistics
  shape only          the 5 alone, to show they carry signal independently
  marginal+SHUFFLED   the 18 with the shape block computed on time-permuted
                      series, as the control for added dimensionality

Everything is scored at a 5% benign false-positive operating point, selected on
the benign scores' (1 - FPR) quantile.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

import numpy as np

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reference_simulator import (  # noqa: E402
    extract_policy_features,
    load_config,
    simulate_trust_stream,
)
from shape_feature_prescreen import FEATURE_NAMES, shape_block  # noqa: E402

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

config = load_config(ART / "configs" / "default.json")
N_UAVS = 30                      # three on-off nodes per seed, see duty_sweep
RATIO = 0.30
SEEDS = list(range(config.raw["evaluation_seeds"]["start"],
                   config.raw["evaluation_seeds"]["stop"]))
FPR = 0.05


def collect():
    marg, shape, shuf, y, groups, kinds = [], [], [], [], [], []
    for seed in SEEDS:
        streams, malicious, types = simulate_trust_stream(
            config, seed=seed, n_uavs=N_UAVS, malicious_ratio=RATIO)
        base = extract_policy_features(config, streams)
        post = streams[config.warmup_steps:]
        perm = np.random.default_rng(seed).permutation(post.shape[0])
        for node in range(streams.shape[1]):
            marg.append(base[node])
            shape.append(shape_block(post[:, node, :]))
            shuf.append(shape_block(post[perm, node, :]))
            y.append(int(malicious[node]))
            groups.append(seed)
            kinds.append(str(types[node]))
    return (np.vstack(marg), np.vstack(shape), np.vstack(shuf),
            np.array(y), np.array(groups), kinds)


def score(X, y, groups, kinds):
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    # Flag the top FPR fraction of BENIGN nodes. That threshold is the
    # (1 - FPR) quantile of the benign score distribution, not the FPR one.
    thr = float(np.quantile(oof[y == 0], 1.0 - FPR))
    pred = oof >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    per = {}
    for k in ("constant", "dormant", "on-off"):
        idx = [i for i, kk in enumerate(kinds) if kk == k]
        per[k] = 100.0 * pred[idx].mean() if idx else float("nan")
    return {
        "auc": float(roc_auc_score(y, oof)),
        "acc": 100.0 * (pred == y).mean(),
        "f1": 200.0 * prec * rec / max(1e-9, prec + rec),
        "benign_fpr": 100.0 * fp / max(1, int((y == 0).sum())),
        **per,
    }


def main():
    print("=" * 94)
    print("probe-level evaluation (logistic), seeds "
          f"{SEEDS[0]}..{SEEDS[-1]}, n_uavs={N_UAVS}, malicious={RATIO:.0%}")
    print(f"operating point: {FPR:.0%} benign FPR, seed-disjoint GroupKFold")
    print("=" * 94)

    marg, shape, shuf, y, groups, kinds = collect()
    print(f"node rows={len(y)}  malicious={int(y.sum())}  "
          f"(constant={kinds.count('constant')}, dormant={kinds.count('dormant')}, "
          f"on-off={kinds.count('on-off')})")
    print()

    arms = {
        "13 marginal": marg,
        "5 shape only": shape,
        "5 shape shuffled": shuf,
        "18 = 13 + 5 shape": np.hstack([marg, shape]),
        "18, shape shuffled": np.hstack([marg, shuf]),
    }
    res = {}
    print(f"{'arm':>20s} {'AUC':>7s} {'Acc':>7s} {'F1':>7s} {'bFPR':>6s} "
          f"{'constant':>9s} {'dormant':>8s} {'on-off':>8s}")
    print("-" * 94)
    for name, X in arms.items():
        r = score(X, y, groups, kinds)
        res[name] = r
        print(f"{name:>20s} {r['auc']:7.4f} {r['acc']:7.2f} {r['f1']:7.2f} "
              f"{r['benign_fpr']:6.2f} {r['constant']:9.1f} {r['dormant']:8.1f} "
              f"{r['on-off']:8.1f}")

    print()
    print("attribution")
    print("-" * 94)
    a, b = res["18 = 13 + 5 shape"], res["18, shape shuffled"]
    c = res["13 marginal"]
    print(f"  marginal alone                       on-off {c['on-off']:5.1f}%   AUC {c['auc']:.4f}")
    print(f"  + shape, time-shuffled (control)    on-off {b['on-off']:5.1f}%   AUC {b['auc']:.4f}")
    print(f"  + shape, real                       on-off {a['on-off']:5.1f}%   AUC {a['auc']:.4f}")
    print(f"  attributable to sequence order      on-off {a['on-off'] - b['on-off']:+5.1f} pp   "
          f"AUC {a['auc'] - b['auc']:+.4f}")
    print()
    print(f"  shape features used ALONE reach on-off "
          f"{res['5 shape only']['on-off']:.1f}% versus "
          f"{res['5 shape shuffled']['on-off']:.1f}% when time-shuffled, so the "
          f"signal is in the ordering")
    print()

    out = HERE / "probe_level.txt"
    with out.open("w", encoding="utf-8") as fh:
        fh.write(f"seeds={SEEDS[0]}..{SEEDS[-1]} n_uavs={N_UAVS} ratio={RATIO} "
                 f"op point={FPR} benign FPR\n")
        fh.write("shape features: " + ", ".join(FEATURE_NAMES) + "\n\n")
        for name, r in res.items():
            fh.write(f"{name:>20s} auc={r['auc']:.4f} acc={r['acc']:.2f} "
                     f"f1={r['f1']:.2f} constant={r['constant']:.1f} "
                     f"dormant={r['dormant']:.1f} onoff={r['on-off']:.1f}\n")


if __name__ == "__main__":
    main()