#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reference_simulator import load_config, mtim_scores, simulate_trust_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate MTIM artifact figures.")
    parser.add_argument("--config", default="artifacts/configs/default.json")
    return parser.parse_args()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "matplotlib is required for plotting. Install with: "
            "python3 -m pip install -r artifacts/requirements.txt"
        ) from exc
    return plt


def parse_mean_std(text: str) -> tuple[float, float]:
    mean, std = text.split("±")
    return float(mean.strip()), float(std.strip())


def diagnostic_trust(config, streams, policy, end_step: int) -> np.ndarray:
    """Sliding-window MTIM diagnostic trust index on a 0--10 scale."""
    windowed = streams.copy()
    cutoff = min(end_step + 1, windowed.shape[0])
    if cutoff < windowed.shape[0]:
        windowed[cutoff:] = windowed[cutoff - 1]
    risk = mtim_scores(config, windowed, policy)
    return 10.0 * (1.0 - risk)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    root = Path(__file__).resolve().parents[2]
    outputs = config.outputs
    figures = outputs / "figures"
    manuscript_figures = root / "paper" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    manuscript_figures.mkdir(parents=True, exist_ok=True)
    plt = require_matplotlib()

    metrics = pd.read_csv(outputs / "logs" / "per_seed_metrics.csv")
    streams = pd.read_csv(outputs / "logs" / "per_step_trust_streams.csv")
    policy = json.loads((outputs / "logs" / "training_policy.json").read_text())
    main_ratio = float(config.raw["experiments"]["main_ratio"])
    default_n = int(config.raw["network"]["default_uavs"])
    default_agents = int(config.raw["network"]["default_thinker_agents"])

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
        }
    )

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    colors = {2: "#1f77b4", 5: "#2ca02c", 10: "#d62728"}
    for n_agents in config.raw["experiments"]["agent_grid"]:
        curve_rows = []
        for seed in list(config.eval_seeds)[:10]:
            full_stream, malicious, _ = simulate_trust_stream(config, seed=seed, n_uavs=default_n, malicious_ratio=main_ratio, n_agents=int(n_agents))
            for step in range(config.warmup_steps, config.steps, 20):
                trust = diagnostic_trust(config, full_stream, policy, step)
                curve_rows.append(
                    {
                        "time_s": step * config.update_interval_s,
                        "benign": float(trust[~malicious].mean()),
                        "malicious": float(trust[malicious].mean()),
                    }
                )
        curve = pd.DataFrame(curve_rows).groupby("time_s").mean().reset_index()
        ax.plot(curve["time_s"], curve["benign"], "-", color=colors[int(n_agents)], linewidth=1.8, label=f"M={n_agents} benign")
        ax.plot(curve["time_s"], curve["malicious"], "--", color=colors[int(n_agents)], linewidth=1.8, label=f"M={n_agents} malicious")
    ax.axvline(config.raw["network"]["warmup_s"], color="#666666", linewidth=1.0, linestyle=":")
    ax.set_xlabel("Mission time (s)")
    ax.set_ylabel("MTIM diagnostic trust index")
    ax.set_ylim(0, 10)
    ax.grid(True, alpha=0.25)
    ax.legend(ncol=3, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    for output in [figures / "trust_value_evolution.png", manuscript_figures / "trust_value_evolution.png"]:
        fig.savefig(output)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.8))
    ratio_source = metrics[(metrics["scenario"] == "figure_ratio") & (metrics["n_uavs"] == default_n)]
    ratio_summary = ratio_source.groupby(["malicious_ratio", "method"])["accuracy"].mean().reset_index()
    for method, color in [
        ("MFA", "#7f7f7f"),
        ("FUBA", "#ff7f0e"),
        ("GALTrust", "#9467bd"),
        ("GDM-DTM", "#1f77b4"),
        ("LR-Trust", "#8c564b"),
        ("MLP-Trust", "#e377c2"),
        ("MTIM", "#2ca02c"),
    ]:
        line = ratio_summary[ratio_summary["method"] == method].sort_values("malicious_ratio")
        axes[0].plot(line["malicious_ratio"] * 100, line["accuracy"] * 100, marker="o", linewidth=1.8, label=method, color=color)
    axes[0].set_xlabel("Malicious-node ratio (%)")
    axes[0].set_ylabel("Detection accuracy (%)")
    axes[0].set_ylim(45, 100)
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(fontsize=7, ncol=2)
    axes[0].set_title("(a) Ratio robustness")

    attack_rows = []
    for seed in list(config.eval_seeds)[:10]:
        full_stream, malicious, attack_types = simulate_trust_stream(config, seed=seed, n_uavs=default_n, malicious_ratio=main_ratio, n_agents=default_agents)
        for step in range(config.warmup_steps, config.steps, 20):
            trust = diagnostic_trust(config, full_stream, policy, step)
            for attack_type in ["benign", "constant", "dormant", "on-off"]:
                mask = attack_types == attack_type
                if mask.any():
                    attack_rows.append({"time_s": step * config.update_interval_s, "attack_type": attack_type, "trust": float(trust[mask].mean())})
    trust_by_attack = pd.DataFrame(attack_rows).groupby(["time_s", "attack_type"])["trust"].mean().reset_index()
    attack_colors = {"benign": "#2ca02c", "constant": "#d62728", "dormant": "#ff7f0e", "on-off": "#1f77b4"}
    for attack_type in ["benign", "constant", "dormant", "on-off"]:
        line = trust_by_attack[trust_by_attack["attack_type"] == attack_type]
        if not line.empty:
            axes[1].plot(line["time_s"], line["trust"], linewidth=1.8, color=attack_colors[attack_type], label=attack_type)
    axes[1].axvline(config.raw["network"]["warmup_s"], color="#666666", linewidth=1.0, linestyle=":")
    axes[1].set_xlabel("Mission time (s)")
    axes[1].set_ylabel("Diagnostic trust index")
    axes[1].set_ylim(0, 10)
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(fontsize=8)
    axes[1].set_title("(b) Attack dynamics")

    baseline = pd.read_csv(outputs / "tables" / "baseline_comparison.csv")
    tsr_means = [parse_mean_std(v)[0] for v in baseline["tsr"]]
    axes[2].bar(baseline["method"], tsr_means, color=["#7f7f7f", "#ff7f0e", "#9467bd", "#1f77b4", "#2ca02c"])
    axes[2].set_ylabel("Task success rate (%)")
    axes[2].set_ylim(45, 100)
    axes[2].tick_params(axis="x", rotation=35)
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[2].set_title("(c) TSR at 30% malicious")

    fig.tight_layout()
    for output in [figures / "Fig5_energy_consumption.png", manuscript_figures / "Fig5_energy_consumption.png"]:
        fig.savefig(output)
    plt.close(fig)
    print(f"Wrote figures to {figures}")


if __name__ == "__main__":
    main()
