import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
    }
)
C = {
    "seed": ["#4c78a8", "#f58518", "#54a24b"],
    "rand": "#7f7f7f",
    "ship": "#d62728",
    "re": "#4c78a8",
}
# ---- Fig A: training curves
fig, ax = plt.subplots(1, 3, figsize=(10.5, 3.1))
R = []
V = []
S = []
for s in range(3):
    d = pd.read_csv(f"runs/seed{s}/progress.csv")
    t = d["time/total_timesteps"]
    r = d["rollout/ep_rew_mean"]
    ax[0].plot(t, r, color=C["seed"][s], lw=1, alpha=0.8, label=f"seed {s}")
    R.append(r.values)
    ax[1].plot(t, d["train/value_loss"], color=C["seed"][s], lw=1, alpha=0.8)
    ax[2].plot(t, d["train/std"], color=C["seed"][s], lw=1, alpha=0.8)
ax[0].plot(t, np.mean(R, 0), color="k", lw=1.8, label="mean of 3")
ax[0].set(
    title="(a) Mean episode return",
    xlabel="Training timesteps",
    ylabel="Return per 30-level episode",
)
ax[0].legend(frameon=False, fontsize=8)
ax[1].set(title="(b) Critic (value) loss", xlabel="Training timesteps", yscale="log")
ax[2].set(title="(c) Policy action std. dev.", xlabel="Training timesteps")
for a in ax:
    a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{int(x / 1000)}k"))
fig.tight_layout()
fig.savefig("fig_training_curves.pdf")
fig.savefig("fig_training_curves.png", dpi=250)
# ---- Fig B: evaluation
r = json.load(open("eval.json"))
P = list(r.keys())


def ci(x):
    x = np.array(x)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x))


fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.4))
for k, (met, lab) in enumerate(
    [
        ("reward", "Mean reward per level (higher is better)"),
        ("pace_err", "Pacing error vs. 7.5 s/room target (lower is better)"),
    ]
):
    w = 0.26
    x = np.arange(len(P))
    rand = [np.mean(r[p]["random-init (mean of 10)"][met]) for p in P]
    rc = [ci(r[p]["random-init (mean of 10)"][met]) for p in P]
    ship = [np.mean(r[p]["shipped policy_weights.json"][met]) for p in P]
    sc = [ci(r[p]["shipped policy_weights.json"][met]) for p in P]
    re = [np.mean([np.mean(r[p][f"ppo_seed{s}"][met]) for s in range(3)]) for p in P]
    rs = [np.std([np.mean(r[p][f"ppo_seed{s}"][met]) for s in range(3)], ddof=1) for p in P]
    ax[k].bar(
        x - w,
        rand,
        w,
        yerr=rc,
        color=C["rand"],
        label="Random-init policy (mean of 10)",
        capsize=2,
    )
    ax[k].bar(
        x,
        ship,
        w,
        yerr=sc,
        color=C["ship"],
        label="Trained: shipped policy_weights.json",
        capsize=2,
    )
    ax[k].bar(
        x + w,
        re,
        w,
        yerr=rs,
        color=C["re"],
        label="Trained: re-run (mean of 3 seeds, ±sd)",
        capsize=2,
    )
    ax[k].set_xticks(x)
    ax[k].set_xticklabels([p.replace(" (", "\n(") for p in P], fontsize=7.5)
    ax[k].axvspan(1.5, 2.5, color="#e6e6e6", alpha=1, lw=0, zorder=0)
    [b.set_zorder(3) for b in ax[k].patches if b.get_width() < 0.5]
    ax[k].axhline(0, color="k", lw=0.6)
    ax[k].set_title(lab, fontsize=9)
handles, labels = ax[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8)
ax[1].text(
    2,
    ax[1].get_ylim()[1] * 0.97,
    "training\nrange",
    ha="center",
    va="top",
    fontsize=7,
    color="#555",
)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig("fig_policy_eval.pdf")
fig.savefig("fig_policy_eval.png", dpi=250)
