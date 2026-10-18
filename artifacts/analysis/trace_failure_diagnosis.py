"""Why do the learned methods fail on the converted packet trace?

The trace-driven check reports S-TIM and MLP-Trust detecting none of five
malicious nodes, while a logistic regression on the SAME 18 features detects
all five. That asymmetry is the clue: if the trace were simply outside the
feature support, a linear model on those features would fail too. It does not.

This script measures where the trace's malicious nodes actually sit in the
18-dimensional feature space that the models consume, relative to the benign
and malicious clouds the models were trained on.

For each feature it reports

  benign mu, sigma      the training distribution of benign nodes
  train-mal z           how far training malicious nodes sit, in benign sigmas
  trace-mal z           how far the trace's malicious nodes sit

If trace-mal z lands near zero, the trace's attackers are, feature by feature,
indistinguishable from benign in the trained space, and a saturated sigmoid has
no reason to cross the boundary. If instead the separation is large but the
network still fails, the failure is in the decision function rather than in the
features, which is a different and more fixable problem.
"""
import csv
import os
import sys
from pathlib import Path

import numpy as np

ART = Path(r"F:\zero trust\zero-trust\artifacts")
sys.path.insert(0, str(ART / "scripts"))

from reference_simulator import (  # noqa: E402
    extract_policy_features,
    load_config,
    simulate_trust_stream,
)
from marl_policy import extract_marl_policy_features  # noqa: E402

config = load_config(ART / "configs" / "default.json")
TRACE_CSV = ART / "outputs" / "logs" / "ns3_trust_streams.csv"
TRAIN_SEEDS = list(config.raw["train_seeds"])
N_UAVS = 15


def load_trace():
    """The trace CSV is long format: one row per (time, node) pair."""
    rows = list(csv.DictReader(TRACE_CSV.read_text(encoding="utf-8").splitlines()))
    n_nodes = N_UAVS
    if len(rows) % n_nodes:
        raise ValueError(f"{len(rows)} rows is not a multiple of {n_nodes}")
    n_steps = len(rows) // n_nodes

    stream = np.zeros((n_steps, n_nodes, 5))
    for c, ci in zip(("T1", "T2", "T3", "T4", "T5"), range(5)):
        stream[:, :, ci] = np.array([float(r[c]) for r in rows]).reshape(n_steps, n_nodes)
    mal = np.array([int(r["is_malicious"]) for r in rows], dtype=bool)
    atype = [r.get("attack_type", "benign") for r in rows]
    return stream, mal, atype


def train_clouds():
    X, y = [], []
    for ratio in config.raw["experiments"]["ratio_grid"]:
        for seed in TRAIN_SEEDS:
            st, mal, _ = simulate_trust_stream(
                config, seed=int(seed), n_uavs=N_UAVS,
                malicious_ratio=float(ratio),
                n_agents=int(config.raw["network"]["default_thinker_agents"]))
            f, _ = extract_marl_policy_features(config, st, 5)
            X.append(f)
            y.append(mal.astype(int))
    return np.vstack(X), np.concatenate(y)


def main():
    print("=" * 100)
    print("why the learned methods miss the converted packet trace")
    print("=" * 100)

    stream, tmal, ttype = load_trace()
    print(f"trace: {stream.shape[0]} steps x {stream.shape[1]} nodes, "
          f"malicious={int(tmal.sum())}, types={sorted(set(ttype))}")

    w = config.warmup_steps
    tpost = stream[w:]
    print(f"        post-warmup steps: {tpost.shape[0]}")

    print()
    print("per-channel distribution: simulator benign vs trace benign vs trace malicious")
    print("-" * 100)
    print(f"{'channel':>8s} {'sim benign mu':>14s} {'sd':>7s} "
          f"{'trace benign':>14s} {'trace mal':>11s} {'z(mal)':>8s}")
    for ci, name in enumerate(["T1", "T2", "T3", "T4", "T5"]):
        vals = []
        for seed in TRAIN_SEEDS[:12]:
            st, mal, _ = simulate_trust_stream(
                config, seed=int(seed), n_uavs=N_UAVS, malicious_ratio=0.30)
            vals.append(st[w:, ~mal, ci].ravel())
        sim_ben = np.concatenate(vals)
        mu, sd = sim_ben.mean(), sim_ben.std()
        tb = tpost[:, ~tmal, ci].ravel()
        tm = tpost[:, tmal, ci].ravel()
        print(f"{name:>8s} {mu:14.4f} {sd:7.4f} {tb.mean():14.4f} "
              f"{tm.mean():11.4f} {(tm.mean()-mu)/sd:8.2f}")

    print()
    print("18-dim feature space, standardised by the training benign cloud")
    print("-" * 100)
    Xtr, ytr = train_clouds()
    ben = Xtr[ytr == 0]
    mal = Xtr[ytr == 1]
    mu, sd = ben.mean(axis=0), ben.std(axis=0) + 1e-9

    ftrace, names = extract_marl_policy_features(config, stream, 5)
    ztrace = (ftrace[tmal] - mu) / sd
    ztr_mal = (mal - mu) / sd

    print(f"{'feature':>26s} {'train-mal z':>12s} {'trace-mal z':>12s}")
    for i, nm in enumerate(names):
        print(f"{nm:>26s} {ztr_mal[:, i].mean():12.2f} {ztrace[:, i].mean():12.2f}")

    print()
    print("summary")
    print("-" * 100)
    d_tr = np.sqrt((ztr_mal ** 2).mean(axis=0))
    d_te = np.sqrt((ztrace ** 2).mean(axis=0))
    print(f"  mean distance from benign centre, training malicious : {d_tr.mean():6.2f} sd")
    print(f"  mean distance from benign centre, trace malicious    : {d_te.mean():6.2f} sd")
    print()
    n_inside = int((np.abs(ztrace) < 2.0).sum())
    total = ztrace.size
    print(f"  trace-malicious feature cells within 2 sd of benign: "
          f"{n_inside}/{total} ({100.0*n_inside/total:.1f}%)")
    n_inside_tr = int((np.abs(ztr_mal) < 2.0).sum())
    print(f"  train-malicious feature cells within 2 sd of benign: "
          f"{n_inside_tr}/{ztr_mal.size} ({100.0*n_inside_tr/ztr_mal.size:.1f}%)")

    path = Path(r"F:\zero trust\realdata\trace_failure_diagnosis.txt")
    with path.open("w", encoding="utf-8") as fh:
        fh.write("trace steps=%d nodes=%d malicious=%d\n"
                 % (stream.shape[0], stream.shape[1], int(tmal.sum())))
        fh.write(f"mean |z| from benign: train-mal={d_tr.mean():.2f} "
                 f"trace-mal={d_te.mean():.2f}\n")
        fh.write(f"cells within 2sd: trace={n_inside}/{total} "
                 f"train={n_inside_tr}/{ztr_mal.size}\n")


if __name__ == "__main__":
    main()