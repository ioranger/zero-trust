#!/usr/bin/env python3
"""PyTorch components for the supervised S-TIM trust-stream artifact.

The auxiliary factor-weight, action-class, and value heads share an encoder with
the risk classifier.  Their targets are supervised or heuristic; this module
does not implement reinforcement learning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np

from reference_simulator import Config, extract_policy_features


MARL_EXTRA_FEATURES: list[str] = []

# --- temporal-shape block -------------------------------------------------
# The 13 base features are all marginal / quantile / trend aggregates over a
# fixed trailing window. None of them can express autocorrelation or
# transition structure, so a node that switches on and off on a schedule is
# summarised exactly like a node that is merely noisy.
#
# The attack period is deliberately NOT encoded anywhere here: no lag of 45
# or 90 appears, and every statistic below is scale-free. The model is free
# to pick whatever resolution it needs.
#
# Enabled per config via marl_training.shape_features, so the published
# 13-feature artifact stays exactly reproducible.
SHAPE_FEATURE_NAMES: list[str] = [
    "shape_acf_excess",
    "shape_acf_prominence",
    "shape_flip_rate",
    "shape_two_level",
    "shape_switch_cv",
]

_SHAPE_ATTACK_CHANNELS = (0, 3)   # T1 and T4
_SHAPE_ACF_MIN_LAG = 3
_SHAPE_ACF_MAX_LAG = 120


def _shape_acf_batch(x: np.ndarray, max_lag: int) -> np.ndarray:
    """Autocorrelation of every row of x, computed together.

    x is (n_series, n_steps). Returns (n_series, max_lag + 1) with lag 0 at
    column 0. An FFT convolution replaces the direct per-lag dot products; the
    two agree to ~1e-13, which is summation order rather than a difference in
    what is measured.
    """
    n_steps = x.shape[1]
    nfft = 1 << (2 * n_steps - 1).bit_length()
    z = x - x.mean(axis=1, keepdims=True)
    spec = np.fft.rfft(z, n=nfft, axis=1)
    acov = np.fft.irfft(spec * np.conjugate(spec), n=nfft, axis=1)[:, :n_steps]
    return acov / np.maximum(acov[:, :1], 1e-300)


def shape_features(x: np.ndarray) -> np.ndarray:
    """Five scale-free statistics describing the SHAPE of one channel."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < _SHAPE_ACF_MAX_LAG + 2:
        return np.zeros(len(SHAPE_FEATURE_NAMES))

    acf = _shape_acf_batch(x[None, :], _SHAPE_ACF_MAX_LAG)[0]
    a1 = acf[1]
    lags = range(_SHAPE_ACF_MIN_LAG, min(_SHAPE_ACF_MAX_LAG, n - 1))
    excess = acf[list(lags)] - a1

    s = np.sign(np.diff(x))
    flips = s[1:] * s[:-1] < 0
    flip_rate = float(flips.mean()) if flips.size else 0.0

    idx = np.flatnonzero(flips)
    switch_cv = 0.0
    if idx.size >= 3:
        gaps = np.diff(idx).astype(float)
        if gaps.mean() > 0.0:
            switch_cv = float(gaps.std() / gaps.mean())

    q05, q25, q75, q95 = np.quantile(x, [0.05, 0.25, 0.75, 0.95])
    span = q95 - q05
    two_level = float((q75 - q25) / span) if span > 0.0 else 0.0

    return np.array([
        float(np.mean(np.abs(excess))),
        float(np.max(np.abs(excess))),
        flip_rate,
        two_level,
        switch_cv,
    ])


def extract_shape_features(config: Config, streams: np.ndarray) -> np.ndarray:
    """Per-node shape statistics, averaged over the attacked channels.

    ``streams`` is (steps, n_uavs, channels); the returned block is
    (n_uavs, 5). Each node is scored on its own time series, so a node's
    shape is never mixed with its neighbours'.
    """
    post = streams[config.warmup_steps :]
    n_nodes = post.shape[1]
    per_channel = []
    for ch in _SHAPE_ATTACK_CHANNELS:
        per_channel.append(
            np.array([shape_features(post[:, node, ch]) for node in range(n_nodes)])
        )
    return np.mean(np.stack(per_channel, axis=0), axis=0)


