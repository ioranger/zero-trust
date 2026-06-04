#!/usr/bin/env python3
"""PyTorch policy components for the MTIM artifact.

The network is intentionally compact so the artifact can be trained on a
workstation, but it preserves the paper's parameterized-action structure:
continuous trust-factor weights and discrete incentive actions share an encoder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np

from reference_simulator import Config, extract_policy_features


MARL_EXTRA_FEATURES: list[str] = []


def extract_marl_policy_features(config: Config, streams: np.ndarray, n_agents: int) -> Tuple[np.ndarray, list[str]]:
    """Return per-node MTIM features augmented with thinker-agent context."""

    base = extract_policy_features(config, streams)
    features = base
    names = [
        "1-T1_recent",
        "1-T2_recent",
        "1-T4_recent",
        "1-T5_recent",
        "1-T1_q10",
        "1-T4_q10",
        "low_T1_T4_fraction_0.58",
        "low_T1_T4_fraction_0.62",
        "T1_T4_amplitude",
        "T1_T4_std",
        "T1_T4_positive_slope",
        "directed_T2T3_minus_T1T4_gap",
        "directed_low_quantile_gap",
        *MARL_EXTRA_FEATURES,
    ]
    return features, names


def heuristic_weight_targets(features: np.ndarray, names: Iterable[str]) -> np.ndarray:
    """Derive soft trust-factor weight targets for the auxiliary policy head."""

    name_to_idx = {name: idx for idx, name in enumerate(names)}
    weakness = np.column_stack(
        [
            features[:, name_to_idx["1-T1_recent"]] + features[:, name_to_idx["1-T1_q10"]],
            features[:, name_to_idx["1-T2_recent"]],
            np.full(features.shape[0], 0.15),
            features[:, name_to_idx["1-T4_recent"]] + features[:, name_to_idx["1-T4_q10"]],
            features[:, name_to_idx["1-T5_recent"]],
        ]
    )
    weakness[:, 2] += 0.25 * features[:, name_to_idx["directed_T2T3_minus_T1T4_gap"]]
    weakness = np.maximum(weakness, 0.05)
    return weakness / weakness.sum(axis=1, keepdims=True)


def action_targets(labels: np.ndarray, risk_hint: np.ndarray) -> np.ndarray:
    """Map labels to the five incentive bins {-2,-1,0,1,2} as indices 0..4."""

    targets = np.full(len(labels), 2, dtype=np.int64)
    targets[(labels == 1) & (risk_hint >= 0.65)] = 0
    targets[(labels == 1) & (risk_hint < 0.65)] = 1
    targets[(labels == 0) & (risk_hint <= 0.35)] = 4
    targets[(labels == 0) & (risk_hint > 0.35)] = 3
    return targets


def load_torch_policy(policy: Dict[str, object], root: Path):
    """Load a saved PyTorch policy lazily."""

    import torch

    checkpoint_path = Path(str(policy["checkpoint_path"]))
    if not checkpoint_path.is_absolute():
        checkpoint_path = root / checkpoint_path
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model = TrustPolicyNet(input_dim=int(policy["input_dim"]))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model


def load_torch_risk_baseline(metadata: Dict[str, object], root: Path):
    """Load a saved learned baseline risk model lazily."""

    import torch

    checkpoint_path = Path(str(metadata["checkpoint_path"]))
    if not checkpoint_path.is_absolute():
        checkpoint_path = root / checkpoint_path
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model_type = str(metadata["model_type"])
    input_dim = int(metadata["input_dim"])
    if model_type == "linear":
        model = LinearRiskNet(input_dim=input_dim)
    elif model_type == "mlp":
        model = RiskOnlyNet(input_dim=input_dim)
    else:
        raise ValueError(f"Unknown learned baseline model_type: {model_type}")
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model


class LinearRiskNet:
    def __new__(cls, input_dim: int):
        import torch
        from torch import nn

        class _LinearRiskNet(nn.Module):
            def __init__(self, in_dim: int):
                super().__init__()
                self.linear = nn.Linear(in_dim, 1)

            def forward(self, x):
                return self.linear(x).squeeze(-1)

        return _LinearRiskNet(input_dim)


class RiskOnlyNet:
    def __new__(cls, input_dim: int, hidden: int = 64):
        import torch
        from torch import nn

        class _RiskOnlyNet(nn.Module):
            def __init__(self, in_dim: int, hidden_dim: int):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Linear(in_dim, hidden_dim),
                    nn.LayerNorm(hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, 1),
                )

            def forward(self, x):
                return self.net(x).squeeze(-1)

        return _RiskOnlyNet(input_dim, hidden)


class TrustPolicyNet:  # factory wrapper to avoid importing torch at module import time
    def __new__(cls, input_dim: int, hidden: int = 96):
        import torch
        from torch import nn

        class _TrustPolicyNet(nn.Module):
            def __init__(self, in_dim: int, hidden_dim: int):
                super().__init__()
                self.encoder = nn.Sequential(
                    nn.Linear(in_dim, hidden_dim),
                    nn.LayerNorm(hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                )
                self.risk_head = nn.Linear(hidden_dim, 1)
                self.weight_head = nn.Linear(hidden_dim, 5)
                self.incentive_head = nn.Linear(hidden_dim, 5)
                self.value_head = nn.Linear(hidden_dim, 1)

            def forward(self, x):
                h = self.encoder(x)
                return {
                    "risk_logit": self.risk_head(h).squeeze(-1),
                    "trust_weights": torch.softmax(self.weight_head(h), dim=-1),
                    "incentive_q": self.incentive_head(h),
                    "value": self.value_head(h).squeeze(-1),
                }

        return _TrustPolicyNet(input_dim, hidden)
