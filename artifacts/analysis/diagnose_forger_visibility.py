"""Why does the behaviour block see the telemetry forger?

The prediction was that a forger reporting benign channels would be invisible
to the 13 marginal features. The probe says 76.3%, so the assumption is
wrong somewhere. This prints, per feature, the forger's standardised effect
size against the benign population, and the same for the spatial features.
"""

import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
from marl_policy import (extract_marl_policy_features,  # noqa: E402
                          resolve_spatial_adjacency)

cfg = rs.load_config(str(ROOT / "artifacts" / "configs" / "spatial_position.json"))
N = int(cfg.raw["network"]["default_uavs"])
AGENTS = int(cfg.raw["network"]["default_thinker_agents"])
RATIO = 0.30

X, Y, AT, MT = [], [], [], []
for s in range(200, 216):
    streams, mal, atk = rs.simulate_trust_stream(
        cfg, seed=s, n_uavs=N, malicious_ratio=RATIO, n_agents=AGENTS)
    adj = resolve_spatial_adjacency(cfg, s, N, RATIO)
    x, names = extract_marl_policy_features(
        cfg, streams, AGENTS, use_shape=True, spatial_adjacency=adj)
    X.append(x)
    Y.append(mal)
    AT.append([str(a) for a in atk])
    MT.append([str(a) for a in mal])
X = np.vstack(X)
Y = np.concatenate(Y)
AT = np.array([a for r in AT for a in r])
MT = np.array([a for r in MT for a in r])

benign = ~Y
forger = (AT == "position-inconsistent")
print(f"n = {len(X)}  benign = {benign.sum()}  forgers = {forger.sum()}")

print()
print(f"{'feature':<34}{'benign mean':>13}{'benign sd':>11}"
      f"{'forger mean':>13}{'effect d':>10}")
print("-" * 81)
for j, nm in enumerate(names):
    b = X[benign, j]
    f = X[forger, j]
    d = (f.mean() - b.mean()) / (b.std() + 1e-12)
    flag = "  <-- spatial" if nm.startswith("spatial_") else ""
    print(f"{nm:<34}{b.mean():>13.4f}{b.std():>11.4f}{f.mean():>13.4f}{d:>10.2f}{flag}")

print()
print("=" * 78)
print("IS THE FORGER ACTUALLY BENIGN IN ITS OWN CHANNELS?")
print("=" * 78)
print(f"  forgers whose T1 mean is within 0.05 of the benign mean: "
      f"{int((np.abs(X[forger, 0] - X[benign, 0].mean()) < 0.05).sum())}/{forger.sum()}")

print()
print("  attack class means of the raw T1 channel (streams[:, :, 0]):")
for s in (200, 201):
    streams, mal, atk = rs.simulate_trust_stream(
        cfg, seed=s, n_uavs=N, malicious_ratio=RATIO, n_agents=AGENTS)
    t1 = streams[:, :, 0].mean(axis=0)
    print(f"    seed {s}: benign T1 = {t1[~mal].mean():.4f} (sd {t1[~mal].std():.4f})")
    for t in ("constant", "dormant", "on-off", "position-inconsistent"):
        m = np.array([str(a) == t for a in atk])
        if m.any():
            print(f"        {t:<22} T1 = {t1[m].mean():.4f}")
    # the forgers' own field offset and their neighbours'
    adj = resolve_spatial_adjacency(cfg, s, N, RATIO)
    print(f"    the forgers' neighbour count: "
          f"{[int((adj[i] > 0).sum()) for i in np.where(mal & (np.array([str(a) for a in atk]) == 'position-inconsistent'))[0]][:6]}")
