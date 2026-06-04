#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from marl_policy import (
    LinearRiskNet,
    RiskOnlyNet,
    TrustPolicyNet,
    action_targets,
    extract_marl_policy_features,
    heuristic_weight_targets,
)
from reference_simulator import load_config, simulate_trust_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the MTIM PyTorch parameterized-action policy.")
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


def build_dataset(config) -> Tuple[np.ndarray, np.ndarray, list[str]]:
    rows = []
    labels = []
    default_n = int(config.raw["network"]["default_uavs"])
    default_agents = int(config.raw["network"]["default_thinker_agents"])
    for ratio in config.raw["experiments"]["ratio_grid"]:
        for seed in config.train_seeds:
            streams, malicious, _ = simulate_trust_stream(
                config,
                seed=int(seed),
                n_uavs=default_n,
                malicious_ratio=float(ratio),
                n_agents=default_agents,
            )
            x, names = extract_marl_policy_features(config, streams, default_agents)
            rows.append(x)
            labels.append(malicious.astype(np.float32))
    return np.vstack(rows).astype(np.float32), np.concatenate(labels).astype(np.float32), names


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
    x, y, feature_names = build_dataset(config)
    mean = x.mean(axis=0)
    std = x.std(axis=0) + 1e-6
    xs = (x - mean) / std
    risk_hint = xs[:, [0, 2, 4, 5, 10]].mean(axis=1)
    risk_hint = 1.0 / (1.0 + np.exp(-risk_hint))
    weight_y = heuristic_weight_targets(x, feature_names).astype(np.float32)
    action_y = action_targets(y.astype(np.int64), risk_hint).astype(np.int64)

    epochs = int(args.epochs or config.raw["marl_training"]["epochs"])
    batch_size = int(args.batch_size or config.raw["marl_training"]["batch_size"])
    lr = float(config.raw["marl_training"]["learning_rate"])
    threshold = float(config.raw["marl_training"]["decision_threshold"])
    device = choose_device(args.device)

    dataset = TensorDataset(
        torch.tensor(xs, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
        torch.tensor(weight_y, dtype=torch.float32),
        torch.tensor(action_y, dtype=torch.long),
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, generator=generator)

    model = TrustPolicyNet(input_dim=xs.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=float(config.raw["marl_training"]["weight_decay"]))
    bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([float(config.raw["marl_training"]["positive_class_weight"])], device=device))
    ce = nn.CrossEntropyLoss()
    mse = nn.MSELoss()

    history = []
    x_tensor = torch.tensor(xs, dtype=torch.float32, device=device)
    with torch.no_grad():
        initial = model(x_tensor)
        initial_risk = torch.sigmoid(initial["risk_logit"]).cpu().numpy()
    history.append(metric_row(0, float("nan"), y, initial_risk, threshold))

    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        count = 0
        for batch_x, batch_y, batch_w, batch_a in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            batch_w = batch_w.to(device)
            batch_a = batch_a.to(device)
            out = model(batch_x)
            loss_risk = bce(out["risk_logit"], batch_y)
            loss_weight = mse(out["trust_weights"], batch_w)
            loss_action = ce(out["incentive_q"], batch_a)
            # TD-style auxiliary value target: high value for correct benign service,
            # low value for high-risk malicious assignments.
            value_target = (1.0 - batch_y) * 0.80 - batch_y * 0.40
            loss_value = mse(out["value"], value_target)
            loss = loss_risk + 0.25 * loss_weight + 0.20 * loss_action + 0.10 * loss_value
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
            total += float(loss.detach().cpu()) * len(batch_x)
            count += len(batch_x)

        if epoch % max(1, epochs // 20) == 0 or epoch == epochs:
            model.eval()
            with torch.no_grad():
                out = model(x_tensor)
                risk = torch.sigmoid(out["risk_logit"]).cpu().numpy()
            history.append(metric_row(epoch, total / max(1, count), y, risk, threshold))

    model.eval()
    with torch.no_grad():
        final = model(x_tensor)
        final_risk = torch.sigmoid(final["risk_logit"]).cpu().numpy()
        final_weights = final["trust_weights"].cpu().numpy()
        final_actions = final["incentive_q"].argmax(dim=-1).cpu().numpy()

    checkpoint_rel = Path("artifacts/outputs/checkpoints/mtim_marl_policy.pt")
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
        "policy_type": "pytorch_parameterized_action",
        "checkpoint_path": str(checkpoint_rel),
        "input_dim": int(xs.shape[1]),
        "feature_names": feature_names,
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
        "mean_trust_weights": {
            name: float(value)
            for name, value in zip(["T1", "T2", "T3", "T4", "T5"], final_weights.mean(axis=0))
        },
        "incentive_action_distribution": {
            str(action - 2): int((final_actions == action).sum()) for action in range(5)
        },
    }
    (logs / "marl_policy.json").write_text(json.dumps(policy, indent=2))
    learned_baselines = train_learned_baselines(
        xs=xs,
        y=y,
        feature_names=feature_names,
        config=config,
        logs=logs,
        checkpoints=checkpoints,
        device=device,
        seed=seed,
        threshold=threshold,
    )
    (logs / "learned_baselines.json").write_text(json.dumps(learned_baselines, indent=2))
    print(f"Wrote MARL policy checkpoint to {checkpoint_abs}")
    print(f"Wrote training trace to {logs / 'marl_training_trace.csv'}")
    print(f"Wrote learned baseline metadata to {logs / 'learned_baselines.json'}")


