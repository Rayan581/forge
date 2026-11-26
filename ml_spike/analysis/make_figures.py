"""Figures for the sim-v3 evaluation.

    python ml_spike/analysis/make_figures.py <runs_dir>

Reads <runs_dir>/seed*/progress.csv and ml_spike/analysis/eval_results_sim_v3.json (written by
evaluate_policies.py) and writes PNGs into ml_spike/analysis/figures/.
"""

import json
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
    }
)
# colour-blind-safe (Okabe-Ito) assignments, one colour per policy everywhere
COL = {
    "trained (exported)": "#0072B2",
    "random-init (10)": "#999999",
    "heuristic": "#E69F00",
    "static +8%": "#D55E00",
}
SEEDC = ["#0072B2", "#009E73", "#CC79A7"]
PARAMS = ["HP", "Damage", "Speed", "Aggro", "Hazard", "Scarcity", "Rooms", "Complexity (c)"]


def training_curves(runs):
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.1))
    for s in range(3):
        f = os.path.join(runs, f"seed{s}", "progress.csv")
        if not os.path.exists(f):
            continue
        d = pd.read_csv(f)
        t = d["time/total_timesteps"]
        ax[0].plot(t, d["rollout/ep_rew_mean"], color=SEEDC[s], lw=1.2, label=f"seed {s}")
        ax[1].plot(t, d["train/std"], color=SEEDC[s], lw=1.2)
        ax[2].plot(t, d["train/value_loss"], color=SEEDC[s], lw=1.2)
    ax[0].set(title="(a) Mean episode return (30 floors)", xlabel="timesteps")
    ax[1].set(title="(b) Mean action std (all 8 dims)", xlabel="timesteps")
    ax[1].axhline(0.7, color="k", lw=0.8, ls="--")
    ax[2].set(title="(c) Critic loss", xlabel="timesteps", yscale="log")
    ax[0].legend(frameon=False)
    for a in ax:
        a.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, _: f"{int(x / 1000)}k")
        )
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_training_curves_v3.png"), dpi=200)
    plt.close(fig)


