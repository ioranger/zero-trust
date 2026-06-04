#!/usr/bin/env python3
from __future__ import annotations

import argparse

import pandas as pd

from reference_simulator import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot PyTorch trust-policy training diagnostics.")
    parser.add_argument("--config", default="artifacts/configs/default.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    outputs = config.outputs
    figures = outputs / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    import matplotlib.pyplot as plt

    trace = pd.read_csv(outputs / "logs" / "marl_training_trace.csv")
    trace = trace[trace["epoch"] > 0].copy()
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.2))
    axes[0].plot(trace["epoch"], trace["loss"], color="#1f77b4", linewidth=1.8)
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Training loss")
    axes[0].grid(True, alpha=0.25)
    axes[0].set_title("(a) Optimization")

    axes[1].plot(trace["epoch"], trace["f_score"] * 100, color="#2ca02c", linewidth=1.8, label="F-score")
    axes[1].plot(trace["epoch"], trace["accuracy"] * 100, color="#9467bd", linewidth=1.8, label="Accuracy")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Training metric (%)")
    axes[1].set_ylim(0, 105)
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(fontsize=8)
    axes[1].set_title("(b) Train-set separation")

    fig.tight_layout()
    fig.savefig(figures / "marl_training_trace.png", dpi=180)
    plt.close(fig)
    print(f"Wrote training trace figure to {figures / 'marl_training_trace.png'}")


if __name__ == "__main__":
    main()
