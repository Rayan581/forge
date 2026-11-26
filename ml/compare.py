"""Stage 6b: compare FORGE (retrained PPO) with the baselines.

Conditions (all play the same paired players: same seed -> same skill trajectory):

* ``bsp_fixed``   BSP layout generator + fixed Intermediate settings (non-adaptive, no PPO).
                  Room count = the BSP layout's room count (5-9).
* ``static_8pct`` the game's static baseline: Intermediate, HP and damage x (1 + 0.08 (floor - 1)).
* ``ppo_old``     PPO trained on the OLD simulator (sim-v3), i.e. the policy the game ships today.
* ``ppo_new``     PPO retrained on the NEW simulator (sim-v4: MLP1 + Judge), stage 4.

Each condition is scored in BOTH simulators: sim-v4 (the models learned from data) and sim-v3 (the
hand-written physics). A result that holds in both does not depend on one player model.

Metrics
* difficulty fit   mean |D_real - D_target| (realised measured difficulty vs the target band)
* pace error       mean |s/room - 7.5| / 7.5;  deaths / floor;  damage ratio
* adaptation speed floors until the mean pace error is back under ``recover_thr`` for 2 floors,
                   after a scripted skill change of ``shift_delta`` at floor ``shift_floor``
                   (player starts at skill 0.70)
* layout variety   solvable %, rooms, start->exit path, dead ends, branching, size variance,
                   unique shapes, pairwise layout distance (``ml/layouts.py``)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from . import layouts as L
from . import sim_v2 as S
from .judge_bridge import measured_difficulty
from .player_data import sim

CONDITIONS = ["bsp_fixed", "static_8pct", "ppo_old", "ppo_new"]


def bsp_schedule(rng, cfg_b):
    def f(_floor):
        lay = L.bsp_layout(rng, cfg_b["bsp_min_rooms"], cfg_b["bsp_max_rooms"])
        p = dict(sim.INTERMEDIATE)
        p["room_count"] = float(len(lay.rooms))
        return p, sim.STATIC_A7

    return f


# ---- old simulator (sim-v3) helpers -------------------------------------------------------------
def _old_step_params(env, params, a7):
    env.params = dict(params)
    env.params["room_count"] = float(round(env.params["room_count"]))
    env.a7 = a7
    mix = sim.archetype_mix(a7)
    res = env._simulate(env.params, mix)
    res["c"] = (a7 + 1.0) / 2.0
    vec = np.append(sim.to_action(env.params), a7)
    reward, parts = env._finish_level(res, vec)
    info = dict(time=res["time"], deaths=res["deaths"], dmg_ratio=res["dmg_ratio"],
                rooms=res["rooms"], skill=env.skill, **parts)  # fmt: skip
    return env._get_obs(), reward, env.level >= sim.MAX_LEVELS, info


def old_episode(policy, seed, options, target):
    env = sim.DungeonDifficultyEnv()
    obs, _ = env.reset(seed=seed, options=options)
    rows, done, floor = [], False, 0
    while not done:
        floor += 1
        if callable(policy):
            obs, r, done, _, info = env.step(policy(obs))
        else:
            p, a7 = policy[1](floor)
            obs, r, done, info = _old_step_params(env, p, a7)
        info = dict(info)
        info["reward"] = r
        info["measured"] = measured_difficulty(
            info["time"], info["deaths"], info["dmg_ratio"], info["rooms"]
        )
        info["target"] = target
        rows.append(info)
    return rows


def _policy_for(name, cfg_b, policies, seed):
    if name == "bsp_fixed":
        return ("params", bsp_schedule(np.random.default_rng([seed, 99]), cfg_b))
    if name == "static_8pct":
        return ("params", S.static_schedule)
    return policies[name]


def _metrics(eps):
    def m(key):
        return float(np.mean([np.mean([r[key] for r in ep]) for ep in eps]))

    return dict(
        reward=m("reward"), pace_err=m("pace_err"), deaths=m("deaths"), dmg_ratio=m("dmg_ratio"),
        fit_err=float(np.mean([np.mean([abs(r["measured"] - r["target"]) for r in ep]) for ep in eps])),
        measured=m("measured"), rooms=m("rooms"), n_episodes=len(eps),
    )  # fmt: skip


def recovery_floors(curve, start, thr, margin=0.05, horizon=12):
    """Floors (1 = the first affected floor) until the pace error is back under
    max(thr, pre-shift level + margin) for two floors in a row; None if not within ``horizon``.
    The pre-shift level is the mean of the 5 floors before the shift, so a simulator whose noise
    floor is above ``thr`` (sim-v4) is judged against its own baseline."""
    pre = float(np.mean(curve[max(0, start - 5) : start])) if start > 0 else 0.0
    lim = max(thr, pre + margin)
    for k in range(horizon):
        i = start + k
        if i + 1 < len(curve) and curve[i] <= lim and curve[i + 1] <= lim:
            return k + 1
    return None


def shift_impact(curve, start, n=3):
    """Mean pace error over the first n affected floors minus the pre-shift level."""
    pre = float(np.mean(curve[max(0, start - 5) : start])) if start > 0 else 0.0
    return float(np.mean(curve[start : start + n]) - pre)


def run_stage(cfg, player_model_path, judge_path, new_policy_json, out_dir: Path,
              old_policy_json=None) -> dict:  # fmt: skip
    out_dir.mkdir(parents=True, exist_ok=True)
    cb = cfg["baselines"]
    env = S.DungeonDifficultyEnvV2(player_model_path, judge_path, cfg["sim"])
    target = env.target_difficulty(0.5)
    policies = {"ppo_new": S.json_policy_fn(new_policy_json)}
    conds = ["bsp_fixed", "static_8pct", "ppo_new"]
    if old_policy_json and Path(old_policy_json).exists():
        policies["ppo_old"] = S.json_policy_fn(old_policy_json)
        conds.insert(2, "ppo_old")
    n = int(cb["episodes"])
    res = {"conditions": conds, "new_sim": {}, "old_sim": {}, "adaptation": {}, "per_profile": {}}
    room_counts_new = []
    for name in conds:
        new_all, old_all = [], []
        res["per_profile"][name] = {}
        for prof in cb["profiles"]:
            seeds = [10_000 + i for i in range(n)]
            opts = {"skill": float(prof)}
            ne = [S.run_episode(env, _policy_for(name, cb, policies, s), s, opts) for s in seeds]
            oe = [old_episode(_policy_for(name, cb, policies, s), s, opts, target) for s in seeds]
            new_all += ne
            old_all += oe
            res["per_profile"][name][str(prof)] = dict(new_sim=_metrics(ne), old_sim=_metrics(oe))
            if name == "ppo_new":
                room_counts_new += [int(r["rooms"]) for ep in ne for r in ep]
        res["new_sim"][name] = _metrics(new_all)
        res["old_sim"][name] = _metrics(old_all)
        # adaptation: skill 0.70, scripted shift at shift_floor (index shift_floor - 1)
        shifts = {int(cb["shift_floor"]) - 1: float(cb["shift_delta"])}
        opts = {"skill": 0.70, "shifts": shifts}
        seeds = [30_000 + i for i in range(n)]
        curves = {}
        for sim_name, fn in [("new_sim", lambda p, s: S.run_episode(env, p, s, opts)),
                             ("old_sim", lambda p, s: old_episode(p, s, opts, target))]:  # fmt: skip
            eps = [fn(_policy_for(name, cb, policies, s), s) for s in seeds]
            pace = np.mean([[r["pace_err"] for r in ep] for ep in eps], axis=0)
            fit = np.mean([[abs(r["measured"] - r["target"]) for r in ep] for ep in eps], axis=0)
            curves[sim_name] = dict(
                pace_curve=pace.tolist(), fit_curve=fit.tolist(),
                recovery_floors=recovery_floors(pace, int(cb["shift_floor"]) - 1, cb["recover_thr"],
                                                cb["recover_margin"]),
                shift_impact=shift_impact(pace, int(cb["shift_floor"]) - 1),
            )  # fmt: skip
        res["adaptation"][name] = curves
        print(f"[baselines] {name}: new-sim fit {res['new_sim'][name]['fit_err']:.3f} "
              f"pace {res['new_sim'][name]['pace_err']:.3f} | old-sim pace "
              f"{res['old_sim'][name]['pace_err']:.3f}")  # fmt: skip
    # layout variety and solvability
    variety, _ = L.variety_table(int(cb["layouts_per_generator"]), cfg["seed"],
                                 room_counts_new or [6], 6, cb["bsp_min_rooms"], cb["bsp_max_rooms"])  # fmt: skip
    res["variety"] = variety
    res["target_difficulty"] = target
    res["shift_floor"] = int(cb["shift_floor"])
    (out_dir / "comparison.json").write_text(json.dumps(res, indent=2, default=float), "utf-8")
    _write_csv(out_dir / "comparison.csv", res)
    _write_variety_csv(out_dir / "variety.csv", variety)
    res["figures"] = _figures(res, out_dir, cfg["report"]["dpi"])
    (out_dir / "comparison.json").write_text(json.dumps(res, indent=2, default=float), "utf-8")
    return res


def _write_csv(path, res):
    cols = ["condition", "simulator", "fit_err", "pace_err", "deaths", "dmg_ratio", "measured",
            "rooms", "reward", "recovery_floors"]  # fmt: skip
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for name in res["conditions"]:
            for s in ("new_sim", "old_sim"):
                m = res[s][name]
                rec = res["adaptation"][name][s]["recovery_floors"]
                w.writerow([name, s] + [round(m[c], 4) for c in cols[2:-1]] + [rec])


def _write_variety_csv(path, variety):
    keys = list(next(iter(variety.values())).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["generator"] + keys)
        for g, row in variety.items():
            w.writerow([g] + [round(v, 4) if isinstance(v, float) else v for v in row.values()])


def _figures(res, out_dir, dpi):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = []
    conds = res["conditions"]
    colors = {
        "bsp_fixed": "#8c8c8c",
        "static_8pct": "#c9a227",
        "ppo_old": "#5b8fd9",
        "ppo_new": "#1f4e9e",
    }
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, key, title in zip(axes, ["fit_err", "pace_err", "deaths"],
                              ["Difficulty fit |D_real - D_target|", "Pace error", "Deaths / floor"]):  # fmt: skip
        x = np.arange(2)
        w = 0.8 / len(conds)
        for i, c in enumerate(conds):
            vals = [res["new_sim"][c][key], res["old_sim"][c][key]]
            ax.bar(x + (i - (len(conds) - 1) / 2) * w, vals, w, label=c, color=colors.get(c))
        ax.set_xticks(x, ["sim-v4 (MLP1+Judge)", "sim-v3 (physics)"], fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    p = out_dir / "fig_baseline_comparison.png"
    fig.savefig(p, dpi=dpi)
    plt.close(fig)
    figs.append(str(p))

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, s in zip(axes, ["new_sim", "old_sim"]):
        for c in conds:
            curve = res["adaptation"][c][s]["pace_curve"]
            ax.plot(np.arange(1, len(curve) + 1), curve, label=c, color=colors.get(c))
        ax.axvline(res_shift(res), color="#c33", ls="--", lw=1)
        ax.set_title(f"Pace error after skill shift ({s})", fontsize=10)
        ax.set_xlabel("floor")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    p = out_dir / "fig_adaptation.png"
    fig.savefig(p, dpi=dpi)
    plt.close(fig)
    figs.append(str(p))

    v = res["variety"]
    keys = [("pairwise_dist", "Pairwise layout distance"), ("unique_shapes_pct", "Unique shapes %"),
            ("path_len", "Start->exit doors"), ("size_var", "Room-size variance")]  # fmt: skip
    fig, axes = plt.subplots(1, len(keys), figsize=(12, 3.2))
    for ax, (k, t) in zip(axes, keys):
        ax.bar(list(v), [v[g][k] for g in v], color=["#1f4e9e", "#c9a227", "#8c8c8c"])
        ax.set_title(t, fontsize=10)
        ax.tick_params(axis="x", labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = out_dir / "fig_layout_variety.png"
    fig.savefig(p, dpi=dpi)
    plt.close(fig)
    figs.append(str(p))
    return figs


def res_shift(res):
    return res.get("shift_floor", 10)
