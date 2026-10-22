"""How the level signal disappears as the camouflage factor rises.

The generator mixes a malicious node's attack profile with an evasive
reference by a per-node factor c drawn from a beta distribution:

    attack_mean = (1 - c) * profile + c * evasive_reference

so c = 0 is the loudest end and c = 1 is the quietest, where the attacker's
level is the evasive reference rather than the attack profile. The published
generator draws c from beta(2.7, 1.8), whose mean is 0.60.

This script measures what that factor does to the evidence a trust
aggregator can use, because the answer decides whether the benchmark has
headroom:

  level effect size   Cohen's d between the active attackers' level and the
                      benign level, per channel. The paper's marginal block
                      is a level statistic, so this is the quantity it has
                      to work with.
  risk separability   held-out accuracy of a probe on the 13 marginal
                      features. At 1.000 the benchmark is saturated and no
                      method can be separated from any other.
  on-off, marginal    detection of the periodic attackers by the marginal
                      block alone.
  on-off, +shape      the same by the marginal plus shape block.

The shape statistics are scale-free, so the hypothesis is that the level
channel degrades with c while the shape channel does not, and that the gap
between the two widens.

    python -u artifacts/analysis/camouflage_direction_sweep.py
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

# The camouflage factor's distribution. The published one first, then levels
# whose mean moves upwards, towards the quiet end of the mixture.
LEVELS = [
    ("published beta(2.7, 1.8)", 2.7, 1.8),
    ("beta(1.0, 1.0)", 1.0, 1.0),
    ("beta(2.0, 1.0)", 2.0, 1.0),
    ("beta(3.0, 1.0)", 3.0, 1.0),
    ("beta(4.0, 1.0)", 4.0, 1.0),
    ("beta(6.0, 1.0)", 6.0, 1.0),
    ("beta(9.0, 1.0)", 9.0, 1.0),
]


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Pooled effect size of sample a against sample b."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = ((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)
    if pooled <= 0:
        return 0.0
    return float(abs(a.mean() - b.mean()) / np.sqrt(pooled))


def build(cfg, seeds, n_uavs: int):
    """Per-seed feature matrices and labels, with the level channels kept."""
    X13, X18, Y, R, A = [], [], [], [], []
    for s in seeds:
        streams, malicious, atk = rs.simulate_trust_stream(
            cfg, seed=s, n_uavs=n_uavs, malicious_ratio=0.30,
            n_agents=int(cfg.raw["network"]["default_thinker_agents"]))
        feats, _ = extract_marl_policy_features(
            cfg, streams, int(cfg.raw["network"]["default_thinker_agents"]),
            use_shape=True, spatial_adjacency=None)
        X18.append(feats)
        X13.append(feats[:, :13])
        R.append(malicious.astype(np.int64))
        A.append(np.array([str(a).strip().lower() for a in atk]))
        # The on-off attackers toggle with a fixed period, so the label of a
        # node is constant and the per-node detection rate is the fraction of
        # on-off nodes the classifier calls malicious.
        Y.append(malicious.astype(np.int64))
    return (np.vstack(X13), np.vstack(X18),
            np.concatenate(Y), np.concatenate(R), np.concatenate(A))


def fit_probe(Xa, Xb, ya, yb, n_out, hidden=32, seed=0):
    """Small classifier; returns (accuracy, per-class recall dict, predictions)."""
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
        pred = net(B).argmax(dim=1).numpy()
    acc = float((pred == yb).mean())
    per = {}
    for i in range(n_out):
        m = yb == i
        if m.any():
            per[i] = float((pred[m] == i).mean())
    return acc, per, pred


def sweep(levels, key, label_fmt, extra=None):
    """Run the measurement over a list of (label, a, b) camouflage levels."""
    base_raw = json.loads(
        (ROOT / "artifacts" / "configs" / "default.json").read_text(
            encoding="utf-8-sig"))
    n_uavs = int(base_raw["network"]["default_uavs"])
    agents = int(base_raw["network"]["default_thinker_agents"])
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, a, b in levels:
            raw = copy.deepcopy(base_raw)
            raw.setdefault("generator", {})["camouflage_beta_a"] = a
            raw["generator"]["camouflage_beta_b"] = b
            if extra:
                raw["generator"].update(extra.get(label, {}))
            p = Path(tmp) / "cfg.json"
            p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            cfg = rs.load_config(str(p))

            step_d, window_d = [], []
            for s in range(100, 116):
                streams, malicious, atk = rs.simulate_trust_stream(
                    cfg, seed=s, n_uavs=n_uavs, malicious_ratio=0.30,
                    n_agents=agents)
                types = np.array([str(x).strip().lower() for x in atk])
                active = malicious & (types != "dormant")
                post = streams[cfg.warmup_steps:, :, :4]
                wpost = post.mean(axis=0)
                for ch in range(4):
                    step_d.append(cohens_d(post[:, active, ch].ravel(),
                                           post[:, ~malicious, ch].ravel()))
                    window_d.append(cohens_d(wpost[active, ch],
                                             wpost[~malicious, ch]))

            X13tr, X18tr, Rtr, _, _ = build(cfg, range(100, 148), n_uavs)
            X13te, X18te, Rte, _, Ate = build(cfg, range(148, 160), n_uavs)

            sep13, _, _ = fit_probe(X13tr, X13te, Rtr, Rte, 2)
            sep18, _, _ = fit_probe(X18tr, X18te, Rtr, Rte, 2)
            _, _, pred13 = fit_probe(X13tr, X13te, Rtr, Rte, 2)
            # The 18-dimensional probe is trained on the same block it is
            # evaluated on, so each block normalises on its own statistics.
            _, _, pred18 = fit_probe(X18tr, X18te, Rtr, Rte, 2)

            # The on-off detection is the recall of the malicious class on the
            # on-off subset, not the recall over all malicious nodes, which
            # the constant and dormant attackers would dominate.
            onoff = (Ate == "on-off") & (Rte == 1)
            marg = (float((pred13[onoff] == 1).mean()) if onoff.any()
                    else float("nan"))
            shape = (float((pred18[onoff] == 1).mean()) if onoff.any()
                     else float("nan"))
            out.append((label, a / (a + b), float(np.mean(step_d)),
                        float(np.mean(window_d)), sep13, sep18, marg, shape,
                        shape - marg))
    return out


def print_rows(title, rows):
    print()
    print("=" * 118)
    print(title)
    print("=" * 118)
    print(f"{'level':<26}{'mean c':>8}{'step d':>8}{'window d':>11}{'sep(13)':>10}"
          f"{'sep(18)':>9}{'on-off marg':>13}{'on-off +shape':>15}{'gap':>8}")
    print("-" * 118)
    for label, mean_c, sd_, wd, sep13, sep18, marg, shape, gap in rows:
        print(f"{label:<26}{mean_c:>8.3f}{sd_:>8.2f}{wd:>11.2f}"
              f"{sep13 * 100:>9.1f}%{sep18 * 100:>9.1f}%"
              f"{marg * 100:>12.1f}%{shape * 100:>14.1f}%{gap * 100:>7.1f}pp")


def main() -> int:
    print("=" * 118)
    print("CAMOUFLAGE DIRECTION -- the level evidence against the shape evidence")
    print("=" * 118)

    rows_a = sweep(LEVELS, "camouflage", "c")
    print_rows("PART A -- the camouflage factor, at the published node bias", rows_a)

    # The camouflage factor flattens the attack profile but leaves the
    # per-node offset alone, and the offset enters the attacker's level with
    # a quarter of the weight it enters the benign level with, so a large
    # offset is what separates the two populations once the window has
    # averaged the observation noise away. The second sweep therefore asks
    # what happens when the benign population's own spread is large enough
    # for the attacker's level to fall inside it.
    bias_levels = [("node bias 0.08 (published)", 2.7, 1.8),
                   ("node bias 0.15", 2.7, 1.8),
                   ("node bias 0.25", 2.7, 1.8),
                   ("node bias 0.40", 2.7, 1.8),
                   ("node bias 0.60", 2.7, 1.8),
                   ("node bias 0.40, camo 0.9", 9.0, 1.0)]
    bias_extra = {"node bias 0.15": {"node_bias_sd": 0.15},
                  "node bias 0.25": {"node_bias_sd": 0.25},
                  "node bias 0.40": {"node_bias_sd": 0.40},
                  "node bias 0.60": {"node_bias_sd": 0.60},
                  "node bias 0.40, camo 0.9": {"node_bias_sd": 0.40}}
    rows_b = sweep(bias_levels, "bias", "sd", bias_extra)
    print_rows("PART B -- the benign population's own spread", rows_b)

    print("-" * 118)
    print("mean c      the mean camouflage factor; attack weight is (1 - c), so a")
    print("            larger mean is a quieter attacker")
    print("step d      mean Cohen's d of the attacker's level against the benign")
    print("            level, over the four behaviour channels, per step")
    print("window d    the same after averaging each channel over the window the")
    print("            marginal block uses, which is the effect size a window")
    print("            summary can actually exploit")
    print("sep(13)     held-out separability of the malicious label from the 13")
    print("            marginal features alone")
    print("on-off      the periodic attackers' detection by the marginal block and")
    print("            by the marginal plus shape block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
