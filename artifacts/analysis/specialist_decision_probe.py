"""Can a decision rule over the trained specialists recover the forgers that
the mixture averages away?

The block-routed arm mixes its three specialists with a learned per-node gate,
i.e. it takes a weighted average of their risk logits. The missed-forger probe
shows what that costs: the forgers the mixture misses still carry a larger
neighbourhood-relative residual than the benign population does, so their
evidence is present and the mixture has diluted it.

This probe builds three decision rules over the same trained branches, with
every threshold chosen on the arm's held-out validation seeds at a matched 5%
benign false-positive rate, and reports what each of them detects:

  mixture        the published rule: a weighted average of the branch logits;
  max of experts the branch whose calibrated evidence is strongest decides;
  sum of experts every branch that fires above its own calibrated level adds.

Nothing is trained and no configuration is changed: the branches, the gate and
the generator are the arm's own.

    python -u artifacts/analysis/specialist_decision_probe.py
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
EVAL_SEEDS = list(range(1000, 1019))
FPR_TARGET = 0.05
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]


def quantiles_at_fpr(benign: np.ndarray, fpr: float = FPR_TARGET) -> float:
    return float(np.quantile(benign, 1.0 - fpr))


def threshold_at_fpr(benign: np.ndarray, fpr: float = FPR_TARGET) -> float:
    """The cut that flags exactly `fpr` of the benign scores."""
    return float(np.quantile(benign, 1.0 - fpr))


def per_seed_mean(values: list[np.ndarray], mask_fn) -> float:
    rates = []
    for scores, types, mal in values:
        m = mask_fn(types, mal)
        if m.sum() == 0:
            continue
        rates.append(float((scores[m] > 0).mean()))
    return 100.0 * float(np.mean(rates)) if rates else float("nan")


def main() -> int:
    import torch

    cfg = rs.load_config(str(CONFIG))
    policy = json.loads((ARM / "logs" / "marl_policy.json").read_text(encoding="utf-8"))
    policy["checkpoint_path"] = str(ARM / "checkpoints" / "stim_marl_policy.pt")
    model = mp.load_torch_policy(policy, ROOT)
    model.eval()
    mean = np.array(policy["mean"], dtype=float)
    std = np.array(policy["std"], dtype=float)
    block_idx = [np.asarray(b[1], dtype=int) for b in policy["feature_blocks"]]
    block_names = [str(b[0]) for b in policy["feature_blocks"]]
    n_uavs = int(cfg.raw["network"]["default_uavs"])
    n_agents = int(cfg.raw["network"]["default_thinker_agents"])
    ratio = float(cfg.raw["experiments"]["main_ratio"])
    val_seeds = [int(s) for s in (policy.get("validation_seeds") or [])]

    raw = {"val": [], "eval": []}

    def one_seed(seed: int, bucket: str):
        streams, malicious, attack_types = rs.simulate_trust_stream(
            cfg, seed, n_uavs=n_uavs, malicious_ratio=ratio, n_agents=n_agents)
        adj = mp.resolve_spatial_adjacency(cfg, seed, n_uavs, ratio)
        x, _ = mp.extract_marl_policy_features(cfg, streams, n_agents,
                                               spatial_adjacency=adj)
        xs = (x - mean) / std
        xt = torch.tensor(xs, dtype=torch.float32)
        with torch.no_grad():
            embs = [enc(xt[:, idx]) for enc, idx in zip(model.encoders, block_idx)]
            logits = np.stack(
                [head(e).squeeze(-1).numpy() for head, e in
                 zip(model.risk_heads, embs)], axis=-1)
            out = model(xt)
            mixed = out["risk_logit"].numpy()
            gate_w = torch.softmax(model.gate(torch.cat(embs, dim=-1)), dim=-1).numpy()
        raw[bucket].append((logits, mixed, gate_w,
                            np.asarray(attack_types, dtype=object),
                            np.asarray(malicious, dtype=bool)))

    for s in val_seeds:
        one_seed(s, "val")
    for s in EVAL_SEEDS:
        one_seed(s, "eval")

    # ---- calibrate each branch on the validation seeds ---------------------
    print("=" * 96)
    print(f"specialist decision probe -- arm spatial_position_gated, "
          f"{len(val_seeds)} validation seeds, {len(EVAL_SEEDS)} evaluation seeds")
    print("=" * 96)

    branch_benign = [[] for _ in block_names]
    for logits, _mixed, _gw, types, mal in raw["val"]:
        m = ~mal
        for b in range(len(block_names)):
            branch_benign[b].append(logits[m, b])
    q = [quantiles_at_fpr(np.concatenate(v)) for v in branch_benign]
    print()
    print("per-branch calibration on the validation seeds (the 95th percentile")
    print("of each branch's benign logit):")
    for b, name in enumerate(block_names):
        print(f"  {name:<16}{q[b]:>8.3f}")
    mixed_benign = np.concatenate([m[~mal] for _l, m, _g, _t, mal in raw["val"]])
    mixed_cut = threshold_at_fpr(mixed_benign)

    # ---- build the three rules --------------------------------------------
    def build(scores: dict) -> dict:
        return scores

    rules = {}
    for bucket in ("val", "eval"):
        mix_scores, max_scores, sum_scores = [], [], []
        for logits, mixed, _gw, types, mal in raw[bucket]:
            calibrated = logits - np.asarray(q)[None, :]
            mix_scores.append(mixed)
            max_scores.append(calibrated.max(axis=1))
            sum_scores.append(np.clip(calibrated, 0, None).sum(axis=1))
        rules[bucket] = {"mixture": mix_scores, "max": max_scores, "sum": sum_scores}

    # thresholds for the two new rules, from the validation seeds
    thr = {}
    for name in ("mixture", "max", "sum"):
        benign = np.concatenate([s[~mal] for s, (_l, _m, _g, _t, mal)
                                 in zip(rules["val"][name], raw["val"])])
        thr[name] = threshold_at_fpr(benign)

    print()
    print("thresholds at the matched 5% benign false-positive rate:")
    for name in ("mixture", "max", "sum"):
        print(f"  {name:<16}{thr[name]:>8.3f}")

    # ---- report ------------------------------------------------------------
    print()
    print("=" * 96)
    print("per-class detection rate (%) at the matched operating point")
    print("=" * 96)
    print(f"{'rule':<16}" + "".join(f"{c:>22}" for c in CLASSES)
          + f"{'benign spec.':>15}{'accuracy':>11}{'F-score':>10}")
    print("-" * 96)

    rows = {}
    for name in ("mixture", "max", "sum"):
        cells = []
        for c in CLASSES:
            rates = []
            for s, (_l, _m, _g, types, mal) in zip(rules["eval"][name], raw["eval"]):
                m = types == c
                if m.sum():
                    rates.append(float((s[m] > thr[name]).mean()))
            cells.append(100.0 * float(np.mean(rates)))
        benign_flag = []
        for s, (_l, _m, _g, types, mal) in zip(rules["eval"][name], raw["eval"]):
            benign_flag.append(float((s[~mal] > thr[name]).mean()))
        spec = 100.0 * (1.0 - float(np.mean(benign_flag)))
        tp = fp = fn = tn = 0
        for s, (_l, _m, _g, types, mal) in zip(rules["eval"][name], raw["eval"]):
            pred = s > thr[name]
            tp += int((pred & mal).sum())
            fp += int((pred & ~mal).sum())
            fn += int((~pred & mal).sum())
            tn += int((~pred & ~mal).sum())
        acc = 100.0 * (tp + tn) / max(tp + fp + fn + tn, 1)
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-12)
        rows[name] = (cells, spec, acc, 100 * f1)
        print(f"{name:<16}" + "".join(f"{v:>22.1f}" for v in cells)
              + f"{spec:>15.1f}{acc:>11.2f}{100*f1:>10.2f}")

    print()
    print("=" * 96)
    print("reference: the published single-encoder arm at its fixed 0.60 cut")
    print("=" * 96)
    print("  constant 87.2  dormant 93.4  on-off 91.7  position 83.6  "
          "benign 96.1  accuracy 93.8  F 89.4")
    print("  reference: MLP-Trust on the identical 23-dimensional vector "
          "(fusion arm)")
    print("  constant 88.9  dormant 93.9  on-off 92.5  position 84.5  "
          "benign 95.6  accuracy 93.7  F 89.5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
