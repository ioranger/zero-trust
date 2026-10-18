#!/usr/bin/env python3
"""Paper-level baseline reimplementations used by the S-TIM artifact.

No official code for FUBA, GALTrust, or GDM-DTM is bundled here. The functions
below expose auditable reimplementations over the common T1--T5 interface with
all coefficients kept in one place for review and sensitivity checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


@dataclass(frozen=True)
class BaselineConfig:
    mfa_threshold: float = 0.68
    fuba_threshold: float = 0.69
    galtrust_threshold: float = 0.30
    gdm_dtm_threshold: float = 0.69
    ahp_entropy_threshold: float = 0.62
    ahp_entropy_lambda: float = 0.5


def common_statistics(streams: np.ndarray, warmup_steps: int) -> Dict[str, np.ndarray]:
    post = streams[warmup_steps:]
    recent = streams[-120:].mean(axis=0)
    std = post.std(axis=0)
    volatility = std.mean(axis=1)
    consistency = np.max(np.abs(recent[:, :, None] - recent[:, None, :]), axis=(1, 2))
    return {
        "post": post,
        "recent": recent,
        "std": std,
        "volatility": volatility,
        "consistency": consistency,
    }


def mfa(streams: np.ndarray, warmup_steps: int, cfg: BaselineConfig, noise: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    stats = common_statistics(streams, warmup_steps)
    trust = stats["recent"].mean(axis=1) - 0.02 * stats["volatility"] + noise
    return (trust < cfg.mfa_threshold), np.clip(trust, 0.0, 1.0)


def fuba(streams: np.ndarray, warmup_steps: int, cfg: BaselineConfig, noise: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Fuzzy UAV behavior analytics style trust fusion.

    T1/T2/T4 map to behavior, communication, and mission membership functions;
    T3 receives lower weight because energy drain is ambiguous under mobility.
    """

    stats = common_statistics(streams, warmup_steps)
    recent = stats["recent"]
    weak = np.maximum(0.0, 0.68 - recent)
    weights = np.array([0.25, 0.20, 0.08, 0.27, 0.20])
    trust = recent @ weights - 0.045 * weak[:, [0, 1, 3]].sum(axis=1) - 0.025 * stats["consistency"] + noise
    return (trust < cfg.fuba_threshold), np.clip(trust, 0.0, 1.0)


def galtrust(streams: np.ndarray, warmup_steps: int, cfg: BaselineConfig, noise: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """GAN/type-2-fuzzy inspired anomaly profile adapter.

    The honest profile is estimated at the T1--T5 interface; distance, volatility,
    and consistency approximate the discriminator/fuzzy uncertainty score.
    """

    stats = common_statistics(streams, warmup_steps)
    profile = np.array([0.80, 0.76, 0.72, 0.80, 0.75])
    weights = np.array([1.15, 0.95, 0.45, 1.25, 0.70])
    distance = np.sqrt(((stats["recent"] - profile) ** 2 * weights).sum(axis=1))
    risk = 0.65 * distance + 0.38 * stats["volatility"] + 0.11 * stats["consistency"] + noise
    return (risk > cfg.galtrust_threshold), np.clip(1.0 - risk, 0.0, 1.0)


def gdm_dtm(streams: np.ndarray, warmup_steps: int, cfg: BaselineConfig, noise: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Group decision-making dynamic trust management adapter."""

    stats = common_statistics(streams, warmup_steps)
    recent = stats["recent"]
    weights = np.array([0.27, 0.20, 0.08, 0.28, 0.17])
    trust = (
        recent @ weights
        - 0.040 * stats["consistency"]
        - 0.025 * np.maximum(0.0, 0.60 - recent.min(axis=1))
        + noise
    )
    return (trust < cfg.gdm_dtm_threshold), np.clip(trust, 0.0, 1.0)


# --- AHP + entropy-weight (combined subjective/objective weighting) ----------

# Saaty 1-9 pairwise scale for T1--T5 against the parent goal "node trust".
# Built from a stated priority ordering (T1 = T4 > T2 > T5 > T3), i.e.
# a_ij = v_i / v_j with v = (5, 3, 1, 5, 2). The matrix is therefore perfectly
# consistent (CR = 0). The ordering follows the threat model: sustained
# task/behavior degradation is harder for an evasive attacker to sustain than
# energy behaviour, which the generator also makes the easiest channel to mimic.
_AHP_PRIORITY = np.array([5.0, 3.0, 1.0, 5.0, 2.0])
_AHP5 = _AHP_PRIORITY[:, None] / _AHP_PRIORITY[None, :]


def ahp_weights() -> np.ndarray:
    """Priority vector from the Saaty judgement matrix (geometric-mean method)."""

    n = _AHP5.shape[0]
    gm = np.prod(_AHP5, axis=1) ** (1.0 / n)
    w = gm / gm.sum()
    # Consistency check: CR = CI / RI, Saaty random index for n = 5.
    lam_max = float((_AHP5 @ w / w).mean())
    ci = (lam_max - n) / (n - 1)
    cr = ci / 1.12
    if cr > 0.10:  # pragma: no cover - the matrix above is consistent by design
        raise ValueError(f"AHP judgement matrix is inconsistent (CR={cr:.3f} > 0.10)")
    return w


def entropy_weights(matrix: np.ndarray) -> np.ndarray:
    """Shannon-entropy weights over columns of ``matrix`` (n_nodes x n_factors)."""

    x = np.asarray(matrix, dtype=float)
    # Shift to be strictly positive, then normalise per column.
    x = x - x.min(axis=0, keepdims=True) + 1e-9
    p = x / x.sum(axis=0, keepdims=True)
    n = p.shape[0]
    e = -(p * np.log(p)).sum(axis=0) / np.log(n)
    d = 1.0 - e                       # information utility
    if d.sum() <= 0:                  # pragma: no cover - degenerate constant input
        return np.ones(p.shape[1]) / p.shape[1]
    return d / d.sum()


def ahp_entropy(
    streams: np.ndarray,
    warmup_steps: int,
    cfg: BaselineConfig,
    noise: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """AHP (subjective) + entropy (objective) combined trust weighting.

    This adapter differs from the neural S-TIM weighting in that the weights are
    derived from an explicit judgement matrix and observed dispersion rather than
    learned end to end, so it needs no training seeds. It is included to test
    whether an interpretable weighting scheme is competitive with the learned one.
    """

    stats = common_statistics(streams, warmup_steps)
    recent = stats["recent"]                                  # (n_nodes, 5)
    # Objective weights: Shannon-entropy over the cross-node distribution of
    # each factor. A factor whose values vary more across nodes carries more
    # discriminative information and therefore receives a larger weight.
    hist_w = entropy_weights(recent)                          # (5,)
    subj_w = ahp_weights()                                    # (5,)
    lam = float(np.clip(cfg.ahp_entropy_lambda, 0.0, 1.0))
    weights = lam * subj_w + (1.0 - lam) * hist_w
    trust = recent @ weights + noise
    return (trust < cfg.ahp_entropy_threshold), np.clip(trust, 0.0, 1.0)
