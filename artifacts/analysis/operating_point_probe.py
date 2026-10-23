"""The spatial scenario at a matched benign false-positive rate.

The main table compares every method at one fixed cut, 0.60. That is only a
fair comparison if the methods put the cut at the same point of their score
distributions, and the block-routed arm shows they do not: its marginal
specialist alone detects 96.9% of constant attackers at a 17.8% benign false
positive rate, so its scores are far more spread out than the mixture's. A
fixed cut therefore compares two operating points rather than two detectors.

This probe switches to the operating point the manuscript already uses in its
probe-level section: each method's cut is chosen on the arm's held-out
validation seeds as the upper quantile of the benign scores, at a 5% benign
false positive rate, and is then applied unchanged to the evaluation seeds.
The rule is applied to every method alike, so it cannot favour one of them.

The probe also scores the gated arm's individual branches, to separate "the
information is there and the routing wastes it" from "the information is not
there".

Nothing is trained here and no published number is changed. Every rate is
computed from the generator's own seeds and the arms' own checkpoints.

    python -u artifacts/analysis/operating_point_probe.py
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

GATED = ROOT / "artifacts" / "runs" / "spatial_position_gated"
GATED_CONFIG = ROOT / "artifacts" / "configs" / "spatial_position_gated.json"
SINGLE = ROOT / "artifacts" / "runs" / "spatial_position_23dim"
SINGLE_CONFIG = ROOT / "artifacts" / "configs" / "spatial_position.json"
MARGINAL = ROOT / "artifacts" / "runs" / "spatial_position_13dim"
MARGINAL_CONFIG = ROOT / "artifacts" / "configs" / "spatial_position_13dim.json"
EVAL_SEEDS = list(range(1000, 1019))
FPR_TARGET = 0.05
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]
SCORERS = ["S-TIM", "S-TIM marginal branch", "S-TIM shape branch",
           "S-TIM neighborhood branch", "MLP-Trust"]


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """AUC of the scores separating `pos` from `neg`, rank based with tie
    averaging."""
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(order.size, dtype=float)
    ranks[order] = np.arange(1, order.size + 1)
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            ranks[order[m]] = ranks[order[m]].mean()
    return float((ranks[:pos.size].sum() - pos.size * (pos.size + 1) / 2) /
                 (pos.size * neg.size))


def collect(arm: Path, config_path: Path, eval_seeds: list[int]):
    """Simulate the seeds once and return every scorer's per-node scores."""
    import torch

    cfg = rs.load_config(str(config_path))
    policy = json.loads((arm / "logs" / "marl_policy.json").read_text(encoding="utf-8"))
    policy["checkpoint_path"] = str(arm / "checkpoints" / "stim_marl_policy.pt")
    learned = policy.get("learned_baselines", {}).get("baselines", {})
    if not learned:
        # The evaluation harness attaches the baseline metadata from the
        # separate log; the policy file alone does not carry it.
        bl_path = arm / "logs" / "learned_baselines.json"
        if bl_path.exists():
            policy["learned_baselines"] = json.loads(
                bl_path.read_text(encoding="utf-8"))
            learned = policy["learned_baselines"].get("baselines", {})
    for _name, meta in learned.items():
        meta["checkpoint_path"] = str(arm / "checkpoints" /
                                      Path(str(meta["checkpoint_path"])).name)

    gated = str(policy.get("fusion", "single")) == "gated"
    model = mp.load_torch_policy(policy, ROOT)
    model.eval()
    mlp_meta = learned.get("MLP-Trust")
    mlp_model = None
    if mlp_meta is not None:
        mlp_model = mp.load_torch_risk_baseline(mlp_meta, ROOT)

    mean = np.array(policy["mean"], dtype=float)
    std = np.array(policy["std"], dtype=float)
    block_names = [str(b[0]) for b in policy.get("feature_blocks", [])]
    block_idx = [np.asarray(b[1], dtype=int) for b in policy.get("feature_blocks", [])]

    n_uavs = int(cfg.raw["network"]["default_uavs"])
    n_agents = int(cfg.raw["network"]["default_thinker_agents"])
    ratio = float(cfg.raw["experiments"]["main_ratio"])
    val_seeds = [int(s) for s in (policy.get("validation_seeds") or [])]

    out = {"val": [], "eval": []}

    def one_seed(seed: int, bucket: str):
        streams, malicious, attack_types = rs.simulate_trust_stream(
            cfg, seed, n_uavs=n_uavs, malicious_ratio=ratio, n_agents=n_agents)
        adj = mp.resolve_spatial_adjacency(cfg, seed, n_uavs, ratio)
        x, _ = mp.extract_marl_policy_features(cfg, streams, n_agents,
                                               spatial_adjacency=adj)
        xs = (x - mean) / std
        xt = torch.tensor(xs, dtype=torch.float32)
        with torch.no_grad():
            res = model(xt)
            scores = {"S-TIM": torch.sigmoid(res["risk_logit"]).numpy()}
            if gated:
                embs = [enc(xt[:, idx]) for enc, idx in zip(model.encoders, block_idx)]
                logits = np.stack(
                    [head(e).squeeze(-1).numpy() for head, e in
                     zip(model.risk_heads, embs)], axis=-1)
                for bi, bname in enumerate(block_names):
                    scores[f"S-TIM {bname} branch"] = 1.0 / (1.0 + np.exp(-logits[:, bi]))
        if mlp_model is not None:
            xb, _ = mp.baseline_feature_view(
                cfg, streams, n_agents, seed=seed, n_uavs=n_uavs,
                malicious_ratio=ratio)
            bmean = np.array(mlp_meta.get("mean", mean), dtype=float)
            bstd = np.array(mlp_meta.get("std", std), dtype=float)
            bxs = (xb - bmean) / bstd
            with torch.no_grad():
                scores["MLP-Trust"] = torch.sigmoid(
                    mlp_model(torch.tensor(bxs, dtype=torch.float32))).numpy()
        out[bucket].append((scores, np.asarray(attack_types, dtype=object),
                            np.asarray(malicious, dtype=bool)))

    for s in val_seeds:
        one_seed(s, "val")
    for s in eval_seeds:
        one_seed(s, "eval")
    return out, val_seeds


