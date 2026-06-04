#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reference_simulator import METHODS, Config, confusion_metrics, load_config, method_predictions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate MTIM and baselines on converted ns-3 T1--T5 traces.")
    parser.add_argument("--config", default="artifacts/configs/default.json")
    parser.add_argument("--trace", default="artifacts/outputs/logs/ns3_trust_streams.csv")
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--output", default="artifacts/outputs/tables/ns3_trace_validation.csv")
    return parser.parse_args()


def trace_to_streams(trace: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    times = sorted(trace["time_s"].unique())
    nodes = sorted(trace["node_id"].unique())
    node_to_idx = {node: idx for idx, node in enumerate(nodes)}
    streams = np.zeros((len(times), len(nodes), 5), dtype=float)
    labels = np.zeros(len(nodes), dtype=bool)
    attack_types = np.array(["benign"] * len(nodes), dtype=object)
    for t_idx, time_s in enumerate(times):
        part = trace[trace["time_s"] == time_s]
        for _, row in part.iterrows():
            idx = node_to_idx[int(row["node_id"])]
            streams[t_idx, idx, :] = [float(row[f"T{i}"]) for i in range(1, 6)]
            labels[idx] = bool(int(row["is_malicious"]))
            attack_types[idx] = str(row["attack_type"])
    return streams, labels, attack_types


def config_for_trace(config: Config, trace_steps: int) -> Config:
    raw = copy.deepcopy(config.raw)
    update_interval = int(raw["network"]["trust_update_interval_s"])
    warmup_steps = max(1, min(trace_steps // 5, trace_steps - 2))
    raw["network"]["warmup_s"] = int(warmup_steps * update_interval)
    raw["network"]["mission_duration_s"] = int(trace_steps * update_interval)
    return Config(raw=raw, root=config.root)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    outputs = config.outputs
    trace_path = Path(args.trace)
    trace = pd.read_csv(trace_path)
    streams, labels, attack_types = trace_to_streams(trace)
    trace_config = config_for_trace(config, streams.shape[0])
    n_uavs = streams.shape[1]
    n_agents = int(config.raw["network"]["default_thinker_agents"])
    malicious_ratio = float(labels.mean())

    policy_path = outputs / "logs" / "marl_policy.json"
    learned_path = outputs / "logs" / "learned_baselines.json"
    if not policy_path.exists() or not learned_path.exists():
        raise FileNotFoundError("Run train_marl_pytorch.py before trace-driven evaluation.")
    policy = json.loads(policy_path.read_text())
    policy["learned_baselines"] = json.loads(learned_path.read_text())

    rows = []
    for method in METHODS:
        prediction, score = method_predictions(
            trace_config,
            streams,
            method,
            policy,
            seed=int(args.seed),
            n_uavs=n_uavs,
            malicious_ratio=malicious_ratio,
            n_agents=n_agents,
        )
        metrics = confusion_metrics(prediction, labels)
        rows.append(
            {
                "trace": str(trace_path),
                "method": method,
                "n_uavs": n_uavs,
                "trace_steps": streams.shape[0],
                "warmup_steps_used": trace_config.warmup_steps,
                "malicious_ratio": malicious_ratio,
                "mean_score_benign": float(score[~labels].mean()) if np.any(~labels) else 0.0,
                "mean_score_malicious": float(score[labels].mean()) if np.any(labels) else 0.0,
                **metrics,
            }
        )

    table = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)

    attack_summary = (
        pd.DataFrame({"attack_type": attack_types, "is_malicious": labels.astype(int)})
        .groupby("attack_type")
        .agg(nodes=("attack_type", "size"), malicious_nodes=("is_malicious", "sum"))
        .reset_index()
    )
    summary_path = outputs / "logs" / "ns3_trace_summary.json"
    summary = {
        "trace": str(trace_path),
        "n_uavs": n_uavs,
        "trace_steps": int(streams.shape[0]),
        "warmup_steps_used": int(trace_config.warmup_steps),
        "time_min_s": float(trace["time_s"].min()),
        "time_max_s": float(trace["time_s"].max()),
        "attack_coverage": attack_summary.to_dict(orient="records"),
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Wrote trace-driven validation table to {output}")
    print(f"Wrote trace summary to {summary_path}")


if __name__ == "__main__":
    main()
