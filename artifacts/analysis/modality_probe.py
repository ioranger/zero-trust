"""Why does modality supervision change nothing?

The modality head reaches 98.3% validation accuracy once it is supervised, yet
no detection metric moves. The hypothesis: the modality label is not
recoverable from the RISK LABEL, but it IS recoverable from the FEATURES, so a
modality head can only re-encode what the risk head already sees.

This is a probe, not a training run. A small classifier is fitted on the
feature block to predict the attack-modality label, and the accuracy is
reported for the marginal block, the shape block and the full 18-dim vector.

  marginal only (13) -> if this is high, the modality target is already
                        available to the risk head and the auxiliary head
                        cannot add information
  shape only     (5) -> what the shape block contributes on its own
  full block    (18) -> the block S-TIM actually consumes

Run from the repository root:
    python -u artifacts/analysis/modality_probe.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
from marl_policy import extract_marl_policy_features  # noqa: E402

MODALITY = ("benign", "constant", "dormant", "on-off")


def build(cfg, seeds):
    X, Y = [], []
    n = int(cfg.raw["network"]["default_uavs"])
    agents = int(cfg.raw["network"]["default_thinker_agents"])
    for s in seeds:
        streams, malicious, atk = rs.simulate_trust_stream(
            cfg, seed=s, n_uavs=n, malicious_ratio=0.30, n_agents=agents)
        feats, names = extract_marl_policy_features(
            cfg, streams, agents, use_shape=True, spatial_adjacency=None)
        X.append(feats)
        Y.append(np.array([MODALITY.index(str(a).strip().lower()) for a in atk]))
    return np.vstack(X), np.concatenate(Y)


def fit_predict(Xa, Xb, Ya, Yb, hidden=32, seed=0):
    import torch
    from torch import nn
    torch.manual_seed(seed)
    mu, sd = Xa.mean(axis=0), Xa.std(axis=0) + 1e-8
    A = torch.tensor((Xa - mu) / sd, dtype=torch.float32)
    B = torch.tensor((Xb - mu) / sd, dtype=torch.float32)
    ya = torch.tensor(Ya, dtype=torch.long)
    yb = torch.tensor(Yb, dtype=torch.long)
    net = nn.Sequential(nn.Linear(A.shape[1], hidden), nn.ReLU(),
                         nn.Linear(hidden, 4))
    opt = torch.optim.Adam(net.parameters(), lr=0.01, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss()
    for _ in range(400):
        opt.zero_grad()
        lossf(net(A), ya).backward()
        opt.step()
    with torch.no_grad():
        pred = net(B).argmax(dim=1).numpy()
    return float((pred == Yb).mean()), {
        MODALITY[i]: float((pred[Yb == i] == i).mean())
        for i in range(4) if (Yb == i).any()}


def main():
    cfg = rs.load_config(str(ROOT / "artifacts" / "configs" / "default.json"))
    Xtr, Ytr = build(cfg, range(100, 148))
    Xte, Yte = build(cfg, range(148, 160))
    print(f"train {Xtr.shape}  test {Xte.shape}  classes {MODALITY}")
    print(f"test class balance: {[int((Yte == i).sum()) for i in range(4)]}\n")

    blocks = {
        "13 marginal only": list(range(13)),
        "5 shape only": list(range(13, 18)),
        "18 marginal+shape (S-TIM input)": list(range(18)),
    }
    results = {}
    print(f"{'feature block':<36}{'modality acc':>14}   per-class recall")
    print("-" * 92)
    for label, idx in blocks.items():
        acc, per = fit_predict(Xtr[:, idx], Xte[:, idx], Ytr, Yte)
        results[label] = acc
        ps = "  ".join(f"{k}={v:.2f}" for k, v in per.items())
        print(f"{label:<36}{acc * 100:>13.1f}%   {ps}")

    print("\nchance = 25.0%")
    marg = results["13 marginal only"]
    shape = results["5 shape only"]
    print()
    print("Interpretation")
    print("-" * 92)
    print(f"  the marginal block alone reaches {marg * 100:.1f}% modality accuracy;")
    print(f"  the shape block alone reaches {shape * 100:.1f}%.")
    if marg > 0.9:
        print("  -> The modality label is already recoverable from the features the")
        print("     risk head already receives, so supervising a modality head hands")
        print("     it nothing it cannot already read. That is why every detection")
        print("     metric is unchanged when the auxiliary supervision is switched")
        print("     on, and it identifies the representation rather than the network")
        print("     as the binding constraint.")
    else:
        print("  -> inconclusive; inspect the per-class recalls above.")


if __name__ == "__main__":
    main()
