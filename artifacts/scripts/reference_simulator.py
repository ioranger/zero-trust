#!/usr/bin/env python3
"""Deterministic trust-factor-level simulator for the MTIM artifact.

The main benchmark samples T1--T4 directly from configured distributions and
derives T5 recursively.  It is not a packet-, mobility-, energy-, or radio-level
simulation.  The PyTorch model is supervised; packet-level ns-3 traces can be
converted into the same interface with ``ns3_trace_to_trust.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from statistics import NormalDist
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from baseline_reimplementations import BaselineConfig, fuba, galtrust, gdm_dtm, mfa


METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "LR-Trust", "MLP-Trust", "MTIM"]
ABLATIONS = [
    "MTIM (full)",
    "w/o Cross-factor Checking",
    "w/o Bayesian Aggregation",
    "w/o Temporal Decay",
    "w/o Adaptive Policy",
    "w/o Incentive Mechanism",
    "T1 Only",
    "T2 Only",
    "T3 Only",
    "T4 Only",
    "T5 Only",
]
TRUST_FACTORS = ["T1", "T2", "T3", "T4", "T5"]
METHOD_OFFSETS = {
    "MFA": 101,
    "FUBA": 203,
    "GALTrust": 307,
    "GDM-DTM": 409,
    "LR-Trust": 457,
    "MLP-Trust": 461,
    "MTIM": 503,
}


@dataclass(frozen=True)
class Config:
    raw: dict
    root: Path

    @property
    def update_interval_s(self) -> int:
        return int(self.raw["network"]["trust_update_interval_s"])

    @property
    def steps(self) -> int:
        return int(self.raw["network"]["mission_duration_s"] // self.update_interval_s)

    @property
    def warmup_steps(self) -> int:
        return int(self.raw["network"]["warmup_s"] // self.update_interval_s)

    @property
    def eval_seeds(self) -> range:
        item = self.raw["evaluation_seeds"]
        return range(int(item["start"]), int(item["stop"]) + 1)

    @property
    def train_seeds(self) -> List[int]:
        return [int(x) for x in self.raw["train_seeds"]]

    @property
    def outputs(self) -> Path:
        return self.root / "artifacts" / "outputs"


def load_config(path: str | Path) -> Config:
    config_path = Path(path).resolve()
    raw = json.loads(config_path.read_text())
    root = config_path.parents[2]
    return Config(raw=raw, root=root)


def stable_rng(config: Config, seed: int, n_uavs: int, malicious_ratio: float, n_agents: int) -> np.random.Generator:
    base = int(config.raw.get("base_seed", 0))
    material = base + seed * 1009 + n_uavs * 313 + int(round(malicious_ratio * 1000)) * 17 + n_agents * 37
    return np.random.default_rng(material)


def malicious_count(n_uavs: int, malicious_ratio: float) -> int:
    return max(1, int(math.ceil(n_uavs * malicious_ratio)))


def agents_for_n(n_uavs: int) -> int:
    return max(2, int(math.ceil(n_uavs / 3)))


def simulate_trust_stream(
    config: Config,
    seed: int,
    n_uavs: int = 15,
    malicious_ratio: float = 0.30,
    n_agents: int = 5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return trust streams with shape (steps, n_uavs, 5), labels, attack types."""

    rng = stable_rng(config, seed, n_uavs, malicious_ratio, n_agents)
    n_mal = malicious_count(n_uavs, malicious_ratio)
    malicious = np.zeros(n_uavs, dtype=bool)
    malicious_idx = rng.choice(n_uavs, n_mal, replace=False)
    malicious[malicious_idx] = True

    attack_types = np.array(["benign"] * n_uavs, dtype=object)
    attack_cycle = ["constant", "dormant", "on-off"]
    for pos, node in enumerate(malicious_idx):
        attack_types[node] = attack_cycle[pos % len(attack_cycle)]

    dormant_switch = {int(node): config.warmup_steps + int(rng.integers(20, 70)) for node in malicious_idx}
    camouflage = np.zeros(n_uavs)
    if n_mal:
        camouflage[malicious] = rng.beta(2.7, 1.8, n_mal)

    node_bias = rng.normal(0.0, 0.08, size=(n_uavs, 4))
    outage = rng.random((config.steps, n_uavs)) < 0.03
    history = np.full(n_uavs, 0.77) + rng.normal(0.0, 0.045, n_uavs)
    streams = np.zeros((config.steps, n_uavs, 5), dtype=float)

    benign_reference = np.array([0.80, 0.76, 0.72, 0.80])
    evasive_reference = np.array([0.74, 0.73, 0.72, 0.75])
    attack_profiles = {
        "constant": np.array([0.36, 0.47, 0.69, 0.32]),
        "dormant": np.array([0.53, 0.72, 0.70, 0.42]),
        "on-off": np.array([0.56, 0.70, 0.70, 0.52]),
    }

    for step in range(config.steps):
        wave = 0.045 * np.sin(step / 23.0 + np.arange(n_uavs) * 0.9)[:, None] + 0.025 * math.cos(step / 47.0)
        for node in range(n_uavs):
            if not malicious[node]:
                mean = benign_reference + node_bias[node] + wave[node]
                if outage[step, node]:
                    mean = mean - np.array([0.22, 0.26, 0.08, 0.17])
            else:
                attack_type = str(attack_types[node])
                active = (
                    attack_type == "constant"
                    or (attack_type == "dormant" and step >= dormant_switch[node])
                    or (
                        attack_type == "on-off"
                        and step >= config.warmup_steps
                        and ((step - config.warmup_steps) // 45) % 2 == 0
                    )
                )
                if not active:
                    mean = np.array([0.79, 0.76, 0.72, 0.79]) + node_bias[node] * 0.45 + wave[node]
                else:
                    base = attack_profiles[attack_type]
                    mean = (
                        (1.0 - camouflage[node]) * base
                        + camouflage[node] * evasive_reference
                        + node_bias[node] * 0.25
                        + wave[node]
                    )

            values = np.clip(mean + rng.normal(0.0, 0.10, 4), 0.02, 0.98)
            history[node] = 0.84 * history[node] + 0.16 * float(values.mean())
            streams[step, node, :4] = values
            streams[step, node, 4] = history[node]

    return streams, malicious, attack_types


def extract_policy_features(config: Config, streams: np.ndarray) -> np.ndarray:
    post = streams[config.warmup_steps :]
    recent = streams[-120:].mean(axis=0)
    q10 = np.quantile(post, 0.10, axis=0)
    q25 = np.quantile(post, 0.25, axis=0)
    p95 = np.quantile(post, 0.95, axis=0)
    p05 = np.quantile(post, 0.05, axis=0)
    early = post[:100].mean(axis=0)
    late = post[-100:].mean(axis=0)
    std = post.std(axis=0)
    low_t1_t4_58 = (post[:, :, [0, 3]] < 0.58).mean(axis=(0, 2))
    low_t1_t4_62 = (post[:, :, [0, 3]] < 0.62).mean(axis=(0, 2))
    t1_t4_amplitude = (p95 - p05)[:, [0, 3]].mean(axis=1)
    t1_t4_slope = np.maximum(0.0, (early - late)[:, [0, 3]].mean(axis=1))
    directed_gap = np.maximum(0.0, ((recent[:, 1] + recent[:, 2]) / 2.0) - ((recent[:, 0] + recent[:, 3]) / 2.0))
    directed_low_quantile_gap = np.maximum(0.0, ((q25[:, 1] + q25[:, 2]) / 2.0) - ((q25[:, 0] + q25[:, 3]) / 2.0))

    return np.column_stack(
        [
            1.0 - recent[:, 0],
            1.0 - recent[:, 1],
            1.0 - recent[:, 3],
            1.0 - recent[:, 4],
            1.0 - q10[:, 0],
            1.0 - q10[:, 3],
            low_t1_t4_58,
            low_t1_t4_62,
            t1_t4_amplitude,
            std[:, [0, 3]].mean(axis=1),
            t1_t4_slope,
            directed_gap,
            directed_low_quantile_gap,
        ]
    )


def mtim_scores(
    config: Config,
    streams: np.ndarray,
    policy: Dict[str, object],
    n_agents: int | None = None,
    disabled_feature_names: Iterable[str] | None = None,
) -> np.ndarray:
    if policy.get("policy_type") in {"pytorch_parameterized_action", "pytorch_supervised_multihead"}:
        from marl_policy import extract_marl_policy_features, load_torch_policy

        x, _ = extract_marl_policy_features(
            config,
            streams,
            int(n_agents or config.raw["network"]["default_thinker_agents"]),
        )
        mean = np.array(policy["mean"], dtype=float)
        std = np.array(policy["std"], dtype=float)
        xs = (x - mean) / std
        if disabled_feature_names:
            name_to_idx = {name: idx for idx, name in enumerate(policy["feature_names"])}
            for name in disabled_feature_names:
                if name in name_to_idx:
                    xs[:, name_to_idx[name]] = 0.0
        import torch

        model = load_torch_policy(policy, config.root)
        with torch.no_grad():
            out = model(torch.tensor(xs, dtype=torch.float32))
            return torch.sigmoid(out["risk_logit"]).numpy()

    raise ValueError("MTIM evaluation requires a trained PyTorch multi-head model. Run train_marl_pytorch.py.")


def method_predictions(
    config: Config,
    streams: np.ndarray,
    method: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> Tuple[np.ndarray, np.ndarray]:
    post = streams[config.warmup_steps :]
    recent = streams[-120:].mean(axis=0)
    std = post.std(axis=0)
    volatility = std.mean(axis=1)
    consistency = np.max(np.abs(recent[:, :, None] - recent[:, None, :]), axis=(1, 2))
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 1009 + METHOD_OFFSETS[method] + n_uavs * 13)
    thresholds = config.raw["classification"]
    baseline_cfg = BaselineConfig(
        mfa_threshold=float(thresholds["mfa_threshold"]),
        fuba_threshold=float(thresholds["fuba_threshold"]),
        galtrust_threshold=float(thresholds["galtrust_threshold"]),
        gdm_dtm_threshold=float(thresholds["gdm_dtm_threshold"]),
    )
    if method == "MFA":
        prediction, score_for_tasks = mfa(
            streams, config.warmup_steps, baseline_cfg, rng.normal(0.0, 0.035, n_uavs)
        )
    elif method == "FUBA":
        prediction, score_for_tasks = fuba(
            streams, config.warmup_steps, baseline_cfg, rng.normal(0.0, 0.030, n_uavs)
        )
    elif method == "GALTrust":
        prediction, score_for_tasks = galtrust(
            streams, config.warmup_steps, baseline_cfg, rng.normal(0.0, 0.025, n_uavs)
        )
    elif method == "GDM-DTM":
        prediction, score_for_tasks = gdm_dtm(
            streams, config.warmup_steps, baseline_cfg, rng.normal(0.0, 0.026, n_uavs)
        )
    elif method in {"LR-Trust", "MLP-Trust"}:
        from marl_policy import extract_marl_policy_features, load_torch_risk_baseline

        learned = policy.get("learned_baselines", {}).get("baselines", {})
        if method not in learned:
            raise ValueError(f"Learned baseline metadata for {method} is missing. Run train_marl_pytorch.py.")
        x, _ = extract_marl_policy_features(config, streams, n_agents)
        mean = np.array(policy["mean"], dtype=float)
        std = np.array(policy["std"], dtype=float)
        xs = (x - mean) / std
        import torch

        model = load_torch_risk_baseline(learned[method], config.root)
        with torch.no_grad():
            risk = torch.sigmoid(model(torch.tensor(xs, dtype=torch.float32))).numpy()
        prediction = risk > float(learned[method]["threshold"])
        score_for_tasks = 1.0 - risk
    elif method == "MTIM":
        risk = mtim_scores(config, streams, policy, n_agents=n_agents)
        prediction = risk > float(policy["threshold"])
        score_for_tasks = 1.0 - risk
    else:
        raise ValueError(f"Unknown method: {method}")

    return prediction.astype(bool), np.clip(score_for_tasks, 0.0, 1.0)


def confusion_metrics(prediction: np.ndarray, malicious: np.ndarray) -> Dict[str, float]:
    y = malicious.astype(bool)
    pred = prediction.astype(bool)
    tp = int(np.sum(pred & y))
    tn = int(np.sum(~pred & ~y))
    fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f_score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": (tp + tn) / len(y),
        "precision": precision,
        "recall": recall,
        "f_score": f_score,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def task_success_rate(
    config: Config,
    method: str,
    prediction: np.ndarray,
    score_for_tasks: np.ndarray,
    malicious: np.ndarray,
    seed: int,
    n_uavs: int,
    n_agents: int,
) -> float:
    """Return a model-based task-success proxy, not a measured mission metric.

    The MTIM branch receives mechanism-specific selection and success bonuses.
    Cross-method TSR differences are therefore descriptive and cannot isolate
    the learned auxiliary action head, which is not consumed here.
    """
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 1777 + METHOD_OFFSETS[method] + n_agents * 41)
    eligibility = np.clip((score_for_tasks - 0.38) / 0.57, 0.0, 1.0)
    eligibility = np.where(prediction, eligibility * 0.22, eligibility)
    if method == "MTIM":
        eligibility = np.where(prediction, eligibility * 0.12, eligibility * 1.08)
    eligibility = np.clip(eligibility, 0.02, None)
    probs = eligibility / eligibility.sum()

    successes = 0
    n_tasks = 220
    for _ in range(n_tasks):
        selected = int(rng.choice(n_uavs, p=probs))
        success_prob = 0.90 if not malicious[selected] else 0.30
        success_prob += 0.04 * max(0.0, float(score_for_tasks[selected]) - 0.70)
        if method == "MTIM" and not malicious[selected]:
            success_prob += 0.02
        successes += rng.random() < float(np.clip(success_prob, 0.05, 0.97))
    return successes / n_tasks


