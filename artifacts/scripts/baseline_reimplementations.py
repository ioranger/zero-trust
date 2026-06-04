#!/usr/bin/env python3
"""Paper-level baseline reimplementations used by the MTIM artifact.

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