def shape_features_enabled(config: Config) -> bool:
    return bool(config.raw.get("marl_training", {}).get("shape_features", False))


SPATIAL_FEATURE_NAMES: list[str] = [
    "spatial_dev_T1",
    "spatial_dev_T4",
    "spatial_gap_dev",
    "spatial_rel_dev",
    "spatial_std_dev",
]

# --- factor ablation -------------------------------------------------------
# Which trust factor every feature column is computed from. This mapping is
# what makes a leave-one-factor-out control possible: dropping a factor
# removes exactly the columns that carry information about it, and nothing
# else about the run changes.
#
# The two directed cross-factor gaps read the channels as
# (T2 + T3) - (T1 + T4), so each of them depends on four factors and both of
# them disappear as soon as any one of those four is removed.
FEATURE_FACTORS: dict[str, tuple[str, ...]] = {
    "1-T1_recent": ("T1",),
    "1-T2_recent": ("T2",),
    "1-T4_recent": ("T4",),
    "1-T5_recent": ("T5",),
    "1-T1_q10": ("T1",),
    "1-T4_q10": ("T4",),
    "low_T1_T4_fraction_0.58": ("T1", "T4"),
    "low_T1_T4_fraction_0.62": ("T1", "T4"),
    "T1_T4_amplitude": ("T1", "T4"),
    "T1_T4_std": ("T1", "T4"),
    "T1_T4_positive_slope": ("T1", "T4"),
    "directed_T2T3_minus_T1T4_gap": ("T1", "T2", "T3", "T4"),
    "directed_low_quantile_gap": ("T1", "T2", "T3", "T4"),
    # the temporal-shape block is computed on T1 and T4
    **{name: ("T1", "T4") for name in SHAPE_FEATURE_NAMES},
    # the neighbourhood block is computed on T1 and T4
    **{name: ("T1", "T4") for name in SPATIAL_FEATURE_NAMES},
}


def disabled_factors(config: Config) -> list[str]:
    """The trust factors the configuration asks the model not to see.

    Off by default: the published configuration consumes every factor, and
    only the leave-one-factor-out control switches it on.
    """
    raw = (config.raw.get("marl_training", {}) or {}).get("disabled_factors", []) or []
    return [str(f) for f in raw]


def factor_keep_mask(names: list[str], disabled: list[str]) -> np.ndarray:
    """Keep a column unless it carries information about a disabled factor."""
    if not disabled:
        return np.ones(len(names), dtype=bool)
    keep = []
    for name in names:
        factors = FEATURE_FACTORS.get(name)
        keep.append(True if factors is None
                    else not any(f in factors for f in disabled))
    return np.array(keep, dtype=bool)


def disabled_features(config: Config) -> list[str]:
    """Feature columns the configuration asks the model not to see.

    Off by default. The factor-level control removes everything a dimension
    carries; this one removes named columns, which is what a diagnostic on a
    single mechanism needs.
    """
    raw = (config.raw.get("marl_training", {}) or {}).get("disabled_features", []) or []
    return [str(f) for f in raw]


def spatial_features_enabled(config: Config) -> bool:
    return bool((config.raw.get("spatial") or {}).get("features", False))


def baselines_get_spatial_block(config: Config) -> bool:
    """Whether the learned per-node baselines are also handed the neighbourhood block.

    The main comparison protocol keeps the neighbourhood block away from LR-Trust
    and MLP-Trust, because they are per-node aggregators by construction and
    handing them a neighbourhood-relative feature would make the comparison
    about input width rather than about architecture.

    A fusion-mechanism ablation needs the opposite: the *same* feature vector
    fed to three different fusion mechanisms, so that any difference is
    attributable to how the blocks are combined rather than to what was
    available. That arm switches this on explicitly, is labelled as a control
    of the proposed model, and never touches the published configuration.
    """
    return bool((config.raw.get("fairness") or {}).get(
        "learned_baselines_get_spatial_block", False))


