"""Saturation sweep: what does stronger camouflage do to the benchmark?

The published table cannot separate the proposed model from its feature-matched
control because every learned method reaches about 97% on it. The diagnosis in
the manuscript is that the training split is perfectly separable, so the
classifier is not the binding constraint and the aggregate metric compresses
the method classes.

The camouflage mixture is the knob that changes this. A malicious node's attack
profile is mixed with the benign reference by a per-node factor drawn from a
beta distribution; moving the two beta parameters towards each other pushes
that mixture towards a uniform factor, which flattens the attack profile
towards the benign reference and removes the level separation the marginal
summaries depend on, while leaving the shape of the attack intact.

This sweep measures, per camouflage level and on held-out seeds:

  risk separability   how separable the malicious label is from the 18
                      features. At 1.000 the benchmark is saturated and no
                      method can be separated from any other.
  modality (13)       how recoverable the attack-modality label is from the
                      marginal block alone. This is the quantity that decides
                      whether an auxiliary modality head has anything new to
                      teach: while it is near 1.0 the head can only re-encode
                      what the risk head already receives.
  modality (18)       the same from the marginal plus shape block.

    python -u artifacts/analysis/saturation_sweep.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
from marl_policy import extract_marl_policy_features  # noqa: E402

MODALITY = ("benign", "constant", "dormant", "on-off")
LEVELS = [
    ("published  beta(2.7, 1.8)", 2.7, 1.8),
    ("beta(2.2, 2.2)", 2.2, 2.2),
    ("beta(1.8, 1.8)", 1.8, 1.8),
    ("beta(1.5, 1.5)", 1.5, 1.5),
    ("beta(1.2, 1.2)", 1.2, 1.2),
    ("beta(1.0, 1.0)", 1.0, 1.0),
]


def build(cfg, seeds):
    X, Y, R = [], [], []
    n = int(cfg.raw["network"]["default_uavs"])
    agents = int(cfg.raw["network"]["default_thinker_agents"])
    for s in seeds:
        streams, malicious, atk = rs.simulate_trust_stream(
            cfg, seed=s, n_uavs=n, malicious_ratio=0.30, n_agents=agents)
        feats, _ = extract_marl_policy_features(
            cfg, streams, agents, use_shape=True, spatial_adjacency=None)
        X.append(feats)
        Y.append(np.array([MODALITY.index(str(a).strip().lower()) for a in atk]))
        R.append(malicious.astype(np.int64))
    return np.vstack(X), np.concatenate(Y), np.concatenate(R)


def fit_probe(Xa, Xb, ya, yb, n_out, hidden=32, seed=0):
    """Small classifier; returns (accuracy, per-class recall dict)."""
    import torch
    from torch import nn
    torch.manual_seed(seed)
    mu, sd = Xa.mean(axis=0), Xa.std(axis=0) + 1e-8
    A = torch.tensor((Xa - mu) / sd, dtype=torch.float32)
    B = torch.tensor((Xb - mu) / sd, dtype=torch.float32)
    ta = torch.tensor(ya, dtype=torch.long)
    tb = torch.tensor(yb, dtype=torch.long)
    net = nn.Sequential(nn.Linear(A.shape[1], hidden), nn.ReLU(),
                         nn.Linear(hidden, n_out))
    opt = torch.optim.Adam(net.parameters(), lr=0.01, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss()
    for _ in range(400):
        opt.zero_grad()
        lossf(net(A), ta).backward()
        opt.step()
    with torch.no_grad():
        logits = net(B)
        if n_out == 2:
            pred = logits.argmax(dim=1).numpy()
        else:
            pred = logits.argmax(dim=1).numpy()
    acc = float((pred == yb).mean())
    per = {}
    for i in range(n_out):
        m = yb == i
        if m.any():
            per[i] = float((pred[m] == i).mean())
    return acc, per


def main() -> int:
    base_raw = json.loads(
        (ROOT / "artifacts" / "configs" / "default.json").read_text(
            encoding="utf-8-sig"))

    print("=" * 104)
    print("SATURATION SWEEP -- camouflage strength against separability and "
          "modality recoverability")
    print("=" * 104)
    print(f"{'camouflage level':<28}{'risk sep.':>11}{'risk FPR':>10}"
          f"{'mod(13)':>10}{'mod(18)':>10}   marginal per-class recall")
    print("-" * 104)

    with tempfile.TemporaryDirectory() as tmp:
        for label, a, b in LEVELS:
            raw = copy.deepcopy(base_raw)
            raw.setdefault("generator", {})["camouflage_beta_a"] = a
            raw["generator"]["camouflage_beta_b"] = b
            p = Path(tmp) / "cfg.json"
            p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            cfg = rs.load_config(str(p))

            Xtr, Ytr, Rtr = build(cfg, range(100, 148))
            Xte, Yte, Rte = build(cfg, range(148, 160))

            r_acc, r_per = fit_probe(Xtr, Xte, Rtr, Rte, 2)
            fpr = r_per.get(0, float("nan"))
            m13, _ = fit_probe(Xtr[:, :13], Xte[:, :13], Ytr, Yte, 4)
            m18, m18_per = fit_probe(Xtr, Xte, Ytr, Yte, 4)
            ps = "  ".join(f"{MODALITY[i]}={v:.2f}" for i, v in m18_per.items())
            print(f"{label:<28}{r_acc * 100:>10.1f}%{fpr * 100:>9.1f}%"
                  f"{m13 * 100:>9.1f}%{m18 * 100:>9.1f}%   {ps}")

    print("-" * 104)
    print("risk sep.    held-out accuracy of a probe on the malicious label, "
          "18-dim features")
    print("risk FPR     its false-positive rate on benign nodes")
    print("mod(13)      attack-modality accuracy from the marginal block alone")
    print("mod(18)      attack-modality accuracy from the marginal + shape block")
    print()
    print("A benchmark whose risk separability has fallen below 1.000 is no")
    print("longer saturated, and a marginal-block modality accuracy well below")
    print("1.000 is the regime in which an auxiliary modality head carries")
    print("information the risk head does not already receive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
