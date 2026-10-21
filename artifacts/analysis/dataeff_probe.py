"""Fast probe: does the multi-head encoder pay off when data is scarce?

Replicates the two learning architectures of the artifact on the real feature
extractor and the real training-set construction, at several training-set
sizes:

  MLP-shaped      the feature-matched control: two hidden layers of 64 with a
                  LayerNorm, a single risk head, binary label only. This is
                  the RiskOnlyNet shape that MLP-Trust uses.
  multi risk-only the proposed encoder: two hidden layers of 96 with a
                  LayerNorm, a risk head and four auxiliary heads, every
                  auxiliary loss off.
  multi + modality the same encoder with the modality head supervised at
                  weight 0.30.

The published 60-seed regime is saturated, so the three variants coincide
there. The question this probe asks is whether they separate when the
training set is too small for the risk head to learn on its own which attack
class it is looking at.

    python -u artifacts/analysis/dataeff_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
from marl_policy import extract_marl_policy_features  # noqa: E402

SIZES = [6, 12, 24, 60]
MODALITY = ("benign", "constant", "dormant", "on-off")
EPOCHS = 200


def build(cfg, seeds):
    X, Y, M = [], [], []
    n = int(cfg.raw["network"]["default_uavs"])
    agents = int(cfg.raw["network"]["default_thinker_agents"])
    for s in seeds:
        streams, malicious, atk = rs.simulate_trust_stream(
            cfg, seed=s, n_uavs=n, malicious_ratio=0.30, n_agents=agents)
        feats, _ = extract_marl_policy_features(
            cfg, streams, agents, use_shape=True, spatial_adjacency=None)
        X.append(feats)
        Y.append(malicious.astype(np.float32))
        M.append(np.array([MODALITY.index(str(a).strip().lower()) for a in atk]))
    return (np.vstack(X).astype(np.float32), np.concatenate(Y),
            np.concatenate(M))


def make_model(kind, in_dim):
    from torch import nn
    if kind == "mlp":
        return nn.Sequential(
            nn.Linear(in_dim, 64), nn.LayerNorm(64), nn.ReLU(),
            nn.Linear(64, 64), nn.ReLU(),
            nn.Linear(64, 1))
    enc = nn.Sequential(nn.Linear(in_dim, 96), nn.LayerNorm(96), nn.ReLU(),
                         nn.Linear(96, 96), nn.ReLU())
    return nn.ModuleDict({"enc": enc,
                           "risk": nn.Linear(96, 1),
                           "mod": nn.Linear(96, 4)})


def run_variant(Xa, ya, ma, Xb, yb, kind, modality_weight, seed=0):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    np.random.seed(seed)
    mu, sd = Xa.mean(axis=0), Xa.std(axis=0) + 1e-6
    A = torch.tensor((Xa - mu) / sd, dtype=torch.float32)
    B = torch.tensor((Xb - mu) / sd, dtype=torch.float32)
    ta = torch.tensor(ya, dtype=torch.float32)
    tam = torch.tensor(ma, dtype=torch.long)

    model = make_model(kind, A.shape[1])
    params = list(model.parameters())
    opt = torch.optim.Adam(params, lr=0.0015, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([2.0]))
    ce = nn.CrossEntropyLoss()
    loader = DataLoader(TensorDataset(A, ta, tam), batch_size=64, shuffle=True,
                        generator=torch.Generator().manual_seed(seed))

    for _ in range(EPOCHS):
        for xb, yb_, mb in loader:
            opt.zero_grad()
            if kind == "mlp":
                out = model(xb).squeeze(-1)
                loss = bce(out, yb_)
            else:
                h = model["enc"](xb)
                out = model["risk"](h).squeeze(-1)
                loss = bce(out, yb_)
                if modality_weight > 0:
                    loss = loss + modality_weight * ce(model["mod"](h), mb)
            loss.backward()
            opt.step()

    with torch.no_grad():
        if kind == "mlp":
            pred = (model(B).squeeze(-1) > 0).numpy()
        else:
            h = model["enc"](B)
            pred = (model["risk"](h).squeeze(-1) > 0).numpy()
    y = np.asarray(yb)
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1)))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return float((pred == y).mean()), float(f1)


def main() -> int:
    cfg = rs.load_config(str(ROOT / "artifacts" / "configs" / "default.json"))

    print("=" * 100)
    print("DATA-EFFICIENCY PROBE -- identical features, different architecture and supervision")
    print("=" * 100)
    print(f"{'train seeds':<13}{'rows':>7}{'MLP-shaped':>16}{'multi risk-only':>18}"
          f"{'multi + modality':>20}")
    print("-" * 100)

    for k in SIZES:
        n_val = max(1, int(round(k * 0.2)))
        fit_seeds = list(range(100, 100 + k))[:-n_val]
        Xf, yf, mf = build(cfg, fit_seeds)
        Xt, yt, mt = build(cfg, range(900, 912))
        a_s, f_s = run_variant(Xf, yf, mf, Xt, yt, "mlp", 0.0)
        a_r, f_r = run_variant(Xf, yf, mf, Xt, yt, "multi", 0.0)
        a_m, f_m = run_variant(Xf, yf, mf, Xt, yt, "multi", 0.30)
        print(f"{k:<13}{len(Xf):>7}{a_s * 100:>15.1f}%{a_r * 100:>17.1f}%"
              f"{a_m * 100:>19.1f}%")
        print(f"{'  (F1)':<13}{'':>7}{f_s * 100:>15.1f}%{f_r * 100:>17.1f}%"
              f"{f_m * 100:>19.1f}%")

    print("-" * 100)
    print("MLP-shaped       the feature-matched control (RiskOnlyNet shape), "
          "binary label only")
    print("multi risk-only  the proposed encoder, every auxiliary loss off")
    print("multi + modality the proposed encoder, modality head supervised at 0.30")
    print("test seeds       900-911, twelve seeds never used for training")
    return 0


if __name__ == "__main__":
    sys.exit(main())