def policy_eval(res):
    P = res["profiles"]
    M = res["metrics"]
    fig, ax = plt.subplots(1, 4, figsize=(14, 3.4))
    for k, (met, lab) in enumerate(
        [
            ("reward", "Reward / floor (higher better)"),
            ("pace", "Pacing error (lower better)"),
            ("deaths", "Deaths / floor (lower better)"),
            ("dact", "Mean |delta action| per floor"),
        ]
    ):
        names = list(COL)
        w = 0.8 / len(names)
        for j, n in enumerate(names):
            vals = [np.mean(M[p][n][met]) for p in P]
            err = [1.96 * np.std(M[p][n][met], ddof=1) / np.sqrt(len(M[p][n][met])) for p in P]
            ax[k].bar(
                np.arange(len(P)) + (j - 1.5) * w,
                vals,
                w,
                yerr=err,
                color=COL[n],
                label=n,
                capsize=1.5,
            )
        ax[k].set_xticks(np.arange(len(P)))
        ax[k].set_xticklabels([p.replace(" (", "\n(") for p in P], fontsize=7)
        ax[k].set_title(lab, fontsize=9)
        ax[k].axhline(0, color="k", lw=0.6)
    ax[3].axhline(0.35, color="k", lw=0.8, ls="--")
    handles, labels = ax[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(os.path.join(FIG, "fig_policy_eval_v3.png"), dpi=200)
    plt.close(fig)


def params_by_profile(res):
    P = res["profiles"]
    M = res["metrics"]
    acts = np.array([M[p]["trained (exported)"]["acts"] for p in P])  # [profile, 8] in [-1,1]
    norm = (acts + 1) / 2
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.4), gridspec_kw={"width_ratios": [1.5, 1]})
    im = ax[0].imshow(norm.T, vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax[0].set_xticks(range(len(P)))
    ax[0].set_xticklabels([p.replace(" (", "\n(") for p in P], fontsize=7)
    ax[0].set_yticks(range(8))
    ax[0].set_yticklabels(PARAMS)
    ax[0].grid(False)
    for i in range(8):
        for j in range(len(P)):
            ax[0].text(
                j,
                i,
                f"{norm[j, i]:.2f}",
                ha="center",
                va="center",
                color="w" if norm[j, i] < 0.6 else "k",
                fontsize=7,
            )
    fig.colorbar(im, ax=ax[0], label="position in range (0 = min, 1 = max)")
    ax[0].set_title("Mean parameter chosen (trained policy)")
    mix = np.array([M[p]["trained (exported)"]["mix"] for p in P])
    names = ["Crawler", "Pyromancer", "Brute", "Skirmisher", "Swarmer"]
    cols = ["#999999", "#E69F00", "#D55E00", "#0072B2", "#009E73"]
    bottom = np.zeros(len(P))
    for i in range(5):
        ax[1].bar(range(len(P)), mix[:, i], bottom=bottom, color=cols[i], label=names[i])
        bottom += mix[:, i]
    ax[1].set_xticks(range(len(P)))
    ax[1].set_xticklabels([p.split(" ")[1].strip("()") for p in P], fontsize=8)
    ax[1].set_xlabel("initial skill")
    ax[1].set_title("Mean archetype mix")
    ax[1].legend(fontsize=7, frameon=False, bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_params_by_profile_v3.png"), dpi=200)
    plt.close(fig)


def personalization(res):
    """Mean position in range of damage / scarcity / hazard vs initial skill, sim-v3 vs sim-v2."""
    P = res["profiles"]
    M = res["metrics"]
    skills = [float(p.split("(")[1].strip(")")) for p in P]
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.1), sharey=True)
    for a, (j, lab) in zip(
        ax, [(1, "enemy_damage"), (5, "resource_scarcity"), (4, "hazard_density")]
    ):
        for n, col, ls in [
            ("trained (exported)", "#0072B2", "-"),
            ("sim-v2 policy", "#999999", "--"),
        ]:
            if n not in M[P[0]]:
                continue
            y = [(M[p][n]["acts"][j] + 1) / 2 for p in P]
            a.plot(
                skills,
                y,
                color=col,
                ls=ls,
                marker="o",
                lw=1.6,
                label=n.replace("trained (exported)", "sim-v3 (shipped)"),
            )
        a.set_title(lab)
        a.set_xlabel("initial skill")
        a.set_ylim(0, 1)
    ax[0].set_ylabel("mean position in range")
    ax[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_personalization_v3.png"), dpi=200)
    plt.close(fig)


def abrupt(res):
    sc = res["scenario"]
    fig, ax = plt.subplots(2, len(sc), figsize=(4.2 * len(sc), 5.2), sharex=True)
    ax = np.atleast_2d(ax).reshape(2, -1)
    for c, (s0, cur) in enumerate(sc.items()):
        for n, v in cur.items():
            col = COL.get(n, "#bbbbbb")
            ax[0, c].plot(v["pace"], color=col, lw=1.4, label=n)
            ax[1, c].plot(v["deaths"], color=col, lw=1.4)
        for a in ax[:, c]:
            a.axvline(10, color="k", lw=0.8, ls=":")
            a.axvline(20, color="k", lw=0.8, ls=":")
        ax[0, c].axhline(0.15, color="k", lw=0.8, ls="--")
        ax[0, c].set_title(
            f"skill {float(s0):.2f} -> {float(s0) - 0.3:.2f} (floor 10) -> {float(s0):.2f} (floor 20)",
            fontsize=8,
        )
        ax[0, c].set_ylim(0, 1.2)
        ax[1, c].set_xlabel("floor")
    ax[0, 0].set_ylabel("mean pacing error")
    ax[1, 0].set_ylabel("mean deaths / floor")
    ax[0, 0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_abrupt_shift_v3.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    runs = sys.argv[1]
    training_curves(runs)
    res = json.load(open(os.path.join(HERE, "eval_results_sim_v3.json")))
    policy_eval(res)
    params_by_profile(res)
    personalization(res)
    abrupt(res)
    print("figures written to", FIG)
