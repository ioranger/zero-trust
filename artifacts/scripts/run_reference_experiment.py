#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from reference_simulator import (
    ABLATIONS,
    METHODS,
    agents_for_n,
    evaluate_ablation,
    evaluate_method,
    load_config,
    per_step_log_rows,
    simulate_trust_stream,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MTIM trust-factor reference experiment.")
    parser.add_argument("--config", default="artifacts/configs/default.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    outputs = config.outputs
    for subdir in ["logs", "tables", "figures"]:
        (outputs / subdir).mkdir(parents=True, exist_ok=True)

    policy_path = outputs / "logs" / "marl_policy.json"
    if not policy_path.exists():
        raise FileNotFoundError(
            f"{policy_path} is missing. Run artifacts/scripts/train_marl_pytorch.py before this experiment."
        )
    policy = json.loads(policy_path.read_text())
    learned_path = outputs / "logs" / "learned_baselines.json"
    if not learned_path.exists():
        raise FileNotFoundError(
            f"{learned_path} is missing. Run artifacts/scripts/train_marl_pytorch.py to train learned baselines."
        )
    policy["learned_baselines"] = json.loads(learned_path.read_text())
    (outputs / "logs" / "training_policy.json").write_text(json.dumps(policy, indent=2))

    metric_rows = []
    ablation_rows = []
    step_rows = []
    default_n = int(config.raw["network"]["default_uavs"])
    default_agents = int(config.raw["network"]["default_thinker_agents"])
    main_ratio = float(config.raw["experiments"]["main_ratio"])

    scenario_grid = set()
    for ratio in config.raw["experiments"]["ratio_grid"]:
        scenario_grid.add((default_n, default_agents, float(ratio), "ratio"))
    for ratio in config.raw["experiments"]["figure_ratio_grid"]:
        scenario_grid.add((default_n, default_agents, float(ratio), "figure_ratio"))
    for n_uavs in config.raw["experiments"]["scalability_uavs"]:
        scenario_grid.add((int(n_uavs), agents_for_n(int(n_uavs)), main_ratio, "scalability"))
    for n_agents in config.raw["experiments"]["agent_grid"]:
        scenario_grid.add((default_n, int(n_agents), main_ratio, "agent_grid"))

    for n_uavs, n_agents, ratio, scenario in sorted(scenario_grid):
        for seed in config.eval_seeds:
            streams, malicious, attack_types = simulate_trust_stream(
                config, seed=seed, n_uavs=n_uavs, malicious_ratio=ratio, n_agents=n_agents
            )
            if scenario in {"ratio", "scalability", "agent_grid"} and seed in list(config.eval_seeds)[:10]:
                step_rows.extend(per_step_log_rows(config, streams, malicious, attack_types, seed, n_uavs, ratio, n_agents))

            for method in METHODS:
                metrics = evaluate_method(config, streams, malicious, method, policy, seed, n_uavs, ratio, n_agents)
                metric_rows.append(
                    {
                        "scenario": scenario,
                        "seed": seed,
                        "n_uavs": n_uavs,
                        "n_agents": n_agents,
                        "malicious_ratio": ratio,
                        "method": method,
                        **metrics,
                    }
                )

            if n_uavs == default_n and n_agents == default_agents and abs(ratio - main_ratio) < 1e-12:
                for variant in ABLATIONS:
                    metrics = evaluate_ablation(config, streams, malicious, variant, policy, seed, n_uavs, n_agents)
                    ablation_rows.append(
                        {
                            "seed": seed,
                            "n_uavs": n_uavs,
                            "n_agents": n_agents,
                            "malicious_ratio": ratio,
                            "variant": variant,
                            **metrics,
                        }
                    )

    pd.DataFrame(metric_rows).to_csv(outputs / "logs" / "per_seed_metrics.csv", index=False)
    pd.DataFrame(ablation_rows).to_csv(outputs / "logs" / "per_seed_ablation.csv", index=False)
    pd.DataFrame(step_rows).to_csv(outputs / "logs" / "per_step_trust_streams.csv", index=False)
    print(f"Wrote metrics, ablation, trust-stream logs, and policy to {outputs}")


if __name__ == "__main__":
    main()
