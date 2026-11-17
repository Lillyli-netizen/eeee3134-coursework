# -*- coding: utf-8 -*-
"""Generate the figures used in the report (English labels only).

Outputs (relative to this file):
    figures/architecture.png
    figures/exp2_idm_seed1.png
    figures/exp2_llm_mock_seed1_stride5.png

The two time-space panels are produced by the SAME code path as the result
tables (run_comparison.run_one), so the figure and the numbers cannot drift
apart. The architecture panel is drawn from the code structure.

Usage: python make_report_figures.py [output_dir]
       (default: ./figures next to this file; in the delivered package use
        ``python make_report_figures.py ../figures``)
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from run_comparison import run_one

ROOT = Path(__file__).resolve().parent
FIG = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "figures"


def box(ax, x, y, w, h, text, fc, ec, fs=8.5):
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.012",
            linewidth=1.0, facecolor=fc, edgecolor=ec,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, wrap=True)
    return (x, y, w, h)


def arrow(ax, p0, p1):
    ax.annotate("", xy=p1, xytext=p0,
                arrowprops=dict(arrowstyle="-|>", color="#444444", lw=1.0))


def draw_architecture():
    fig, ax = plt.subplots(figsize=(9.2, 4.4), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.965, "Two-layer controller and what each stage may change",
            ha="center", va="center", fontsize=11, weight="bold")

    # Row 1: planner
    box(ax, 0.02, 0.72, 0.20, 0.16,
        "LLM client\n(mock / qwen)\nreturns JSON plan", "#e8f0fe", "#5b7fbd")
    box(ax, 0.26, 0.72, 0.22, 0.16,
        "validate_plan()\ntype / finite checks\n(reject -> keep cache)", "#f3e8fd", "#8e6bbd")
    box(ax, 0.52, 0.72, 0.22, 0.16,
        "Planner guardrails\n0 <= v <= road limit\n0.8 <= headway <= 2.0", "#fde8e8", "#bd6b6b")
    box(ax, 0.78, 0.72, 0.20, 0.16,
        "Cached plan\n(target_speed,\ntime_headway)", "#e8f7ee", "#4f9b73")

    arrow(ax, (0.22, 0.80), (0.26, 0.80))
    arrow(ax, (0.48, 0.80), (0.52, 0.80))
    arrow(ax, (0.74, 0.80), (0.78, 0.80))

    # "Plan bus": cached plan feeds the executor, passing above row 2.
    ax.plot([0.88, 0.88], [0.72, 0.655], color="#444444", lw=1.0)
    ax.plot([0.88, 0.17], [0.655, 0.655], color="#444444", lw=1.0)
    arrow(ax, (0.17, 0.655), (0.17, 0.605))

    # Row 2: executor
    box(ax, 0.02, 0.40, 0.30, 0.20,
        "EXECUTOR\nvehicle_llm.update_acceleration()\n"
        "recovery guard (past zone end)\n"
        "road-limit cap only if cached > limit\n"
        "headway ramp 0.2 s per second", "#fff6e5", "#c49a4a", fs=8)
    box(ax, 0.36, 0.40, 0.28, 0.20,
        "IDM acceleration rule\n(teacher's vehicle_idm.py,\nunchanged)\n"
        "gap term enforces the leader", "#e8f0fe", "#5b7fbd")
    box(ax, 0.68, 0.40, 0.30, 0.20,
        "Counters kept separately\nmodel output | guarded cache |\nexecuted target\n"
        "+ 1 s execution trace", "#f3e8fd", "#8e6bbd")

    arrow(ax, (0.32, 0.50), (0.36, 0.50))
    arrow(ax, (0.64, 0.50), (0.68, 0.50))

    # Row 3: framework
    box(ax, 0.02, 0.08, 0.30, 0.20,
        "Simulator loop (teacher's)\nshared arrival schedule\n"
        "admission: spacing (teacher)\n+ kinematic (ours)", "#eef1f5", "#7a8794")
    box(ax, 0.36, 0.08, 0.28, 0.20,
        "Deterministic noise\n(seed, vehicle id, step)\n"
        "same noise for every\ncontroller", "#eef1f5", "#7a8794")
    box(ax, 0.68, 0.08, 0.30, 0.20,
        "metrics.py\nvalid_until_s boundary\npair stats + comfort\n"
        "two efficiency scopes", "#eef1f5", "#7a8794")

    ax.text(0.5, 0.015,
            "Only the shaded planner/executor stages are ours; the IDM rule and the "
            "simulation loop are the teacher's original code.",
            ha="center", va="center", fontsize=7.5, color="#555555")

    FIG.mkdir(exist_ok=True)
    out = FIG / "architecture.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("written:", out)


def main():
    FIG.mkdir(exist_ok=True)
    draw_architecture()
    run_one("idm", 2, 1, time_max=1000.0, output_dir=FIG,
            ego_ids=[60], save_decisions=False, plot_stride=5)
    run_one("llm_mock", 2, 1, time_max=1000.0, output_dir=FIG,
            ego_ids=[60], save_decisions=False, plot_stride=5)
    print("figures:", sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