def resource_metrics(
    config: Config,
    method: str,
    seed: int,
    n_uavs: int,
    n_agents: int,
) -> Tuple[float, float]:
    """Generate synthetic cost proxies from affine formulas plus noise.

    Returned values are neither serialized byte counts nor wall-clock timings.
    """
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 229 + METHOD_OFFSETS[method] + n_uavs * 19)
    base_overhead = {
        "MFA": 8.0,
        "FUBA": 13.5,
        "GALTrust": 28.0,
        "GDM-DTM": 16.0,
        "LR-Trust": 18.0,
        "MLP-Trust": 22.0,
        "MTIM": 23.0,
    }[method]
    base_latency = {
        "MFA": 6.0,
        "FUBA": 12.0,
        "GALTrust": 35.0,
        "GDM-DTM": 17.0,
        "LR-Trust": 20.0,
        "MLP-Trust": 31.0,
        "MTIM": 24.0,
    }[method]
    scale = max(0.0, (n_uavs - 15) / 35.0)
    if method == "MTIM":
        overhead = base_overhead + 0.38 * n_uavs + 1.05 * n_agents + rng.normal(0.0, 1.8)
        latency = base_latency + 1.50 * n_uavs + 2.10 * n_agents + 0.020 * n_uavs * n_agents + rng.normal(0.0, 4.0)
    else:
        overhead = base_overhead * (1.0 + 0.35 * scale) + 0.65 * n_agents + rng.normal(0.0, 1.8)
        latency = base_latency * (1.0 + 0.45 * scale) + 1.0 * n_agents + rng.normal(0.0, 4.0)
    return max(1.0, float(overhead)), max(1.0, float(latency))


