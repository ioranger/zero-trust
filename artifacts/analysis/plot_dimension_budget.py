#!/usr/bin/env python3
"""Plot the dimension-budget series of the channel-focused scenario.

The chart answers the question the ablation asks: what does a deployment
that can observe k of the five trust dimensions detect? Every point is one
trained arm, the band is the spread of the arms at the same budget, and the
star is the configuration the manuscript proposes. The second panel shows
the mechanism: the attackers on the dimensions the deployment observes are
detected, the attackers on the dimensions it does not observe are not.

Usage:
    python -u artifacts/analysis/plot_dimension_budget.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "artifacts" / "outputs" / "tables" / "channel_profile_dimension_budget.csv"
FIGURES = ROOT / "paper" / "figures"

FACTORS = ["T1", "T2", "T3", "T4", "T5"]


def main() -> int:
    df = pd.read_csv(TABLE)
    FIGURES.mkdir(parents=True, exist_ok=True)

    blue = "#1f77b4"
    red = "#d62728"
    green = "#2ca02c"

    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.1))

    ax = axes[0]
    for _, row in df[df["k"] < 5].iterrows():
        ax.plot(row["k"], row["accuracy"], "o", markersize=4.5,
                color="#9ecae1", markeredgecolor="#4a6fa5", zorder=2)
    ks = sorted(df["k"].unique())
    means = [df[df["k"] == k]["accuracy"].mean() for k in ks]
    los = [df[df["k"] == k]["accuracy"].min() for k in ks]
    his = [df[df["k"] == k]["accuracy"].max() for k in ks]
    ax.vlines(ks, los, his, color=blue, linewidth=6, alpha=0.22, zorder=1)
    ax.plot(ks, means, "-o", color=blue, linewidth=1.8, markersize=5, zorder=3)
    ref = df[df["k"] == 5].iloc[0]
    ax.plot([5], [ref["accuracy"]], "*", markersize=15, color=red,
            markeredgecolor="black", markeredgewidth=0.4, zorder=5)
    ax.annotate("proposed configuration\n(all five dimensions)",
                xy=(4.93, ref["accuracy"]), xytext=(1.25, 97.0),
                fontsize=7.5, ha="left", va="top", color=red,
                arrowprops=dict(arrowstyle="->", color=red, linewidth=0.8,
                                shrinkA=0, shrinkB=4,
                                connectionstyle="arc3,rad=-0.15"))
    ax.set_xticks(ks)
    ax.set_xlabel("dimensions the deployment observes, $k$", fontsize=8.5)
    ax.set_ylabel("Accuracy (\\%)", fontsize=8.5)
    ax.set_ylim(66, 101)
    ax.grid(True, alpha=0.25)
    ax.tick_params(labelsize=8)
    ax.set_title("(a) Accuracy against the observation budget",
                 fontsize=9)

    ax = axes[1]
    obs, unobs = [], []
    for k in ks:
        group = df[df["k"] == k]
        o, u = [], []
        for _, row in group.iterrows():
            observed = [f.strip() for f in str(row["observed"]).split(",")]
            for f in FACTORS:
                value = row["detection_" + f]
                (o if f in observed else u).append(value)
        obs.append(sum(o) / len(o))
        unobs.append(sum(u) / len(u) if u else float("nan"))
    ax.plot(ks, obs, "-o", color=green, linewidth=1.8, markersize=5,
            label="attacker on an observed dimension")
    ax.plot(ks, unobs, "--s", color=red, linewidth=1.8, markersize=5,
            label="attacker on an unobserved dimension")
    ax.set_xticks(ks)
    ax.set_xlabel("dimensions the deployment observes, $k$", fontsize=8.5)
    ax.set_ylabel("Detection rate (\\%)", fontsize=8.5)
    ax.set_ylim(-4, 104)
    ax.grid(True, alpha=0.25)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7.5, loc="center left")
    ax.set_title("(b) Where the evidence is", fontsize=9)

    fig.tight_layout()
    out = FIGURES / "dimension_budget.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote " + str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
