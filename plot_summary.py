#!/usr/bin/env python3
"""
Draw the one-figure summary of the solver comparison used in README.md.

Each solver is placed by how many of the 100 minimization instances it proved
optimal, and by how long it took on the ones it did prove. Up and to the left is
better, so a solver that dominates the others sits alone in that corner.

Times are the cost-minimization phase, averaged over each solver's own proven
optimal instances, taken from minimization/results/<solver>.csv.

    python plot_summary.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SOLVERS = {"chuffed": "Chuffed", "ortools": "OR-Tools", "gecode": "Gecode",
           "HiGHs": "HiGHS"}
WINNER = "chuffed"

ACCENT = "#1f6feb"   # the solver that dominates
NEUTRAL = "#57606a"  # the others
SURFACE = "#fcfcfb"
INK = "#1c2128"
MUTED = "#57606a"
GRID = "#d8dee4"

OUTPUT = "summary.png"


def read_point(solver):
    d = pd.read_csv(os.path.join("minimization", "results", f"{solver}.csv"))
    optimal = d["Min_Status"].str.strip() == "OPTIMAL"
    seconds = pd.to_numeric(d["Time_MIN_Sec"], errors="coerce")[optimal].mean()
    return int(optimal.sum()), float(seconds)


def main():
    points = {name: read_point(key) for key, name in SOLVERS.items()}
    winner = SOLVERS[WINNER]

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for name, (solved, seconds) in points.items():
        best = name == winner
        ax.scatter(seconds, solved,
                   s=260 if best else 150,
                   color=ACCENT if best else NEUTRAL,
                   edgecolors=SURFACE, linewidths=2, zorder=3)
        # direct label: identity never rests on colour alone
        ax.annotate(f"{name}\n{solved}/100 · {seconds:.1f}s",
                    (seconds, solved),
                    textcoords="offset points",
                    xytext=(16, -4) if name != "HiGHS" else (-16, -4),
                    ha="left" if name != "HiGHS" else "right",
                    va="center", fontsize=10.5,
                    color=INK if best else MUTED,
                    fontweight="bold" if best else "normal", zorder=4)

    ax.set_xscale("log")
    ax.set_xlim(1.9, 68)
    ax.set_ylim(60, 105)
    ax.set_xticks([2, 5, 10, 20, 50])
    ax.set_xticklabels(["2s", "5s", "10s", "20s", "50s"])
    ax.set_yticks([60, 70, 80, 90, 100])

    ax.set_xlabel("Mean time on the instances it proved optimal  ·  faster ←",
                  fontsize=10.5, color=MUTED, labelpad=10)
    ax.set_ylabel("Instances proved optimal  ·  more ↑",
                  fontsize=10.5, color=MUTED, labelpad=10)
    ax.set_title("Chuffed proves more instances optimal, and does it faster",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=16)

    ax.grid(True, which="major", color=GRID, linewidth=0.8, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)

    fig.text(0.008, 0.015,
             "100 instances, cost-minimization phase, 300s limit per phase",
             fontsize=9, color=MUTED)

    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(OUTPUT, facecolor=SURFACE)
    print(f"written: {OUTPUT}")
    for name, (solved, seconds) in points.items():
        print(f"  {name:10} {solved:3}/100   {seconds:6.2f}s")


if __name__ == "__main__":
    main()