def resolve_spatial_adjacency(config: Config, seed: int, n_uavs: int,
                              malicious_ratio: float):
    """Neighbourhood matrix for this seed, or None when spatial is off.

    Returns None when the generator is disabled *or* when the feature block is
    switched off. Both gates are required: `spatial.features=false` is meant to
    be a true ablation of the neighbourhood block, with the generator otherwise
    unchanged. Gating only on `enabled` made the ablation a byte-for-byte copy
    of the full configuration, because the training path always received an
    adjacency and S-TIM stayed at 23 features either way.
    """
    from reference_simulator import spatial_cfg, spatial_geometry
    if not spatial_cfg(config):
        return None
    if not spatial_features_enabled(config):
        return None
    _, A, _, _, _, _, _ = spatial_geometry(config, int(seed), int(n_uavs),
                                      float(malicious_ratio))
    return A


def extract_marl_policy_features(
    config: Config,
    streams: np.ndarray,
    n_agents: int,
    use_shape: bool | None = None,
    spatial_adjacency=None,
) -> Tuple[np.ndarray, list[str]]:
    """Return per-node S-TIM features.

    ``n_agents`` is retained for API compatibility but is not currently used.
    Consequently, the artifact does not learn an agent-count or local-agent
    context effect.

    ``use_shape`` overrides the config flag. Inference passes it explicitly so
    a checkpoint trained with the temporal-shape block is always scored with
    the feature width it was trained on.
    """
    if use_shape is None:
        use_shape = shape_features_enabled(config)
    base = extract_policy_features(config, streams)
    blocks = []
    extras = []
    if use_shape:
        blocks.append(extract_shape_features(config, streams))
        extras.extend(SHAPE_FEATURE_NAMES)
    if spatial_adjacency is not None:
        from reference_simulator import extract_spatial_features
        blocks.append(extract_spatial_features(config, streams, spatial_adjacency))
        extras.extend(SPATIAL_FEATURE_NAMES)
    features = np.hstack([base] + blocks) if blocks else base
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
        *(extras if extras else MARL_EXTRA_FEATURES),
    ]
    # The leave-one-factor-out control removes the columns that carry
    # information about a factor the configuration disables. The mask is
    # applied here, in the one function that both training and inference go
    # through, so the two cannot disagree about the input width.
    disabled = disabled_factors(config)
    if disabled:
        keep = factor_keep_mask(names, disabled)
        features = features[:, keep]
        names = [n for n, k in zip(names, keep) if k]
    # The column-level control removes named columns only, which is what a
    # diagnostic on one mechanism needs: the factor control removes everything
    # a dimension carries, this one leaves the rest of the dimension in place.
    off = disabled_features(config)
    if off:
        keep = np.array([n not in off for n in names])
        features = features[:, keep]
        names = [n for n, k in zip(names, keep) if k]
    return features, names


def baseline_feature_view(
    config: Config,
    streams: np.ndarray,
    n_agents: int,
    seed: int | None = None,
    n_uavs: int | None = None,
    malicious_ratio: float | None = None,
    spatial_adjacency=None,
) -> Tuple[np.ndarray, list[str]]:
    """The feature matrix the learned per-node baselines are scored on.

    One code path for both training and inference, so the width a baseline was
    trained at is necessarily the width it is scored at.

    With the switch off (the published protocol) the neighbourhood block is
    withheld, so the baselines stay per-node aggregators. With the switch on
    the baseline sees exactly the vector the proposed model sees, which is what
    the fusion-mechanism ablation needs.

    Note that ``spatial_adjacency`` is *ignored* when the switch is off. The
    caller may hold a non-None adjacency for the proposed model; handing that
    same matrix to the baselines would silently move the published protocol,
    so the switch is the only thing that may widen the baseline input.
    """
    adj = None
    if baselines_get_spatial_block(config):
        adj = spatial_adjacency
        if (adj is None and seed is not None and n_uavs is not None
                and malicious_ratio is not None):
            adj = resolve_spatial_adjacency(
                config, int(seed), int(n_uavs), float(malicious_ratio))
    return extract_marl_policy_features(
        config, streams, n_agents, spatial_adjacency=adj)


