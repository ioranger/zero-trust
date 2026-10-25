#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from marl_policy import (
    GatedTrustPolicyNet,
    LinearRiskNet,
    MODALITY_CLASSES,
    RiskOnlyNet,
    TrustPolicyNet,
    action_targets,
    baseline_feature_view,
    extract_marl_policy_features,
    feature_blocks,
    heuristic_weight_targets,
    modality_targets,
    resolve_spatial_adjacency,
)
from reference_simulator import load_config, simulate_trust_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the supervised S-TIM multi-head trust model.")
    parser.add_argument("--config", default="artifacts/configs/default.json")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "mps"])
    return parser.parse_args()


def choose_device(value: str):
    import torch

    if value == "cpu":
        return torch.device("cpu")
    if value == "mps":
        return torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def domain_augment(streams: np.ndarray, malicious: np.ndarray, rng) -> np.ndarray:
    """Randomise calibration and residual attack strength on training streams.

    The trace-driven check in the manuscript fails for a concrete reason: on a
    converted packet trace the malicious nodes carry a trust score around 0.69,
    which is further inside the trusted region than anything the training split
    contains, so the network places every attacker on the trusted side. Two
    properties of the training generator cause that. Its per-channel
    calibration is fixed, and its residual attack strength is concentrated by
    the Beta camouflage draw near (1 - camo) ~ 0.4.

    This widens both. Each channel gets an independent gain and offset, so the
    model has to read relative pattern rather than absolute level. Malicious
    nodes get an extra per-node dilution toward the benign profile, so weak
    attacks -- including attacks the generator would otherwise never produce --
    appear in training.

    Applied to training streams only. The evaluation seeds and the ns-3 trace
    are never augmented, so this cannot flatter any reported number; it can
    only change what the model generalises to.
    """
    out = streams.copy()
    n_nodes = streams.shape[1]
    n_ch = streams.shape[2]

    gain = rng.uniform(0.85, 1.15, size=(1, n_nodes, n_ch))
    offset = rng.normal(0.0, 0.015, size=(1, n_nodes, n_ch))
    out[:, :, :4] = out[:, :, :4] * gain[:, :, :4] + offset[:, :, :4]

    # Dilute each malicious node toward the benign reference by a random
    # factor, emulating an attack the generator under-represents.
    dil = rng.uniform(0.0, 1.0, size=n_nodes)
    for node in np.flatnonzero(malicious):
        w = float(dil[node])
        if w <= 0.0:
            continue
        blended = 0.75 * out[:, node, :4] + 0.25 * out[:, node, 4:5]
        out[:, node, :4] = (1.0 - w) * out[:, node, :4] + w * blended

    return np.clip(out, 0.02, 0.98)