def train_learned_baselines(
    xs: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    config,
    logs: Path,
    checkpoints: Path,
    device,
    seed: int,
    threshold: float,
) -> dict:
    """Train stronger supervised baselines on the same train seeds and features.

    These baselines are intentionally risk-only models: they do not use MTIM's
    auxiliary trust-weight or incentive heads. They provide a stricter check
    that MTIM's gains are not merely from access to learned diagnostic features.
    """

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    x_tensor = torch.tensor(xs, dtype=torch.float32, device=device)
    dataset = TensorDataset(torch.tensor(xs, dtype=torch.float32), torch.tensor(y, dtype=torch.float32))
    generator = torch.Generator().manual_seed(seed + 7919)
    loader = DataLoader(dataset, batch_size=int(config.raw["marl_training"]["batch_size"]), shuffle=True, generator=generator)
    pos_weight = torch.tensor([float(config.raw["marl_training"]["positive_class_weight"])], device=device)
    bce = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    baseline_specs = {
        "LR-Trust": ("linear", LinearRiskNet(input_dim=xs.shape[1])),
        "MLP-Trust": ("mlp", RiskOnlyNet(input_dim=xs.shape[1])),
    }
    metadata = {
        "feature_names": feature_names,
        "threshold": threshold,
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
        for epoch in range(1, epochs + 1):
            baseline_model.train()
            total = 0.0
            count = 0
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                logits = baseline_model(batch_x)
                loss = bce(logits, batch_y)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(baseline_model.parameters(), 2.0)
                optimizer.step()
                total += float(loss.detach().cpu()) * len(batch_x)
                count += len(batch_x)
            if epoch % max(1, epochs // 20) == 0 or epoch == epochs:
                baseline_model.eval()
                with torch.no_grad():
                    risk = torch.sigmoid(baseline_model(x_tensor)).cpu().numpy()
                row = metric_row(epoch, total / max(1, count), y, risk, threshold)
                row["baseline"] = name
                history_rows.append(row)
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
            "threshold": threshold,
            "training_metrics": metric_row(epochs, float(history_rows[-1]["loss"]), y, risk, threshold),
        }
    if history_rows:
        pd.DataFrame(history_rows).to_csv(logs / "learned_baseline_training_trace.csv", index=False)
    return metadata


if __name__ == "__main__":
    main()