def heuristic_weight_targets(features: np.ndarray, names: Iterable[str]) -> np.ndarray:
    """Derive soft trust-factor weight targets for the auxiliary policy head.

    A column that the configuration has disabled is read as zero, so the
    factor it belonged to is treated as carrying no evidence rather than as
    making the target undefined.
    """

    name_to_idx = {name: idx for idx, name in enumerate(names)}

    def col(name: str, default: float = 0.0) -> np.ndarray:
        idx = name_to_idx.get(name)
        if idx is None:
            return np.full(features.shape[0], default)
        return features[:, idx]

    weakness = np.column_stack(
        [
            col("1-T1_recent") + col("1-T1_q10"),
            col("1-T2_recent"),
            np.full(features.shape[0], 0.15),
            col("1-T4_recent") + col("1-T4_q10"),
            col("1-T5_recent"),
        ]
    )
    weakness[:, 2] += 0.25 * col("directed_T2T3_minus_T1T4_gap")
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


MODALITY_CLASSES = ("benign", "constant", "dormant", "on-off")
MODALITY_INDEX = {name: i for i, name in enumerate(MODALITY_CLASSES)}


def modality_targets(attack_types) -> np.ndarray:
    """Map simulator attack types to class indices 0..3.

    This is the one auxiliary target in the network that is NOT a function of
    the binary risk label. constant, dormant and on-off all carry y = 1, so the
    risk head cannot express the difference between them; a modality head can,
    and the gradient it sends to the shared encoder forces the representation
    to encode temporal pattern rather than level. That is the entire reason a
    multi-head network can be expected to beat a single BCE head here.
    """
    out = np.empty(len(attack_types), dtype=np.int64)
    for i, at in enumerate(attack_types):
        key = str(at).strip().lower()
        out[i] = MODALITY_INDEX.get(key, MODALITY_INDEX["benign"])
    return out


def load_torch_policy(policy: Dict[str, object], root: Path):
    """Load a saved PyTorch policy lazily."""

    import torch

    checkpoint_path = Path(str(policy["checkpoint_path"]))
    if not checkpoint_path.is_absolute():
        checkpoint_path = root / checkpoint_path
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if str(policy.get("fusion", "single")) == "gated":
        blocks = [(str(name), np.asarray(idx, dtype=int))
                  for name, idx in policy["feature_blocks"]]
        model = GatedTrustPolicyNet(input_dim=int(policy["input_dim"]),
                                    blocks=blocks)
    else:
        model = TrustPolicyNet(input_dim=int(policy["input_dim"]))
    # strict=False keeps checkpoints trained before the modality head existed
    # loadable; the missing head is simply not consumed at inference.
    model.load_state_dict(checkpoint["model_state"], strict=False)
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
                # Auxiliary head whose target is NOT recoverable from the binary
                # risk label. See modality_targets for why this is the only head
                # that can change what the shared encoder represents.
                self.modality_head = nn.Linear(hidden_dim, len(MODALITY_CLASSES))

            def forward(self, x):
                h = self.encoder(x)
                return {
                    "risk_logit": self.risk_head(h).squeeze(-1),
                    "trust_weights": torch.softmax(self.weight_head(h), dim=-1),
                    "incentive_q": self.incentive_head(h),
                    "value": self.value_head(h).squeeze(-1),
                    "modality_q": self.modality_head(h),
                }

        return _TrustPolicyNet(input_dim, hidden)


# --- block-routed fusion -------------------------------------------------
#
# The shared-encoder auxiliary head is a crude router. Its target is the
# attack class, and for the on-off class the class is identified by the
# shape features, so the modality loss pulls the shared representation
# towards shape and away from level. Measured on the spatial scenario, that
# coupling costs 8.7 points of constant-attacker detection (p < 0.0001)
# while the feature-matched control, which has no auxiliary head, pays
# nothing at all for the same five columns.
#
# The block-routed form keeps the routing idea and removes the coupling. Each
# evidence block gets its own encoder, a per-node gate decides how far each
# block's specialist is trusted, and the auxiliary heads read the branch
# embeddings with the gradient path to the branch encoders removed. The shape
# branch is then available to the nodes that need it without taxing the nodes
# that do not, and the auxiliary head becomes what the manuscript says it
# already is: a measurement of what the representation contains, rather than
# a force that reshapes it.
#
# The gate is trained by the risk loss alone. It learns to route because
# routing reduces the risk loss, not because a class label is pushed through
# it.

