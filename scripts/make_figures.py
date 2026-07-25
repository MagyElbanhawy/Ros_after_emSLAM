#!/usr/bin/env python3
"""
Generate the manuscript figures into paper_figures/ from the frozen CSVs in
paper_results/. Publication-clean, colour-blind-safe, self-contained.

    python scripts/make_figures.py
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "paper_results")
FIG = os.path.join(ROOT, "paper_figures")
os.makedirs(FIG, exist_ok=True)

# Okabe-Ito colour-blind-safe palette
C = dict(fifo="#E69F00", gated="#0072B2", plus="#009E73",
         base="#999999", accent="#D55E00")
plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
    "axes.axisbelow": True, "figure.autolayout": True,
})


def save(fig, name):
    p = os.path.join(FIG, name)
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print("->", os.path.relpath(p, ROOT))


def fig_s7c():
    d = pd.read_csv(os.path.join(RES, "s7c_paired.csv")).sort_values("n_robots")
    N = d.n_robots.values
    x = np.arange(len(N)); w = 0.38
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    ax.bar(x - w/2, d.rho_base_mean, w, yerr=d.rho_base_sd, capsize=3,
           label=r"$\hat{I}$ (base surrogate)", color=C["base"])
    ax.bar(x + w/2, d.rho_plus_mean, w, yerr=d.rho_plus_sd, capsize=3,
           label=r"$\hat{I}^{+}$ (observability)", color=C["plus"])
    for xi, dm in zip(x, d.drho_mean):
        ax.annotate(f"+{dm:.2f}", (xi, 0.02), ha="center", va="bottom",
                    fontsize=8, color=C["accent"])
    ax.set_xticks(x); ax.set_xticklabels([f"N={n}" for n in N])
    ax.set_ylabel(r"Spearman $\rho$ vs exact incremental info")
    ax.set_ylim(0, 0.8)
    ax.set_title("S7-C: surrogate fidelity to true information gain\n"
                 r"($\Delta\rho>0$ for all 40 runs, $p=9.8\times10^{-4}$ per N)",
                 fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    save(fig, "fig_s7c_fidelity.png")


def fig_s8():
    d = pd.read_csv(os.path.join(RES, "s8_30seed_summary.csv"))
    t = pd.read_csv(os.path.join(RES, "s8_30seed_tests.csv"))
    arms = ["fifo", "bacs_gated", "plus_0.30_6"]
    labels = {"fifo": "FIFO", "bacs_gated": "BACS", "plus_0.30_6": "BACS+"}
    col = {"fifo": C["fifo"], "bacs_gated": C["gated"], "plus_0.30_6": C["plus"]}
    Ns = sorted(d.n_robots.unique())
    x = np.arange(len(Ns)); w = 0.26

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), sharex=True)
    # primary: alignment
    ax = axes[0]
    for k, arm in enumerate(arms):
        sub = d[d.arm == arm].set_index("n_robots").loc[Ns]
        yerr = [sub.align_mean - sub.align_ci_lo, sub.align_ci_hi - sub.align_mean]
        ax.bar(x + (k-1)*w, sub.align_mean, w, yerr=yerr, capsize=2,
               label=labels[arm], color=col[arm])
    # significance stars: BACS+ vs FIFO on alignment
    for i, n in enumerate(Ns):
        row = t[(t.n_robots == n) & (t.metric == "align_rmse")
                & (t.arm_a == "plus_0.30_6") & (t.arm_b == "fifo")]
        if len(row) and row.wilcoxon_p.iloc[0] < 0.05:
            yv = d[(d.n_robots == n) & (d.arm == "plus_0.30_6")].align_ci_hi.iloc[0]
            ax.annotate("*", (x[i] + w, yv + 0.01), ha="center", fontsize=13,
                        color=C["plus"])
    ax.set_xticks(x); ax.set_xticklabels([f"N={n}" for n in Ns])
    ax.set_ylabel("Map-alignment RMSE [m]  (95% CI)")
    ax.set_title("Primary: map-fusion consistency", fontsize=9)
    ax.legend(frameon=False, fontsize=8)

    # secondary: pose (no significant effect)
    ax = axes[1]
    for k, arm in enumerate(arms):
        sub = d[d.arm == arm].set_index("n_robots").loc[Ns]
        ax.bar(x + (k-1)*w, sub.pose_mean, w, color=col[arm], label=labels[arm])
    ax.set_xticks(x); ax.set_xticklabels([f"N={n}" for n in Ns])
    ax.set_ylabel("Per-step pose RMSE [m]")
    ax.set_title("Secondary: pose RMSE (no significant effect)", fontsize=9)
    fig.suptitle("S8 (30 held-out seeds): scheduling improves map alignment, "
                 "not odometry-bound pose RMSE", fontsize=10)
    save(fig, "fig_s8_alignment_vs_pose.png")


def fig_s9():
    d = pd.read_csv(os.path.join(RES, "s9_deferral_gamma.csv"))
    order = ["fixed 0.003", "drift derived", "drift adaptive",
             "deferral derived", "deferral adaptive"]
    present = [r for r in order if r in d["rule"].values]
    d = d.set_index("rule").loc[present].reset_index()
    colors = [C["base"], C["fifo"], C["fifo"], C["plus"], C["gated"]]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    x = np.arange(len(d))
    ax.bar(x, d.pose_rmse_mean, yerr=d.pose_rmse_std, capsize=3,
           color=colors[:len(d)])
    for xi, g in zip(x, d.gamma_mean):
        ax.annotate(rf"$\gamma$={g:.4f}", (xi, 0.01), ha="center", va="bottom",
                    fontsize=8, rotation=90, color="white")
    ax.axhline(d.pose_rmse_mean.iloc[0], ls="--", color=C["base"], lw=1,
               label="tuned optimum")
    ax.set_xticks(x); ax.set_xticklabels(d.rule, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Per-step pose RMSE [m]")
    ax.set_title("S9: deferral-derived $\\gamma$ recovers the optimum\n"
                 "(drift derivation of Eq. 16 is falsified)", fontsize=9)
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig_s9_gamma.png")


def fig_progression():
    d = pd.read_csv(os.path.join(RES, "progression.csv"))
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    x = np.arange(len(d))
    ax.errorbar(x, d.pose_rmse_mean, yerr=d.pose_rmse_std, marker="o",
                color=C["gated"], capsize=3, label="pose RMSE")
    ax.errorbar(x, d.align_rmse_mean, yerr=d.align_rmse_std, marker="s",
                color=C["plus"], capsize=3, label="map-alignment RMSE")
    ax.set_xticks(x)
    ax.set_xticklabels([s.split(" (")[0] for s in d.stage], rotation=15,
                       ha="right", fontsize=8)
    ax.set_ylabel("RMSE [m]")
    ax.set_title("Methodological progression: EMRMF-original → BACS+", fontsize=9)
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig_progression.png")


if __name__ == "__main__":
    fig_s7c(); fig_s8(); fig_s9(); fig_progression()
    print("figures done")
