"""Where does the block-routed gate send each attack class, and what would the
per-class detection rates be if the routing were forced?

The block-routed arm (`spatial_position_gated`) gives every evidence block its
own encoder and its own risk specialist, and mixes the specialists with a
per-node gate that is trained by the risk loss alone. On the spatial scenario
it lands on the same per-class rates as the published single-encoder arm, and
the constant class stays about three points below what the 13-dimensional
marginal-only arm reaches. Two explanations fit that:

  mis-routing   the gate sends constant and dormant nodes to the shape or
                neighbourhood specialist, whose opinion is wrong for them, so
                the mixture is wrong even though the marginal branch itself
                is fine;
  branch decay  the marginal branch is itself worse than the marginal-only
                arm's encoder, because it is trained through a mixture and
                its gradient is diluted.

The two are separated by counterfactuals that need no retraining. The probe
below recomputes the trust streams for a few evaluation seeds, runs the saved
checkpoint, and then replaces the learned mixture with three forced ones:
every node scored by the marginal specialist alone, by the shape specialist
alone, by the neighbourhood specialist alone, and by the uniform average of
the three. If the forced-marginal counterfactual recovers the marginal-only
arm's constant rate, the gate is at fault. If it does not, the branch itself
is.

Nothing is trained here and no number is adjusted. Every rate printed is
computed from the arm's own checkpoint and the generator's own seeds.

    python -u artifacts/analysis/gate_routing_probe.py
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

ARM = ROOT / "artifacts" / "runs" / "spatial_position_gated"
CONFIG = ROOT / "artifacts" / "configs" / "spatial_position_gated.json"
SEEDS = [1000, 1001, 1002, 1003, 1004]
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]


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
    block_names = [str(b[0]) for b in policy["feature_blocks"]]
    block_idx = [np.asarray(b[1], dtype=int) for b in policy["feature_blocks"]]
    n_uavs = int(cfg.raw["network"]["default_uavs"])
    n_agents = int(cfg.raw["network"]["default_thinker_agents"])
    ratio = float(cfg.raw["experiments"]["main_ratio"])

    print("=" * 104)
    print(f"GATE ROUTING PROBE -- arm: spatial_position_gated, seeds {SEEDS}, "
          f"threshold {threshold:.2f}")
    print("=" * 104)
    print(f"  blocks: {block_names}")
    print(f"  feature width: {policy['input_dim']}")

    # acc[mode][class] = [n_nodes, n_detected]
    modes = ["learned gate", "forced marginal", "forced shape",
             "forced neighborhood", "uniform mix"]
    acc = {m: {c: [0, 0] for c in CLASSES} for m in modes}
    gate_sum = {c: np.zeros(len(block_names)) for c in CLASSES}
    gate_n = {c: 0 for c in CLASSES}
    argmax_hist = {c: {b: 0 for b in block_names} for c in CLASSES}
    missed_gate = {c: np.zeros(len(block_names)) for c in CLASSES}
    missed_n = {c: 0 for c in CLASSES}

    for seed in SEEDS:
        streams, malicious, attack_types = rs.simulate_trust_stream(
            cfg, seed, n_uavs=n_uavs, malicious_ratio=ratio, n_agents=n_agents)
        adj = mp.resolve_spatial_adjacency(cfg, seed, n_uavs, ratio)
        x, _names = mp.extract_marl_policy_features(
            cfg, streams, n_agents, spatial_adjacency=adj)
        xs = (x - mean) / std
        xt = torch.tensor(xs, dtype=torch.float32)
        with torch.no_grad():
            out = model(xt)
            embs = [enc(xt[:, idx]) for enc, idx in zip(model.encoders, block_idx)]
            cat = torch.cat(embs, dim=-1)
            gw = torch.softmax(model.gate(cat), dim=-1).numpy()
            logits = np.stack(
                [head(e).squeeze(-1).numpy() for head, e in
                 zip(model.risk_heads, embs)], axis=-1)

        scores = {
            "learned gate": out["risk_logit"].numpy(),
            "forced marginal": logits[:, 0],
            "forced shape": logits[:, 1],
            "forced neighborhood": logits[:, 2],
            "uniform mix": logits.mean(axis=1),
        }
        pred = {m: (1.0 / (1.0 + np.exp(-s)) > threshold) for m, s in scores.items()}

        for node in range(n_uavs):
            c = str(attack_types[node])
            if c not in acc["learned gate"]:
                continue
            for m in modes:
                acc[m][c][0] += 1
                acc[m][c][1] += int(pred[m][node])
            gate_sum[c] += gw[node]
            gate_n[c] += 1
            am = block_names[int(np.argmax(gw[node]))]
            argmax_hist[c][am] += 1
            if not pred["learned gate"][node] and c != "benign":
                missed_gate[c] += gw[node]
                missed_n[c] += 1
        print(f"  seed {seed}: done", flush=True)

    print()
    print("=" * 104)
    print("1. per-class detection rate (%) under the learned gate and under forced routing")
    print("=" * 104)
    print(f"{'attack class':>22}" + "".join(f"{m:>22}" for m in modes))
    print("-" * 104)
    for c in CLASSES:
        row = f"{c:>22}"
        for m in modes:
            n, k = acc[m][c]
            row += f"{(100.0 * k / n if n else float('nan')):>22.1f}"
        print(row)

    print()
    print("=" * 104)
    print("2. where the learned gate puts its weight, by attack class (mean mixture weight)")
    print("=" * 104)
    print(f"{'attack class':>22}" + "".join(f"{b:>16}" for b in block_names)
          + f"{'argmax branch':>20}")
    print("-" * 104)
    for c in CLASSES:
        if not gate_n[c]:
            continue
        mean_gw = gate_sum[c] / gate_n[c]
        row = f"{c:>22}" + "".join(f"{v:>16.3f}" for v in mean_gw)
        top = max(block_names, key=lambda b: argmax_hist[c][b])
        print(row + f"{top:>20}")

    print()
    print("=" * 104)
    print("3. the same mixture weights for the nodes the learned gate MISSES")
    print("=" * 104)
    print(f"{'attack class':>22}" + "".join(f"{b:>16}" for b in block_names)
          + f"{'n missed':>12}")
    print("-" * 104)
    for c in CLASSES:
        if c == "benign" or not missed_n[c]:
            continue
        mg = missed_gate[c] / missed_n[c]
        print(f"{c:>22}" + "".join(f"{v:>16.3f}" for v in mg) + f"{missed_n[c]:>12}")

    print()
    print("=" * 104)
    print("4. what the comparison implies")
    print("=" * 104)
    print("   forced marginal / forced shape / forced neighborhood are the same")
    print("   trained branches scored without the gate, so the difference between")
    print("   them and the learned gate is the cost of mixing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