def feature_blocks(feature_names) -> list[tuple[str, np.ndarray]]:
    """Split a feature vector into its evidence blocks.

    The marginal block is whatever the shape and spatial blocks did not
    claim, so the split does not depend on a hard-coded width and follows
    the feature names the extractor actually produced.
    """
    blocks: dict[str, list[int]] = {"marginal": [], "shape": [],
                                    "neighborhood": []}
    for i, name in enumerate(feature_names):
        if name.startswith("shape_"):
            blocks["shape"].append(i)
        elif name.startswith("spatial_"):
            blocks["neighborhood"].append(i)
        else:
            blocks["marginal"].append(i)
    return [(k, np.array(v, dtype=int)) for k, v in blocks.items() if v]


def GatedTrustPolicyNet(input_dim: int, blocks, hidden: int = 96,
                        gate_hidden: int = 64):
    """A trust model whose evidence blocks are routed, not averaged.

    ``blocks`` is the output of :func:`feature_blocks`. Each block is encoded
    on its own, each block has its own risk specialist, and a gate over the
    concatenated embeddings produces a per-node mixture weight. The mixture
    is what the risk head reads, so the gate is trained by the risk loss.

    The auxiliary heads read the branch embeddings detached, so their losses
    train the heads and nothing else. That is deliberate: the measurement
    that the shared encoder's auxiliary supervision costs 8.7 points on the
    constant class was made with the auxiliary loss attached, and the
    detached form is the one that cannot repeat it.
    """
    import torch
    from torch import nn

    class _GatedTrustPolicyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.blocks = [(name, np.asarray(idx, dtype=int))
                           for name, idx in blocks]
            self.encoders = nn.ModuleList()
            self.risk_heads = nn.ModuleList()
            for _name, idx in self.blocks:
                self.encoders.append(nn.Sequential(
                    nn.Linear(len(idx), hidden),
                    nn.LayerNorm(hidden),
                    nn.ReLU(),
                    nn.Linear(hidden, hidden),
                    nn.ReLU(),
                ))
                self.risk_heads.append(nn.Linear(hidden, 1))
            self.gate = nn.Sequential(
                nn.Linear(hidden * len(self.blocks), gate_hidden),
                nn.ReLU(),
                nn.Linear(gate_hidden, len(self.blocks)),
            )
            self.weight_head = nn.Linear(hidden, 5)
            self.incentive_head = nn.Linear(hidden, 5)
            self.value_head = nn.Linear(hidden, 1)
            self.modality_head = nn.Linear(hidden, len(MODALITY_CLASSES))
            # The auxiliary heads read one summary of the branch embeddings
            # rather than the concatenation itself, so that they keep the
            # width of a single branch.
            self.aux_projection = nn.Linear(hidden * len(self.blocks), hidden)

        def forward(self, x):
            embs = [enc(x[:, idx]) for enc, (_n, idx) in
                    zip(self.encoders, self.blocks)]
            cat = torch.cat(embs, dim=-1)
            weights = torch.softmax(self.gate(cat), dim=-1)
            logits = torch.stack(
                [head(e).squeeze(-1) for head, e in
                 zip(self.risk_heads, embs)], dim=-1)
            risk = (weights * logits).sum(dim=-1)
            # Detached on purpose: the auxiliary losses may train the
            # auxiliary heads, and may not touch the branch encoders.
            h = self.aux_projection(cat).detach()
            return {
                "risk_logit": risk,
                "trust_weights": torch.softmax(self.weight_head(h), dim=-1),
                "incentive_q": self.incentive_head(h),
                "value": self.value_head(h).squeeze(-1),
                "modality_q": self.modality_head(h),
                "gate_weights": weights,
            }

    return _GatedTrustPolicyNet()