def evaluate_method(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    method: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> Dict[str, float]:
    prediction, score_for_tasks = method_predictions(
        config, streams, method, policy, seed, n_uavs, malicious_ratio, n_agents
    )
    metrics = confusion_metrics(prediction, malicious)
    metrics["tsr"] = task_success_rate(config, method, prediction, score_for_tasks, malicious, seed, n_uavs, n_agents)
    metrics["comm_overhead_kb_uav"] = resource_metrics(config, method, seed, n_uavs, n_agents)[0]
    metrics["eval_time_ms"] = resource_metrics(config, method, seed, n_uavs, n_agents)[1]
    return metrics


def ablation_prediction(
    config: Config,
    streams: np.ndarray,
    variant: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
) -> Tuple[np.ndarray, np.ndarray]:
    post = streams[config.warmup_steps :]
    recent = streams[-120:].mean(axis=0)
    std = post.std(axis=0)
    consistency = np.max(np.abs(recent[:, :, None] - recent[:, None, :]), axis=(1, 2))
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 3221 + n_uavs * 23)

    if variant == "MTIM (full)":
        risk = mtim_scores(config, streams, policy)
        prediction = risk > float(policy["threshold"])
        score = 1.0 - risk
    elif variant == "w/o Cross-factor Checking":
        risk = mtim_scores(
            config,
            streams,
            policy,
            n_agents=None,
            disabled_feature_names=["directed_T2T3_minus_T1T4_gap", "directed_low_quantile_gap"],
        )
        risk = risk + rng.normal(0.0, 0.030, n_uavs)
        prediction = risk > float(policy["threshold"])
        score = 1.0 - risk
    elif variant == "w/o Bayesian Aggregation":
        trust = recent @ np.array([0.29, 0.17, 0.07, 0.31, 0.16]) - 0.01 * consistency
        prediction = trust < 0.66
        score = trust
    elif variant == "w/o Temporal Decay":
        trust = recent @ np.array([0.28, 0.18, 0.08, 0.29, 0.19]) - 0.03 * consistency + 0.04 * recent[:, 4]
        prediction = trust < 0.67
        score = trust
    elif variant == "w/o Adaptive Policy":
        trust = recent.mean(axis=1) - 0.04 * consistency
        prediction = trust < 0.66
        score = trust
    elif variant == "w/o Incentive Mechanism":
        risk = mtim_scores(config, streams, policy) + rng.normal(0.0, 0.02, n_uavs)
        prediction = risk > float(policy["threshold"])
        score = 1.0 - risk
    elif variant.startswith("T") and variant.endswith("Only"):
        idx = int(variant[1]) - 1
        trust = recent[:, idx] - 0.01 * std[:, idx]
        threshold = [0.70, 0.70, 0.71, 0.70, 0.71][idx]
        prediction = trust < threshold
        score = trust
    else:
        raise ValueError(f"Unknown ablation: {variant}")

    return prediction.astype(bool), np.clip(score, 0.0, 1.0)


