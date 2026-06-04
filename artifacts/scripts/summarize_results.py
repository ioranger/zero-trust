#!/usr/bin/env python3
from __future__ import annotations

import argparse

import pandas as pd

from reference_simulator import (
    METHODS,
    holm_correction,
    load_config,
    paired_test,
    pearson_correlation_summary,
    simulate_trust_stream,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize MTIM artifact logs into manuscript tables.")
    parser.add_argument("--config", default="artifacts/configs/default.json")
    return parser.parse_args()


def mean_std(df: pd.DataFrame, metric: str, percent: bool) -> str:
    mean = df[metric].mean()
    std = df[metric].std(ddof=1)
    if percent:
        return f"{mean * 100:.1f} ± {std * 100:.1f}"
    return f"{mean:.1f} ± {std:.1f}"


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    outputs = config.outputs
    tables = outputs / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    metrics = pd.read_csv(outputs / "logs" / "per_seed_metrics.csv")
    ablation = pd.read_csv(outputs / "logs" / "per_seed_ablation.csv")
    main_ratio = float(config.raw["experiments"]["main_ratio"])
    default_n = int(config.raw["network"]["default_uavs"])
    default_agents = int(config.raw["network"]["default_thinker_agents"])

    main = metrics[
        (metrics["scenario"].isin(["ratio", "figure_ratio"]))
        & (metrics["n_uavs"] == default_n)
        & (metrics["n_agents"] == default_agents)
        & (metrics["malicious_ratio"].round(6) == round(main_ratio, 6))
    ].drop_duplicates(["seed", "method"])

    baseline_rows = []
    for method in METHODS:
        part = main[main["method"] == method]
        baseline_rows.append(
            {
                "method": method,
                "accuracy": mean_std(part, "accuracy", True),
                "f_score": mean_std(part, "f_score", True),
                "tsr": mean_std(part, "tsr", True),
                "comm_overhead_kb_uav": mean_std(part, "comm_overhead_kb_uav", False),
                "eval_time_ms": mean_std(part, "eval_time_ms", False),
            }
        )
    pd.DataFrame(baseline_rows).to_csv(tables / "baseline_comparison.csv", index=False)

    ratio_rows = []
    ratio_source = metrics[(metrics["scenario"] == "ratio") & (metrics["n_uavs"] == default_n)]
    for method in METHODS:
        row = {"method": method}
        for ratio in config.raw["experiments"]["ratio_grid"]:
            part = ratio_source[(ratio_source["method"] == method) & (ratio_source["malicious_ratio"].round(6) == round(float(ratio), 6))]
            row[f"accuracy_{int(float(ratio) * 100)}pct"] = mean_std(part, "accuracy", True)
            row[f"tsr_{int(float(ratio) * 100)}pct"] = mean_std(part, "tsr", True)
        ratio_rows.append(row)
    pd.DataFrame(ratio_rows).to_csv(tables / "multi_ratio.csv", index=False)

    ablation_rows = []
    for variant, part in ablation.groupby("variant", sort=False):
        ablation_rows.append(
            {
                "variant": variant,
                "accuracy": mean_std(part, "accuracy", True),
                "f_score": mean_std(part, "f_score", True),
                "tsr": mean_std(part, "tsr", True),
            }
        )
    pd.DataFrame(ablation_rows).to_csv(tables / "ablation.csv", index=False)

    scalability_source = metrics[
        (metrics["scenario"] == "scalability")
        & (metrics["method"] == "MTIM")
        & (metrics["malicious_ratio"].round(6) == round(main_ratio, 6))
    ]
    scalability_rows = []
    for n_uavs, part in scalability_source.groupby("n_uavs"):
        n_agents = int(part["n_agents"].iloc[0])
        scalability_rows.append(
            {
                "n_uavs": int(n_uavs),
                "n_agents": n_agents,
                "accuracy": mean_std(part, "accuracy", True),
                "eval_time_ms": mean_std(part, "eval_time_ms", False),
                "comm_overhead_kb_uav": mean_std(part, "comm_overhead_kb_uav", False),
            }
        )
    pd.DataFrame(scalability_rows).sort_values("n_uavs").to_csv(tables / "scalability.csv", index=False)

    test_rows = []
    p_values = []
    for baseline in [m for m in METHODS if m != "MTIM"]:
        merged = main[main["method"] == "MTIM"][["seed", "accuracy", "f_score", "tsr"]].merge(
            main[main["method"] == baseline][["seed", "accuracy", "f_score", "tsr"]],
            on="seed",
            suffixes=("_mtim", "_baseline"),
        )
        for metric in ["accuracy", "f_score", "tsr"]:
            t_stat, p_value, effect = paired_test(merged[f"{metric}_mtim"], merged[f"{metric}_baseline"])
            p_values.append(p_value)
            test_rows.append(
                {
                    "baseline": baseline,
                    "metric": metric,
                    "mean_diff": merged[f"{metric}_mtim"].mean() - merged[f"{metric}_baseline"].mean(),
                    "t_stat_normal_approx": t_stat,
                    "p_value": p_value,
                    "cohens_dz": effect,
                }
            )
    adjusted = holm_correction(p_values)
    for row, adj in zip(test_rows, adjusted):
        row["holm_p_value"] = adj
        row["significant_0_01"] = bool(adj < 0.01)
    pd.DataFrame(test_rows).to_csv(tables / "statistical_tests.csv", index=False)

    streams_by_seed = {}
    for seed in config.eval_seeds:
        streams, _, _ = simulate_trust_stream(config, seed=seed, n_uavs=default_n, malicious_ratio=main_ratio, n_agents=default_agents)
        streams_by_seed[seed] = streams
    pearson_correlation_summary(config, streams_by_seed).to_csv(tables / "correlation.csv", index=False)

    print(f"Wrote summary tables to {tables}")


if __name__ == "__main__":
    main()