def report(name: str, data: dict) -> None:
    if not data["val"] or not data["eval"]:
        return
    benign_val = np.concatenate([
        sc[name][np.asarray(t, dtype=object) == "benign"]
        for sc, t, _m in data["val"]])
    thr = float(np.quantile(benign_val, 1.0 - FPR_TARGET))
    fixed = 0.60

    benign_eval = np.concatenate([
        sc[name][~m] for sc, _t, m in data["eval"]])
    benign_spec_matched = 100.0 * (1.0 - float((benign_eval > thr).mean()))
    benign_spec_fixed = 100.0 * (1.0 - float((benign_eval > fixed).mean()))

    print()
    print(f"--- {name} ---")
    print(f"{'attack class':>22}{'at 5% FPR':>14}{'at fixed 0.60':>16}"
          f"{'AUC vs benign':>16}{'n nodes':>10}")
    print("-" * 78)
    for c in CLASSES:
        # The arms' own tables report the mean over seeds of the per-seed
        # rate, not the rate over pooled nodes, so this probe does the same.
        per_seed_m, per_seed_f = [], []
        pooled = []
        for sc, t, _m in data["eval"]:
            mask = np.asarray(t, dtype=object) == c
            s = sc[name][mask]
            pooled.append(s)
            per_seed_m.append(float((s > thr).mean()))
            per_seed_f.append(float((s > fixed).mean()))
        pooled = np.concatenate(pooled)
        det_m = 100.0 * float(np.mean(per_seed_m))
        det_f = 100.0 * float(np.mean(per_seed_f))
        print(f"{c:>22}{det_m:>14.1f}{det_f:>16.1f}"
              f"{auc(pooled, benign_eval):>16.3f}{pooled.size:>10}")
    print(f"{'benign (specificity)':>22}{benign_spec_matched:>14.1f}"
          f"{benign_spec_fixed:>16.1f}{'':>16}{benign_eval.size:>10}")

    # aggregate metrics at the two operating points
    for label, thr_use in (("at 5% FPR", thr), ("at fixed 0.60", fixed)):
        tp = fp = fn = tn = 0
        for sc, _t, mal in data["eval"]:
            pred = sc[name] > thr_use
            tp += int((pred & mal).sum())
            fp += int((pred & ~mal).sum())
            fn += int((~pred & mal).sum())
            tn += int((~pred & ~mal).sum())
        acc = 100.0 * (tp + tn) / max(tp + fp + fn + tn, 1)
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-12)
        print(f"    aggregate {label:<16} accuracy {acc:6.2f}   precision {prec:6.3f}"
              f"   recall {rec:6.3f}   F-score {100*f1:6.2f}")


def main() -> int:
    print("=" * 104)
    print("MATCHED OPERATING POINT -- threshold chosen on held-out validation seeds at 5% benign FPR")
    print("=" * 104)

    for arm, cfg_path, label in (
            (MARGINAL, MARGINAL_CONFIG, "spatial_position_13dim (marginal only)"),
            (SINGLE, SINGLE_CONFIG, "spatial_position_23dim (published, single encoder)"),
            (GATED, GATED_CONFIG, "spatial_position_gated (block routed)")):
        if not (arm / "logs" / "marl_policy.json").exists():
            print(f"!! missing arm {arm}")
            continue
        data, val_seeds = collect(arm, cfg_path, EVAL_SEEDS)
        print()
        print("#" * 104)
        print(f"# {label}   (validation seeds: {len(val_seeds)}, "
              f"evaluation seeds: {EVAL_SEEDS})")
        print("#" * 104)
        for scorer in SCORERS:
            if scorer not in data["eval"][0][0]:
                continue
            report(scorer, data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