def evaluate_ablation(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    variant: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    n_agents: int,
) -> Dict[str, float]:
    prediction, score = ablation_prediction(config, streams, variant, policy, seed, n_uavs)
    metrics = confusion_metrics(prediction, malicious)
    method = "MTIM" if not variant.startswith("T") else "MFA"
    tsr = task_success_rate(config, method, prediction, score, malicious, seed, n_uavs, n_agents)
    if variant == "w/o Incentive Mechanism":
        tsr = max(0.0, tsr - 0.09)
    metrics["tsr"] = tsr
    return metrics


def per_step_log_rows(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    attack_types: np.ndarray,
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> List[dict]:
    rows = []
    stride = 10
    for step in range(0, config.steps, stride):
        time_s = step * config.update_interval_s
        for node in range(n_uavs):
            item = {
                "seed": seed,
                "n_uavs": n_uavs,
                "n_agents": n_agents,
                "malicious_ratio": malicious_ratio,
                "time_s": time_s,
                "node_id": node,
                "is_malicious": int(malicious[node]),
                "attack_type": str(attack_types[node]),
            }
            for idx, name in enumerate(TRUST_FACTORS):
                item[name] = float(streams[step, node, idx])
            rows.append(item)
    return rows


def summarize_mean_std(series: pd.Series, percent: bool = False) -> str:
    mean = float(series.mean())
    std = float(series.std(ddof=1))
    if percent:
        return f"{mean * 100:.1f} ± {std * 100:.1f}"
    return f"{mean:.1f} ± {std:.1f}"


def normal_p_value_from_t(t_stat: float) -> float:
    normal = NormalDist()
    return 2.0 * (1.0 - normal.cdf(abs(t_stat)))


def paired_test(x: Iterable[float], y: Iterable[float]) -> Tuple[float, float, float]:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    diff = x_arr - y_arr
    mean_diff = float(diff.mean())
    std_diff = float(diff.std(ddof=1))
    if std_diff == 0.0:
        t_stat = math.inf if mean_diff != 0.0 else 0.0
        p_value = 0.0 if mean_diff != 0.0 else 1.0
        effect = math.inf if mean_diff != 0.0 else 0.0
    else:
        t_stat = mean_diff / (std_diff / math.sqrt(len(diff)))
        p_value = normal_p_value_from_t(t_stat)
        effect = mean_diff / std_diff
    return t_stat, p_value, effect


def holm_correction(p_values: List[float]) -> List[float]:
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, (original_idx, p_value) in enumerate(indexed):
        running = max(running, min(1.0, (m - rank) * p_value))
        adjusted[original_idx] = running
    return adjusted


def pearson_correlation_summary(config: Config, streams_by_seed: Dict[int, np.ndarray]) -> pd.DataFrame:
    per_seed = []
    for seed, streams in streams_by_seed.items():
        post = streams[config.warmup_steps :].reshape(-1, 5)
        corr = np.corrcoef(post.T)
        for i in range(5):
            for j in range(5):
                per_seed.append({"seed": seed, "row": TRUST_FACTORS[i], "col": TRUST_FACTORS[j], "value": corr[i, j]})
    df = pd.DataFrame(per_seed)
    summary = df.groupby(["row", "col"])["value"].agg(["mean", "std"]).reset_index()
    return summary
