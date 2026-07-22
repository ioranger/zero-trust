#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
FIG_WIDTH_IN = 8.0


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt
        from matplotlib import patches
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "matplotlib is required for plotting. Install with: "
            "python3 -m pip install -r artifacts/requirements.txt"
        ) from exc
    return plt, patches


def draw_box(ax, patches, x, y, w, h, title, body, face, edge, title_color="#111111"):
    rect = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.6,
        edgecolor=edge,
        facecolor=face,
        mutation_aspect=1,
    )
    ax.add_patch(rect)
    ax.text(
        x + w / 2,
        y + h * 0.72,
        title,
        ha="center",
        va="center",
        fontsize=8.4,
        fontweight="bold",
        color=title_color,
    )
    ax.text(
        x + w / 2,
        y + h * 0.39,
        "\n".join(body),
        ha="center",
        va="center",
        fontsize=6.3,
        color="#202020",
        linespacing=1.16,
    )
    return rect


def arrow(ax, start, end, color="#333333", style="solid", lw=1.6, rad=0.0):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            linestyle=style,
            shrinkA=5,
            shrinkB=5,
            mutation_scale=15,
            connectionstyle=f"arc3,rad={rad}",
        ),
    )


def poly_arrow(ax, points, color="#333333", lw=1.6):
    xs, ys = zip(*points[:-1])
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round")
    arrow(ax, points[-2], points[-1], color=color, lw=lw)


def label(ax, x, y, text, size=6.8, color="#333333", weight="normal", ha="center"):
    ax.text(x, y, text, fontsize=size, color=color, fontweight=weight, ha=ha, va="center")


def main() -> None:
    plt, patches = require_matplotlib()
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "artifacts" / "outputs" / "figures"
    manuscript_figures = root / "paper" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    manuscript_figures.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "figure.dpi": 240,
        }
    )

    fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, 4.15))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    colors = {
        "blue_face": "#EAF3FB",
        "blue_edge": "#2D5F8B",
        "green_face": "#EAF6EF",
        "green_edge": "#2E7D59",
        "orange_face": "#FFF3E5",
        "orange_edge": "#B66A1E",
        "gray_face": "#F5F6F8",
        "gray_edge": "#565E66",
        "red_face": "#FCEEEE",
        "red_edge": "#A74747",
        "purple_face": "#F1EDFA",
        "purple_edge": "#67519B",
    }

    # Core MTIM status-update path.
    draw_box(
        ax,
        patches,
        0.04,
        0.56,
        0.175,
        0.22,
        "Summarization Agent",
        [
            "UAV and ground-control",
            "observation streams",
        ],
        colors["blue_face"],
        colors["blue_edge"],
    )
    draw_box(
        ax,
        patches,
        0.265,
        0.56,
        0.18,
        0.22,
        "Trust Branches",
        [
            "verified T1--T5 factors",
            "cross-factor checks",
        ],
        colors["green_face"],
        colors["green_edge"],
    )
    draw_box(
        ax,
        patches,
        0.495,
        0.56,
        0.18,
        0.22,
        "Supervised Risk Model",
        [
            "shared encoder + risk head",
            "auxiliary supervised heads",
        ],
        colors["gray_face"],
        colors["gray_edge"],
    )
    draw_box(
        ax,
        patches,
        0.725,
        0.56,
        0.185,
        0.22,
        "Proposed Aggregation",
        [
            "multi-observer fusion",
            "not executed in artifact",
        ],
        colors["purple_face"],
        colors["purple_edge"],
    )

    draw_box(
        ax,
        patches,
        0.34,
        0.205,
        0.25,
        0.205,
        "Proposed State Update",
        [
            "decayed prior + observation",
            "not executed in artifact",
        ],
        colors["orange_face"],
        colors["orange_edge"],
    )
    draw_box(
        ax,
        patches,
        0.68,
        0.205,
        0.235,
        0.205,
        "Allocation Proxy",
        [
            "score-weighted task sampling",
            "simulator-specific rules",
        ],
        colors["red_face"],
        colors["red_edge"],
    )

    draw_box(
        ax,
        patches,
        0.055,
        0.21,
        0.18,
        0.16,
        "Trust Memory",
        [
            "historical score",
            "recent evidence window",
        ],
        "#FAFAFA",
        "#888888",
    )

    draw_box(
        ax,
        patches,
        0.735,
        0.865,
        0.185,
        0.105,
        "Proposed Constraint",
        [
            "budgeted reward",
            "restricted access",
        ],
        "#FFFFFF",
        "#888888",
    )

    # Forward signal flow.
    arrow(ax, (0.215, 0.67), (0.265, 0.67))
    arrow(ax, (0.445, 0.67), (0.495, 0.67))
    arrow(ax, (0.675, 0.67), (0.725, 0.67))
    arrow(ax, (0.81, 0.56), (0.49, 0.41), rad=0.08)
    arrow(ax, (0.59, 0.305), (0.68, 0.305))

    # Feedback loop from the decision layer to the next update interval.
    poly_arrow(ax, [(0.80, 0.205), (0.80, 0.14), (0.28, 0.14), (0.36, 0.56)], color="#2E7D59", lw=1.45)
    label(ax, 0.55, 0.155, "proposed feedback (not executed)", size=6.3, color="#2E7D59")

    # Trust memory and policy constraints feed the next closed-loop decision.
    arrow(ax, (0.235, 0.29), (0.31, 0.56), color="#777777", style=(0, (4, 3)), lw=1.35, rad=-0.12)
    label(ax, 0.155, 0.425, "temporal evidence", size=6.1, color="#666666")
    arrow(ax, (0.82, 0.865), (0.80, 0.78), color="#777777", style=(0, (4, 3)), lw=1.25, rad=-0.08)

    # Lightweight lane labels.
    label(ax, 0.045, 0.895, "MTIM artifact and proposed deployment extensions", size=8.2, color="#222222", weight="bold", ha="left")
    ax.plot([0.045, 0.92], [0.835, 0.835], color="#D7DCE2", lw=1.1)
    label(ax, 0.045, 0.105, "The risk model and allocation proxy are executable; aggregation, state feedback, and constraints are design extensions.", size=5.9, color="#555555", ha="left")

    fig.tight_layout(pad=0.25)
    for output in [manuscript_figures / "update.png", out_dir / "update_mechanism.png"]:
        fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {manuscript_figures / 'update.png'}")
    print(f"Wrote {out_dir / 'update_mechanism.png'}")


if __name__ == "__main__":
    main()
