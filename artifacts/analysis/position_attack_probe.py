"""DECISIVE TEST: is the spatial block complementary to the behaviour channels?

The telemetry-forging attacker reports channels that are indistinguishable from
the benign population but is placed where the RF field differs from what it
reports. If the design is right:

  * the 13 marginal features carry no signal for it
  * the 5 shape features carry no signal for it
  * the 5 spatial features carry a strong signal

A logistic probe is fitted per feature block on training seeds and scored on
held-out seeds, and the detection rate is reported per attack class. This is
the same probe protocol the paper already uses for the marginal-vs-shape
comparison, so the numbers are directly comparable.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
from marl_policy import (extract_marl_policy_features,  # noqa: E402
                          resolve_spatial_adjacency)

CFG = ROOT / "artifacts" / "configs" / "spatial_position.json"
cfg = rs.load_config(str(CFG))
N = int(cfg.raw["network"]["default_uavs"])
AGENTS = int(cfg.raw["network"]["default_thinker_agents"])
RATIO = float(cfg.raw["experiments"]["main_ratio"])
TRAIN = list(range(100, 116))
TEST = list(range(200, 216))

print("=" * 78)
print("CONFIG")
print("=" * 78)
sp = cfg.raw["spatial"]
for k in ("enabled", "features", "position_attack_ratio", "field_amplitude",
          "field_grid", "comm_range_m", "airspace_side_m"):
    print(f"  spatial.{k:<24} = {sp.get(k)}")
print(f"  n_uavs = {N}  agents = {AGENTS}  malicious_ratio = {RATIO}")
print(f"  train seeds {TRAIN[0]}-{TRAIN[-1]}   test seeds {TEST[0]}-{TEST[-1]}")


def build(seeds):
    X, Y, AT, MAL = [], [], [], []
    for s in seeds:
        streams, malicious, atk = rs.simulate_trust_stream(
            cfg, seed=s, n_uavs=N, malicious_ratio=RATIO, n_agents=AGENTS)
        adj = resolve_spatial_adjacency(cfg, s, N, RATIO)
        x, names = extract_marl_policy_features(
            cfg, streams, AGENTS, use_shape=True, spatial_adjacency=adj)
        X.append(x)
        Y.append(malicious.astype(int))
        AT.append([str(a) for a in atk])
        MAL.append(malicious)
    return (np.vstack(X), np.concatenate(Y),
            np.array([a for row in AT for a in row]), names)


Xtr, Ytr, ATr, names = build(TRAIN)
Xte, Yte, ATe, _ = build(TEST)
print(f"\nfeature matrix {Xtr.shape}  names={len(names)}")
print("  spatial names:", [n for n in names if n.startswith("spatial_")])

# how many of each attack class are there
print("\nattack class counts in the test split:")
for t in sorted(set(ATe.tolist())):
    m = (ATe == t) & (Yte == 1)
    print(f"  {t:<24} {int(m.sum()):>5} malicious nodes")


def probe(idx, seed=0):
    """Logistic probe on the given feature columns."""
    from sklearn.linear_model import LogisticRegression
    mu = Xtr[:, idx].mean(axis=0)
    sd = Xtr[:, idx].std(axis=0) + 1e-8
    A = (Xtr[:, idx] - mu) / sd
    B = (Xte[:, idx] - mu) / sd
    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    clf.fit(A, Ytr)
    return clf.predict_proba(B)[:, 1]


BLOCKS = {
    "13 marginal only": list(range(13)),
    "18 marginal + 5 shape": list(range(18)),
    "23 marginal + shape + 5 spatial": list(range(23)),
}

print()
print("=" * 78)
print("PROBE DETECTION RATE (%) BY ATTACK CLASS")
print("=" * 78)
classes = ["constant", "dormant", "on-off", "position-inconsistent"]
header = f"{'feature block':<34}" + "".join(f"{c[:18]:>20}" for c in classes)
print(header)
print("-" * len(header))
results = {}
for label, idx in BLOCKS.items():
    p = probe(idx)
    row = {"block": label}
    cells = []
    for c in classes:
        m = (ATe == c) & (Yte == 1)
        rate = float((p[m] > 0.5).mean()) * 100 if m.any() else float("nan")
        row[c] = rate
        cells.append(f"{rate:>19.1f}%")
    results[label] = row
    print(f"{label:<34}" + "".join(cells))

print()
print("=" * 78)
print("THE DECISIVE CELL")
print("=" * 78)
r13 = results["13 marginal only"]["position-inconsistent"]
r18 = results["18 marginal + 5 shape"]["position-inconsistent"]
r23 = results["23 marginal + shape + 5 spatial"]["position-inconsistent"]
print(f"  behaviour-only (18-dim) on the forger : {r18:.1f}%")
print(f"  with the spatial block (23-dim)         : {r23:.1f}%")
print(f"  spatial block contribution             : {r23 - r18:+.1f} pp")
if r18 < 35 and r23 - r18 > 25:
    print("\n  -> COMPLEMENTARY: the behaviour channels are blind to this attacker")
    print("     and the spatial block is the only thing that sees it. The two")
    print("     modalities cover disjoint attack classes, which is what makes a")
    print("     spatio-temporal fusion necessary rather than decorative.")
elif r23 - r18 > 10:
    print("\n  -> PARTIAL: the spatial block adds signal but the gap is modest.")
else:
    print("\n  -> NOT SUPPORTED: the spatial block does not separate this attacker.")

out = ROOT / "artifacts" / "runs" / "position_attack_probe.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nwrote {out}")
