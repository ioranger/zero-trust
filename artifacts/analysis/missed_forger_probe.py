"""Is the residual of a missed spatially inconsistent attacker still informative?

In the published spatial scenario the proposed model detects 83.6% of the
forgers whose own telemetry is indistinguishable from benign traffic. The
question this probe answers is whether the remaining 16.4% are recoverable,
and it separates the two answers that look the same from the outside:

  information present   the missed forger's neighbourhood-relative residual
                        is as large as the detected forger's, so a better
                        combination rule could still catch it;
  information absent    the missed forger's residual is as small as a benign
                        node's, so no rule over these features can catch it
                        and the ceiling is the representation itself.

The probe reproduces the generator's own seeds, scores them with the arm's own
checkpoint, and then compares the residual of the detected forgers, the missed
forgers and the benign nodes. Nothing is trained and no configuration is
changed.

    python -u artifacts/analysis/missed_forger_probe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
import marl_policy as mp  # noqa: E402

ARM = ROOT / "artifacts" / "runs" / "spatial_position_23dim"
CONFIG = ROOT / "artifacts" / "configs" / "spatial_position.json"
EVAL_SEEDS = list(range(1000, 1019))
RESIDUALS = ["spatial_dev_T1", "spatial_dev_T4", "spatial_gap_dev",
              "spatial_rel_dev", "spatial_std_dev"]


def main() -> int:
    import torch

    cfg = rs.load_config(str(CONFIG))
    policy = json.loads((ARM / "logs" / "marl_policy.json").read_text(encoding="utf-8"))
    policy["checkpoint_path"] = str(ARM / "checkpoints" / "stim_marl_policy.pt")
    model = mp.load_torch_policy(policy, ROOT)
    model.eval()
    mean = np.array(policy["mean"], dtype=float)
    std = np.array(policy["std"], dtype=float)
    threshold = float(policy["threshold"])
    names = list(policy["feature_names"])
    resid_idx = [names.index(n) for n in RESIDUALS if n in names]

    n_uavs = int(cfg.raw["network"]["default_uavs"])
    n_agents = int(cfg.raw["network"]["default_thinker_agents"])
    ratio = float(cfg.raw["experiments"]["main_ratio"])

    buckets = {"forger, detected": [], "forger, missed": [], "benign": []}
    risk = {"forger, detected": [], "forger, missed": [], "benign": []}

    for seed in EVAL_SEEDS:
        streams, malicious, attack_types = rs.simulate_trust_stream(
            cfg, seed, n_uavs=n_uavs, malicious_ratio=ratio, n_agents=n_agents)
        adj = mp.resolve_spatial_adjacency(cfg, seed, n_uavs, ratio)
        x, _ = mp.extract_marl_policy_features(cfg, streams, n_agents,
                                               spatial_adjacency=adj)
        xs = (x - mean) / std
        with torch.no_grad():
            out = model(torch.tensor(xs, dtype=torch.float32))
            score = torch.sigmoid(out["risk_logit"]).numpy()
        # the residual magnitude the neighbourhood block actually carries
        resid = np.abs(xs[:, resid_idx]).mean(axis=1)
        for node in range(n_uavs):
            at = str(attack_types[node])
            if at == "position-inconsistent":
                key = "forger, detected" if score[node] > threshold else "forger, missed"
            elif not malicious[node]:
                key = "benign"
            else:
                continue
            buckets[key].append(resid[node])
            risk[key].append(score[node])
        print(f"  seed {seed}: done", flush=True)

    print()
    print("=" * 92)
    print("NEIGHBOURHOOD RESIDUAL (standardised, mean absolute over the five")
    print("neighbourhood-relative features) BY GROUP")
    print("=" * 92)
    print(f"{'group':>22}{'n':>10}{'residual mean':>16}{'residual p90':>15}"
          f"{'risk mean':>13}")
    print("-" * 92)
    for k, v in buckets.items():
        a = np.asarray(v)
        r = np.asarray(risk[k])
        print(f"{k:>22}{a.size:>10}{a.mean():>16.3f}"
              f"{np.quantile(a, 0.9):>15.3f}{r.mean():>13.3f}")

    det = np.asarray(buckets["forger, detected"])
    mis = np.asarray(buckets["forger, missed"])
    ben = np.asarray(buckets["benign"])

    print()
    print("=" * 92)
    print("VERDICT")
    print("=" * 92)
    if mis.size == 0:
        print("  no missed forger in this sample; nothing to diagnose")
        return 0
    # A missed forger whose residual is close to the benign population carries
    # no information; one whose residual is close to the detected forgers does.
    midpoint = (ben.mean() + det.mean()) / 2.0
    verdict = "information present" if mis.mean() > midpoint else "information absent"
    print(f"  the midpoint between the benign residual ({ben.mean():.3f}) and the")
    print(f"  detected forger residual ({det.mean():.3f}) is {midpoint:.3f}; the missed")
    print(f"  forgers sit at {mis.mean():.3f}.")
    print()
    print(f"  VERDICT: {verdict}")
    if verdict == "information present":
        print("  A combination rule over the same features could still recover these")
        print("  nodes, so the ceiling is the decision rule rather than the")
        print("  representation, and a per-node evidence-routing model is worth")
        print("  building.")
    else:
        print("  The missed forgers look like benign nodes in the neighbourhood block")
        print("  as well as in their own channels, so no rule over these features can")
        print("  recover them and the ceiling is the representation itself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
