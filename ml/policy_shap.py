"""Stage 5: SHAP explanation of the retrained PPO policy (which observation drives which setting).

The policy is the exported JSON network (the exact function the game runs: 8 -> 64 -> 64 -> 8,
tanh, output clipped). With only 8 inputs, SHAP values are computed EXACTLY (shap's Exact
explainer, all 2^8 coalitions) against a background of observations the policy really meets in the
new simulator. Outputs:

* ``policy_shap.json`` - mean |SHAP| per (action, observation) for the new and the old policy
* ``fig_policy_shap_heatmap.png`` - 8 x 8 heatmap for the new policy (and the old one, side by side)
* ``fig_policy_shap_<action>.png`` - beeswarm for the two most-explained actions
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import sim_v2 as S
from .player_data import sim

OBS_NAMES = ["norm_time", "norm_deaths", "norm_dmg", "enemy_hp", "enemy_dmg", "hazard", "rooms",
             "level"]  # fmt: skip
ACT_NAMES = list(sim.ACTION_NAMES)


def collect_observations(env, policy, n: int, seed0: int = 70_000) -> np.ndarray:
    obs_all = []
    i = 0
    while len(obs_all) < n:
        obs, _ = env.reset(seed=seed0 + i)
        done = False
        while not done and len(obs_all) < n:
            obs_all.append(obs.copy())
            obs, _r, done, _t, _info = env.step(policy(obs))
        i += 1
    return np.asarray(obs_all, dtype=np.float64)


def explain(policy_fn, background: np.ndarray, X: np.ndarray):
    """SHAP values (N, 8 obs, 8 actions) and base values (8,)."""
    import shap

    f = lambda Z: np.asarray(policy_fn(np.asarray(Z)), dtype=np.float64)  # noqa: E731
    explainer = shap.explainers.Exact(
        f, shap.maskers.Independent(background, max_samples=len(background))
    )
    ex = explainer(X)
    return np.asarray(ex.values), np.asarray(ex.base_values)


def mean_abs_table(values) -> dict:
    m = np.abs(values).mean(axis=0)  # (8 obs, 8 act)
    return {
        a: {o: float(m[i, j]) for i, o in enumerate(OBS_NAMES)} for j, a in enumerate(ACT_NAMES)
    }


def _heatmap(ax, values, title, vmax=None):
    m = np.abs(values).mean(axis=0).T  # actions x obs
    vmax = float(m.max()) if vmax is None else vmax
    im = ax.imshow(m, cmap="Blues", aspect="auto", vmin=0.0, vmax=vmax)
    ax.set_xticks(range(len(OBS_NAMES)), OBS_NAMES, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(ACT_NAMES)), ACT_NAMES, fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=6,
                    color="white" if m[i, j] > 0.6 * vmax else "#222")  # fmt: skip
    ax.set_title(title, fontsize=10)
    return im


def run_stage(cfg: dict, player_model_path, judge_path, policy_json, out_dir: Path,
              old_policy_json=None) -> dict:  # fmt: skip
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    out_dir.mkdir(parents=True, exist_ok=True)
    pc = cfg["policy_shap"]
    env = S.DungeonDifficultyEnvV2(player_model_path, judge_path, cfg["sim"])
    new = S.json_policy_fn(policy_json)
    obs = collect_observations(env, new, int(pc["background"]) + int(pc["explain"]))
    rng = np.random.default_rng(cfg["seed"])
    rng.shuffle(obs)
    bg, X = obs[: int(pc["background"])], obs[int(pc["background"]) :]
    vals, base = explain(new, bg, X)
    # additivity check (exact SHAP: prediction = base + sum of contributions)
    add_err = float(np.abs(base + vals.sum(axis=1) - new(X)).max())
    result = {"n_background": len(bg), "n_explained": len(X), "additivity_max_err": add_err,
              "new_policy": mean_abs_table(vals), "policy_json": str(policy_json)}  # fmt: skip
    old_vals = None
    if old_policy_json and Path(old_policy_json).exists():
        old = S.json_policy_fn(old_policy_json)
        old_vals, _ = explain(old, bg, X)
        result["old_policy"] = mean_abs_table(old_vals)
        result["old_policy_json"] = str(old_policy_json)
    # top driver per action
    m = np.abs(vals).mean(axis=0)
    result["top_driver"] = {a: OBS_NAMES[int(np.argmax(m[:, j]))] for j, a in enumerate(ACT_NAMES)}
    # figures
    ncols = 2 if old_vals is not None else 1
    fig, axes = plt.subplots(1, ncols, figsize=(6.2 * ncols, 5.0), squeeze=False)
    vmax = max(float(np.abs(v).mean(axis=0).max()) for v in (vals, old_vals) if v is not None)
    _heatmap(axes[0, 0], vals, "Retrained PPO (sim-v4): mean |SHAP|", vmax)
    if old_vals is not None:
        _heatmap(axes[0, 1], old_vals, "Old PPO (sim-v3): mean |SHAP| (same scale)", vmax)
    fig.tight_layout()
    heat = out_dir / "fig_policy_shap_heatmap.png"
    fig.savefig(heat, dpi=cfg["report"]["dpi"])
    plt.close(fig)
    figs = [str(heat)]
    order = np.argsort(-m.sum(axis=0))[:2]
    for j in order:
        ex = shap.Explanation(values=vals[:, :, j], base_values=base[:, j] if base.ndim == 2 else base[j],
                              data=X, feature_names=OBS_NAMES)  # fmt: skip
        plt.figure()
        shap.plots.beeswarm(ex, show=False, max_display=8)
        plt.title(f"Policy SHAP: {ACT_NAMES[j]}", fontsize=10)
        p = out_dir / f"fig_policy_shap_{ACT_NAMES[j]}.png"
        plt.gcf().savefig(p, dpi=cfg["report"]["dpi"], bbox_inches="tight")
        plt.close("all")
        figs.append(str(p))
    result["figures"] = figs
    (out_dir / "policy_shap.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(f"[policy-shap] additivity max error {add_err:.2e}; top drivers {result['top_driver']}")
    return result