def build_dataset(config) -> Tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Return (features, binary labels, attack-modality labels, feature names).

    The modality column is new. It carries simulator-derived attack types that
    the binary risk label cannot express, and it exists so that the multi-head
    network has at least one auxiliary task that is not a restatement of the
    risk label.
    """
    rows = []
    rows_plain = []
    labels = []
    modalities = []
    row_seeds = []
    default_n = int(config.raw["network"]["default_uavs"])
    default_agents = int(config.raw["network"]["default_thinker_agents"])
    augment = bool(config.raw["marl_training"].get("domain_augmentation", False))
    for ratio in config.raw["experiments"]["ratio_grid"]:
        for seed in config.train_seeds:
            streams, malicious, attack_types = simulate_trust_stream(
                config,
                seed=int(seed),
                n_uavs=default_n,
                malicious_ratio=float(ratio),
                n_agents=default_agents,
            )
            if augment:
                # Derive the augmentation stream from the same seed so the
                # augmented dataset is itself reproducible.
                streams = domain_augment(
                    streams, malicious,
                    np.random.default_rng(int(seed) * 31 + int(ratio * 100)))
            adj = resolve_spatial_adjacency(config, int(seed), default_n, float(ratio))
            x, names = extract_marl_policy_features(
                config, streams, default_agents, spatial_adjacency=adj)
            # The baselines are per-node aggregators by construction. They must
            # never be handed the neighbourhood block, or the comparison stops
            # being about architecture and starts being about input width.
            #
            # The fusion-mechanism ablation reverses that on purpose: it feeds
            # the identical feature vector to the linear head, the MLP head and
            # the multi-head policy, so any difference between them comes from
            # how the blocks are combined and not from what was available. The
            # switch is off unless the config asks for it.
            x_plain, names_plain = baseline_feature_view(
                config, streams, default_agents,
                seed=int(seed), n_uavs=default_n, malicious_ratio=float(ratio),
                spatial_adjacency=adj)
            rows.append(x)
            rows_plain.append(x_plain)
            labels.append(malicious.astype(np.float32))
            modalities.append(modality_targets(attack_types))
            row_seeds.append(np.full(default_n, int(seed), dtype=np.int64))
    return (np.vstack(rows).astype(np.float32),
            np.vstack(rows_plain).astype(np.float32),
            np.concatenate(labels).astype(np.float32),
            np.concatenate(modalities),
            np.concatenate(row_seeds),
            names,
            names_plain)


def metric_row(epoch: int, loss: float, y_true: np.ndarray, risk: np.ndarray, threshold: float) -> dict:
    pred = risk > threshold
    y = y_true.astype(bool)
    tp = int(np.sum(pred & y))
    tn = int(np.sum(~pred & ~y))
    fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f_score = 2.0 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "epoch": epoch,
        "loss": loss,
        "accuracy": float((tp + tn) / len(y)),
        "precision": precision,
        "recall": recall,
        "f_score": f_score,
        "false_positive_rate": fpr,
        "mean_risk_malicious": float(risk[y].mean()) if np.any(y) else 0.0,
        "mean_risk_benign": float(risk[~y].mean()) if np.any(~y) else 0.0,
    }


def _focal_bce(logits, target, pos_weight, gamma):
    """Binary focal loss: the same binary cross-entropy, with a per-example
    factor (1 - p_t)^gamma that down-weights the examples the model already
    gets right and up-weights the ones it gets wrong.

    The motivation here is measured, not assumed. In the spatially
    inconsistent scenario the forgers that the published arm misses still carry
    a larger neighbourhood-relative residual than the benign population does
    (1.10 against 0.59 on the standardised features), so their evidence is
    present and the decision boundary, not the representation, is what leaves
    them on the wrong side. The modulating factor moves that boundary towards
    the hard examples without changing the input, the thresholds or the
    generator.

    The published configurations do not set `marl_training.risk_loss`, so they
    keep the plain binary cross-entropy and are bit-for-bit unaffected.
    """
    import torch

    ce = torch.nn.functional.binary_cross_entropy_with_logits(
        logits, target, reduction="none", pos_weight=pos_weight)
    p = torch.sigmoid(logits)
    p_t = p * target + (1.0 - p) * (1.0 - target)
    return (((1.0 - p_t) ** gamma) * ce).mean()


def _risk_loss_factory(mt, device, bce):
    """The risk loss, selected by configuration.

    Returns (callable, kind, gamma). The `bce` branch hands back the very same
    `nn.BCEWithLogitsLoss` object the published path uses, so enabling
    anything else cannot perturb the published runs.
    """
    import torch

    kind = str(mt.get("risk_loss", "bce")).strip().lower()
    if kind == "bce":
        return bce, "bce", None
    if kind == "focal":
        gamma = float(mt.get("focal_gamma", 2.0))
        pos_weight = getattr(bce, "pos_weight", None)
        if pos_weight is None:
            pos_weight = torch.tensor(
                [float(mt["positive_class_weight"])], device=device)

        def focal(logits, target):
            return _focal_bce(logits, target, pos_weight, gamma)

        return focal, "focal", gamma
    raise SystemExit(f"unknown marl_training.risk_loss: {kind!r}")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    outputs = config.outputs
    logs = outputs / "logs"
    checkpoints = outputs / "checkpoints"
    logs.mkdir(parents=True, exist_ok=True)
    checkpoints.mkdir(parents=True, exist_ok=True)

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    seed = int(config.raw.get("base_seed", 0))
    np.random.seed(seed)
    torch.manual_seed(seed)
    (x, x_plain, y, modality_y, row_seeds,
     feature_names, baseline_feature_names) = build_dataset(config)
    mean = x.mean(axis=0)
    std = x.std(axis=0) + 1e-6
    xs = (x - mean) / std
    # Separate normalisation for the per-node baselines.
    mean_plain = x_plain.mean(axis=0)
    std_plain = x_plain.std(axis=0) + 1e-6
    # The risk hint is the average of the five standardised columns that
    # carry the raw level of the two attacked channels. They are selected by
    # name, not by position, so a configuration that disables a factor cannot
    # silently shift the selection onto a different column.
    hint_names = ["1-T1_recent", "1-T4_recent", "1-T1_q10", "1-T4_q10",
                  "T1_T4_positive_slope"]
    name_to_idx = {name: idx for idx, name in enumerate(feature_names)}
    hint_idx = [name_to_idx[n] for n in hint_names if n in name_to_idx]
    risk_hint = xs[:, hint_idx].mean(axis=1) if hint_idx else np.zeros(len(xs))
    risk_hint = 1.0 / (1.0 + np.exp(-risk_hint))
    weight_y = heuristic_weight_targets(x, feature_names).astype(np.float32)
    action_y = action_targets(y.astype(np.int64), risk_hint).astype(np.int64)
    modality_weight = float(config.raw["marl_training"].get("modality_loss_weight", 0.30))
    # Auxiliary-head loss weights. Exposed as configuration so that a control
    # arm can keep the identical TrustPolicyNet encoder and input while
    # switching the auxiliary supervision off, isolating what the multi-head
    # structure itself contributes. The defaults reproduce the previous
    # hard-coded 0.25 / 0.20 / 0.10 exactly.
    weight_loss_weight = float(
        config.raw["marl_training"].get("weight_loss_weight", 0.25))
    action_loss_weight = float(
        config.raw["marl_training"].get("action_loss_weight", 0.20))
    value_loss_weight = float(
        config.raw["marl_training"].get("value_loss_weight", 0.10))

    epochs = int(args.epochs or config.raw["marl_training"]["epochs"])
    batch_size = int(args.batch_size or config.raw["marl_training"]["batch_size"])
    lr = float(config.raw["marl_training"]["learning_rate"])
    threshold = float(config.raw["marl_training"]["decision_threshold"])
    device = choose_device(args.device)

    # Held-out validation split BY SEED, not by row. Rows from one seed share
    # a node assignment and a camouflage draw, so splitting rows would leak
    # node identity across the split. Without this split the network drives
    # training accuracy to 1.000 on 2700 samples, which measures memorisation
    # rather than generalisation and leaves no way to choose a stopping point.
    val_frac = float(config.raw["marl_training"].get("validation_seed_fraction", 0.2))
    unique_seeds = sorted(set(int(s) for s in row_seeds))
    n_val = max(1, int(round(len(unique_seeds) * val_frac)))
    val_seeds = set(unique_seeds[-n_val:])
    is_val = np.array([int(s) in val_seeds for s in row_seeds])
    fit_idx = np.flatnonzero(~is_val)
    val_idx = np.flatnonzero(is_val)

    def make(rows):
        return TensorDataset(
            torch.tensor(xs[rows], dtype=torch.float32),
            torch.tensor(y[rows], dtype=torch.float32),
            torch.tensor(weight_y[rows], dtype=torch.float32),
            torch.tensor(action_y[rows], dtype=torch.long),
            torch.tensor(modality_y[rows], dtype=torch.long),
        )

    fit_loader = DataLoader(
        make(fit_idx), batch_size=batch_size, shuffle=True,
        generator=torch.Generator().manual_seed(seed))
    val_loader = DataLoader(
        make(val_idx), batch_size=batch_size, shuffle=False)
    val_x = torch.tensor(xs[val_idx], dtype=torch.float32, device=device)
    val_y = torch.tensor(y[val_idx], dtype=torch.float32, device=device)

    # The fusion form is a configuration choice, and the default is the
    # published single-encoder model. The block-routed form exists because
    # the measurement in artifacts/analysis/modality_head_cost.py showed the
    # shared encoder's auxiliary supervision costs 8.7 points of
    # constant-attacker detection in the spatial scenario, while costing the
    # feature-matched control nothing.
    fusion = str(config.raw["marl_training"].get("fusion", "single"))
    blocks = None
    if fusion == "gated":
        blocks = feature_blocks(feature_names)
        model = GatedTrustPolicyNet(xs.shape[1], blocks).to(device)
        print(f"block-routed fusion: {[(n, len(i)) for n, i in blocks]}")
    elif fusion == "single":
        model = TrustPolicyNet(input_dim=xs.shape[1]).to(device)
    else:
        raise SystemExit(f"unknown marl_training.fusion: {fusion!r}")
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=float(config.raw["marl_training"]["weight_decay"]))
    bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([float(config.raw["marl_training"]["positive_class_weight"])], device=device))
    risk_loss, risk_loss_kind, focal_gamma = _risk_loss_factory(
        config.raw["marl_training"], device, bce)
    ce = nn.CrossEntropyLoss()
    mse = nn.MSELoss()

    history = []
    x_tensor = torch.tensor(xs, dtype=torch.float32, device=device)
    with torch.no_grad():
        initial = model(x_tensor)
        initial_risk = torch.sigmoid(initial["risk_logit"]).cpu().numpy()
    history.append(metric_row(0, float("nan"), y, initial_risk, threshold))

    best_val = float("inf")
    best_epoch = 0
    best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    val_curve = []

    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        count = 0
        for batch_x, batch_y, batch_w, batch_a, batch_m in fit_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            batch_w = batch_w.to(device)
            batch_a = batch_a.to(device)
            batch_m = batch_m.to(device)
            out = model(batch_x)
            loss_risk = risk_loss(out["risk_logit"], batch_y)
            loss_weight = mse(out["trust_weights"], batch_w)
            loss_action = ce(out["incentive_q"], batch_a)
            # Supervised auxiliary target derived directly from the class label.
            value_target = (1.0 - batch_y) * 0.80 - batch_y * 0.40
            loss_value = mse(out["value"], value_target)
            # Attack-modality supervision. Not derivable from batch_y: constant,
            # dormant and on-off share y=1 but demand different temporal
            # encodings. This is the gradient that can make the shared encoder
            # represent shape rather than level.
            loss_modality = ce(out["modality_q"], batch_m)
            loss = (loss_risk
                    + weight_loss_weight * loss_weight
                    + action_loss_weight * loss_action
                    + value_loss_weight * loss_value
                    + modality_weight * loss_modality)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
            total += float(loss.detach().cpu()) * len(batch_x)
            count += len(batch_x)

        # Validation risk loss drives early stopping. Selecting the checkpoint
        # this way, instead of taking the last epoch, is what stops the network
        # from memorising the training split to a training accuracy of 1.000.
        model.eval()
        with torch.no_grad():
            val_logits = model(val_x)["risk_logit"]
            val_loss = float(risk_loss(val_logits, val_y).detach().cpu())
        val_curve.append((epoch, val_loss))
        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_epoch = epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

        if epoch % max(1, epochs // 20) == 0 or epoch == epochs:
            with torch.no_grad():
                out = model(x_tensor)
                risk = torch.sigmoid(out["risk_logit"]).cpu().numpy()
            history.append(metric_row(epoch, total / max(1, count), y, risk, threshold))

    model.load_state_dict(best_state)
    print(f"early stopping: best epoch {best_epoch} of {epochs} "
          f"(validation risk loss {best_val:.5f})")
    print(f"validation split held out {len(val_seeds)} of {len(unique_seeds)} "
          f"training seeds; {len(val_idx)} node rows")

    model.eval()
    with torch.no_grad():
        final = model(x_tensor)
        final_risk = torch.sigmoid(final["risk_logit"]).cpu().numpy()
        final_weights = final["trust_weights"].cpu().numpy()
        final_actions = final["incentive_q"].argmax(dim=-1).cpu().numpy()
        final_modality = final["modality_q"].argmax(dim=-1).cpu().numpy()
    fit_row = metric_row(best_epoch, float("nan"),
                         y[fit_idx], final_risk[fit_idx], threshold)
    val_row = metric_row(best_epoch, float("nan"),
                         y[val_idx], final_risk[val_idx], threshold)

    # Did the auxiliary heads actually learn anything? A head whose loss weight
    # is zero receives no gradient and stays at its initialisation, so its
    # accuracy collapses to chance. Reporting the accuracy makes "the head
    # participates" a checkable claim instead of an assumption.
    def _head_accuracy(pred, target, idx):
        if len(idx) == 0:
            return float("nan")
        return float((pred[idx] == target[idx]).mean())

    modality_val_acc = _head_accuracy(final_modality, modality_y, val_idx)
    modality_chance = 1.0 / len(MODALITY_CLASSES)
    print(f"modality head validation accuracy: {modality_val_acc:.4f} "
          f"(chance {modality_chance:.4f}, loss weight {modality_weight})")

    checkpoint_rel = Path("artifacts/outputs/checkpoints/stim_marl_policy.pt")
    checkpoint_abs = config.root / checkpoint_rel
    torch.save(
        {
            "model_state": model.cpu().state_dict(),
            "feature_names": feature_names,
            "mean": mean.tolist(),
            "std": std.tolist(),
            "decision_threshold": threshold,
        },
        checkpoint_abs,
    )

    pd.DataFrame(history).to_csv(logs / "marl_training_trace.csv", index=False)
    policy = {
        "policy_type": "pytorch_supervised_multihead",
        "checkpoint_path": str(checkpoint_rel),
        "input_dim": int(xs.shape[1]),
        "feature_names": feature_names,
        "fusion": fusion,
        "feature_blocks": ([[name, [int(i) for i in idx]]
                            for name, idx in blocks] if blocks else []),
        "mean": mean.tolist(),
        "std": std.tolist(),
        "threshold": threshold,
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": lr,
            "device": str(device),
            "train_samples": int(len(y)),
            "train_positive": int(y.sum()),
            "train_negative": int(len(y) - y.sum()),
        },
        "final_training_metrics": metric_row(epochs, float(history[-1]["loss"]), y, final_risk, threshold),
        "selected_epoch": best_epoch,
        "validation_risk_loss": best_val,
        "train_fit_metrics": fit_row,
        "validation_metrics": val_row,
        "validation_seeds": sorted(val_seeds),
        "validation_curve": [{"epoch": e, "val_risk_loss": v} for e, v in val_curve],
        "mean_trust_weights": {
            name: float(value)
            for name, value in zip(["T1", "T2", "T3", "T4", "T5"], final_weights.mean(axis=0))
        },
        "incentive_action_distribution": {
            str(action - 2): int((final_actions == action).sum()) for action in range(5)
        },
        "auxiliary_loss_weights": {
            "risk": 1.0,
            "trust_weights": weight_loss_weight,
            "incentive_action": action_loss_weight,
            "value": value_loss_weight,
            "modality": modality_weight,
        },
        "risk_loss": {
            "kind": risk_loss_kind,
            "focal_gamma": focal_gamma,
            "positive_class_weight": float(
                config.raw["marl_training"]["positive_class_weight"]),
        },
        "modality_supervision": {
            "enabled": modality_weight > 0.0,
            "loss_weight": modality_weight,
            "validation_accuracy": modality_val_acc,
            "chance_accuracy": modality_chance,
            "classes": list(MODALITY_CLASSES),
            "train_distribution": {
                str(MODALITY_CLASSES[i]): int((modality_y == i).sum())
                for i in range(len(MODALITY_CLASSES))
            },
        },
    }
    (logs / "marl_policy.json").write_text(json.dumps(policy, indent=2))
    learned_baselines = train_learned_baselines(
        xs=(x_plain - mean_plain) / std_plain,
        raw_mean=mean_plain,
        raw_std=std_plain,
        y=y,
        config=config,
        logs=logs,
        checkpoints=checkpoints,
        device=device,
        seed=seed,
        threshold=threshold,
        fit_idx=fit_idx,
        val_idx=val_idx,
        val_seeds=val_seeds,
        feature_names=baseline_feature_names,
    )
    (logs / "learned_baselines.json").write_text(json.dumps(learned_baselines, indent=2))
    print(f"Wrote MARL policy checkpoint to {checkpoint_abs}")
    print(f"Wrote training trace to {logs / 'marl_training_trace.csv'}")
    print(f"Wrote learned baseline metadata to {logs / 'learned_baselines.json'}")


def train_learned_baselines(
    xs: np.ndarray,
    raw_mean: np.ndarray,
    raw_std: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    config,
    logs: Path,
    checkpoints: Path,
    device,
    seed: int,
    threshold: float,
    fit_idx: np.ndarray,
    val_idx: np.ndarray,
    val_seeds,
) -> dict:
    """Train stronger supervised baselines on the same train seeds and features.

    These baselines are intentionally risk-only models: they do not use S-TIM's
    auxiliary trust-weight or incentive heads. They provide a stricter check
    that S-TIM's gains are not merely from access to learned diagnostic features.

    Fairness note: these baselines receive exactly the same seed-level
    validation split and the same early-stopping rule as S-TIM. Giving only the
    proposed model a regularisation protocol it controls would hand it an
    advantage that has nothing to do with its architecture, so the comparison
    in the manuscript would be measuring the training procedure rather than
    the model class.
    """

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    x_tensor = torch.tensor(xs, dtype=torch.float32, device=device)
    generator = torch.Generator().manual_seed(seed + 7919)
    pos_weight = torch.tensor([float(config.raw["marl_training"]["positive_class_weight"])], device=device)
    bce = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    risk_loss, risk_loss_kind, focal_gamma = _risk_loss_factory(
        config.raw["marl_training"], device, bce)
    batch_size = int(config.raw["marl_training"]["batch_size"])

    def split_of(rows):
        return (torch.tensor(xs[rows], dtype=torch.float32),
                torch.tensor(y[rows], dtype=torch.float32))

    fx, fy = split_of(fit_idx)
    vx, vy = split_of(val_idx)
    vx_dev = vx.to(device)
    vy_dev = vy.to(device)
    fit_loader = DataLoader(TensorDataset(fx, fy), batch_size=batch_size,
                            shuffle=True, generator=generator)

    baseline_specs = {
        "LR-Trust": ("linear", LinearRiskNet(input_dim=xs.shape[1])),
        "MLP-Trust": ("mlp", RiskOnlyNet(input_dim=xs.shape[1])),
    }
    metadata = {
        "feature_names": feature_names,
        "threshold": threshold,
        "early_stopping": True,
        "validation_seeds": sorted(val_seeds),
        "baselines": {},
    }
    history_rows = []
    for name, (model_type, baseline_model) in baseline_specs.items():
        baseline_model = baseline_model.to(device)
        optimizer = torch.optim.AdamW(
            baseline_model.parameters(),
            lr=float(config.raw["marl_training"]["learning_rate"]),
            weight_decay=float(config.raw["marl_training"]["weight_decay"]),
        )
        epochs = int(config.raw["marl_training"]["epochs"])
        best_val = float("inf")
        best_epoch = 0
        best_state = {k: v.detach().clone() for k, v in baseline_model.state_dict().items()}
        for epoch in range(1, epochs + 1):
            baseline_model.train()
            total = 0.0
            count = 0
            for batch_x, batch_y in fit_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                logits = baseline_model(batch_x)
                loss = risk_loss(logits, batch_y)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(baseline_model.parameters(), 2.0)
                optimizer.step()
                total += float(loss.detach().cpu()) * len(batch_x)
                count += len(batch_x)
            baseline_model.eval()
            with torch.no_grad():
                val_loss = float(risk_loss(baseline_model(vx_dev), vy_dev).detach().cpu())
            if val_loss < best_val - 1e-6:
                best_val = val_loss
                best_epoch = epoch
                best_state = {k: v.detach().clone() for k, v in baseline_model.state_dict().items()}
            if epoch % max(1, epochs // 20) == 0 or epoch == epochs:
                with torch.no_grad():
                    risk = torch.sigmoid(baseline_model(x_tensor)).cpu().numpy()
                row = metric_row(epoch, total / max(1, count), y, risk, threshold)
                row["baseline"] = name
                history_rows.append(row)
        baseline_model.load_state_dict(best_state)
        print(f"{name}: early stopping selected epoch {best_epoch} of {epochs} "
              f"(validation risk loss {best_val:.5f})")
        baseline_model.eval()
        with torch.no_grad():
            risk = torch.sigmoid(baseline_model(x_tensor)).cpu().numpy()
        checkpoint_rel = Path(f"artifacts/outputs/checkpoints/{name.lower().replace('-', '_')}.pt")
        checkpoint_abs = config.root / checkpoint_rel
        torch.save({"model_state": baseline_model.cpu().state_dict()}, checkpoint_abs)
        metadata["baselines"][name] = {
            "model_type": model_type,
            "checkpoint_path": str(checkpoint_rel),
            "input_dim": int(xs.shape[1]),
            # Stored per baseline on purpose. method_predictions standardises
            # with learned[method]["mean"]; a document-level copy would be
            # missed and the proposed model's own statistics would be applied
            # to a comparator that never saw the neighbourhood block.
            #
            # These must be the statistics of the RAW features, not of `xs`.
            # `xs` is already standardised by the caller, so `xs.mean()`/`xs.std()`
            # are 0 and 1 by construction; storing those made inference feed
            # unstandardised features to a model trained on standardised ones.
            "mean": np.asarray(raw_mean, dtype=float).tolist(),
            "std": np.asarray(raw_std, dtype=float).tolist(),
            "feature_names": list(feature_names),
            "threshold": threshold,
            "selected_epoch": best_epoch,
            "validation_risk_loss": best_val,
            # The comparator is trained with the same objective as the proposed
            # model, so that a difference between them is not a difference in
            # the training signal. The published configurations use the plain
            # binary cross-entropy for both.
            "risk_loss": {
                "kind": risk_loss_kind,
                "focal_gamma": focal_gamma,
            },
            "training_metrics": metric_row(best_epoch, float("nan"), y, risk, threshold),
            "train_fit_metrics": metric_row(best_epoch, float("nan"), y[fit_idx], risk[fit_idx], threshold),
            "validation_metrics": metric_row(best_epoch, float("nan"), y[val_idx], risk[val_idx], threshold),
        }
    if history_rows:
        pd.DataFrame(history_rows).to_csv(logs / "learned_baseline_training_trace.csv", index=False)
    return metadata


if __name__ == "__main__":
    main()
