"""Stage 4: retrain PPO on the new simulator (sim-v4 = MLP1 + Judge) and check it does not exploit it.

Training uses exactly the sim-v3 recipe (``train_ppo_difficulty.make_model``: MlpPolicy [64, 64]
tanh, n_steps 512 x 8 envs, gamma 0.9, ...; the wide-box ``TrainWrapper``), one run per seed. The
best seed is picked on a validation set (seeds 50000+, random skill and shifts), then exported to
the JSON format PPOPolicy.gd loads (``policy_weights.json``, meta.version = sim-v4-mlp1-judge).
The exported file is written into the run folder only; copying it into the game is a manual step.

Exploit check (the PPO's reward contains a learned model, so it may find settings where the Judge
is wrong in its favour). On held-out episodes we measure:

* judge_gap   mean |D_judge - D_real|: Judge prediction vs the difficulty actually realised by the
              MLP1 player (same target formula). Must stay near the Judge's own held-out MAE:
              gap <= max(exploit_gap_factor x MAE, MAE + exploit_gap_abs). Also compared with the gap
              of uniformly random actions and of the old PPO on the same simulator.
* judge_bias  mean (D_real - D_judge): > 0 means the policy picks floors the Judge under-rates.
* ood_rate    mean share of setting features outside the Judge's training range.
* saturation  share of action entries at the box edge (|a| >= 0.98).
* old_sim     the new policy played in the OLD physics simulator (sim-v3), an independent player
              model: its pacing error may be at most ``max_old_sim_regression`` worse than the old
              PPO's. A policy that only works on the learned models fails here.
* mlp1_spread ensemble disagreement of MLP1 on the chosen floors vs on random floors (report only).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from . import sim_v2 as S
from .player_data import sim


def _vec_env(factory, n_envs, seed, kind="dummy"):
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    cls = SubprocVecEnv if kind == "subproc" and n_envs > 1 else DummyVecEnv
    return make_vec_env(factory, n_envs=n_envs, seed=seed, wrapper_class=sim.TrainWrapper,
                        vec_env_cls=cls)  # fmt: skip


def train_one(factory, seed: int, total_timesteps: int, n_envs: int, out_dir: Path, hyper=None,
              init_from=None, vec_env="dummy"):  # fmt: skip
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.logger import configure

    torch.set_num_threads(1)
    env = _vec_env(factory, n_envs, seed, vec_env)
    if init_from:
        model = PPO.load(str(init_from), env=env, device="cpu", **(hyper or {}))
    else:
        model = sim.make_model(env, seed=seed, **(hyper or {}))
    log_dir = out_dir / f"seed{seed}"
    model.set_logger(configure(str(log_dir), ["csv"]))
    model.learn(total_timesteps=int(total_timesteps), reset_num_timesteps=True)
    sim.finalize_model(model)
    path = out_dir / f"ppo_seed{seed}.zip"
    model.save(str(path))
    env.close()
    return path, log_dir / "progress.csv"


def model_policy(model):
    return lambda obs: model.predict(obs, deterministic=True)[0]


def validation_reward(env, policy, n: int, seed0: int = 50_000) -> float:
    vals = []
    for i in range(n):
        rows = S.run_episode(env, policy, seed0 + i)
        vals.append(np.mean([r["reward"] for r in rows]))
    return float(np.mean(vals))


def export_json(model, path: Path, extra_meta: dict | None = None):
    sim.export_policy_to_json(model, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["meta"]["version"] = S.SIM_VERSION
    data["meta"].update(extra_meta or {})
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def random_policy(seed=0):
    rng = np.random.default_rng(seed)
    return lambda obs: rng.uniform(-1, 1, sim.ACT_DIM)


def _old_sim_pace(policy, n, seed0=61_000):
    """Mean pacing error / deaths of a policy in the OLD physics simulator (sim-v3)."""
    pace, deaths = [], []
    for i in range(n):
        env = sim.DungeonDifficultyEnv()
        obs, _ = env.reset(seed=seed0 + i)
        done = False
        while not done:
            obs, _r, done, _, info = env.step(policy(obs))
            pace.append(info["pace_err"])
            deaths.append(info["deaths"])
    return float(np.mean(pace)), float(np.mean(deaths))


def _mlp1_spread(env, rows, n=300, seed=0):
    """Mean std across MLP1 ensemble members of the predicted outcome mean, for given floors."""
    from .player_model import build_features

    rng = np.random.default_rng(seed)
    idx = rng.choice(len(rows), size=min(n, len(rows)), replace=False)
    out = []
    for i in idx:
        r = rows[i]
        a = np.append(sim.to_action(r["params"]), 2.0 * r["c"] - 1.0)
        y, hist, base = env.pm._single_inputs(a, r["skill"], None)
        mm, _ = env.pm._member_outputs(build_features(y, [r["skill"]], base, hist), base)
        out.append(float(mm[:, 0].std(axis=0).mean()))
    return float(np.mean(out))


def exploit_check(env, policy, judge_mae: float, cfg_ppo: dict, old_policy=None, n=None) -> dict:
    n = int(n or cfg_ppo["exploit_episodes"])
    seeds = [60_000 + i for i in range(n)]
    new_eps = [S.run_episode(env, policy, s) for s in seeds]
    rnd_eps = [S.run_episode(env, random_policy(s), s) for s in seeds]
    flat_new = [r for ep in new_eps for r in ep]
    flat_rnd = [r for ep in rnd_eps for r in ep]

    def gap(rows):
        return float(np.mean([abs(r["judge"] - r["measured"]) for r in rows]))

    acts = np.array([np.append(sim.to_action(r["params"]), 2 * r["c"] - 1) for r in flat_new])
    res = {
        "episodes": n,
        "judge_test_mae": judge_mae,
        "judge_gap": gap(flat_new),
        "judge_gap_random_actions": gap(flat_rnd),
        "judge_bias": float(np.mean([r["measured"] - r["judge"] for r in flat_new])),
        "ood_rate": float(np.mean([r["ood"] for r in flat_new])),
        "saturation": float(np.mean(np.abs(acts) >= 0.98)),
        "mlp1_spread_policy": _mlp1_spread(env, flat_new),
        "mlp1_spread_random": _mlp1_spread(env, flat_rnd),
        "new_sim": S.summarize(new_eps),
    }
    n_old = max(5, n // 3)
    res["old_sim_new_policy"] = dict(zip(["pace_err", "deaths"], _old_sim_pace(policy, n_old)))
    if old_policy is not None:
        old_eps = [S.run_episode(env, old_policy, s) for s in seeds]
        res["judge_gap_old_policy"] = gap([r for ep in old_eps for r in ep])
        res["old_sim_old_policy"] = dict(
            zip(["pace_err", "deaths"], _old_sim_pace(old_policy, n_old))
        )
    mae = judge_mae if np.isfinite(judge_mae) else 0.10
    limit = max(cfg_ppo["exploit_gap_factor"] * mae, mae + cfg_ppo["exploit_gap_abs"])
    checks = {
        "judge_gap_ok": res["judge_gap"] <= limit,
        "ood_ok": res["ood_rate"] <= cfg_ppo["max_ood_rate"],
        "saturation_ok": res["saturation"] <= cfg_ppo["max_saturation_rate"],
    }
    if old_policy is not None:
        checks["old_sim_ok"] = (
            res["old_sim_new_policy"]["pace_err"]
            <= res["old_sim_old_policy"]["pace_err"] + cfg_ppo["max_old_sim_regression"]
        )
    res["judge_gap_limit"] = float(limit)
    res["checks"] = checks
    res["passed"] = bool(all(checks.values()))
    return res


def run_stage(
    cfg: dict, player_model_path, judge_path, out_dir: Path, old_policy_path=None
) -> dict:
    from stable_baselines3 import PPO

    out_dir.mkdir(parents=True, exist_ok=True)
    pc = cfg["ppo"]
    factory = S.make_env_factory(player_model_path, judge_path, cfg["sim"])
    hyper = dict(pc.get("hyper") or {})
    runs = {}
    for seed in pc["seeds"]:
        print(f"[ppo] training seed {seed} for {pc['total_timesteps']} steps on {S.SIM_VERSION}")
        path, log = train_one(factory, int(seed), pc["total_timesteps"], int(pc["n_envs"]), out_dir,
                              hyper, pc.get("init_from"), pc.get("vec_env", "dummy"))  # fmt: skip
        runs[int(seed)] = dict(model=str(path), progress=str(log))
    env = factory()
    scores = {}
    for seed, r in runs.items():
        model = PPO.load(r["model"], device="cpu")
        scores[seed] = validation_reward(env, model_policy(model), int(pc["validation_episodes"]))
        print(f"[ppo] seed {seed}: validation reward/floor {scores[seed]:.4f}")
    best = max(scores, key=scores.get)
    best_model = PPO.load(runs[best]["model"], device="cpu")
    best_zip = out_dir / "ppo_best.zip"
    best_model.save(str(best_zip))
    policy_json = export_json(best_model, out_dir / "policy_weights.json",
                              dict(best_seed=best, data_source=_data_source(player_model_path)))  # fmt: skip
    policy = S.json_policy_fn(policy_json)  # evaluate exactly what the game would run
    old = (
        S.json_policy_fn(old_policy_path)
        if old_policy_path and os.path.exists(old_policy_path)
        else None
    )
    print("[ppo] exploit check ...")
    check = exploit_check(env, policy, env.judge.test_mae, pc, old)
    summary = dict(
        sim_version=S.SIM_VERSION, runs=runs, validation_reward=scores, best_seed=best,
        best_model=str(best_zip), policy_json=str(policy_json),
        policy_json_kb=round(os.path.getsize(policy_json) / 1024, 1), exploit_check=check,
        player_model=str(player_model_path), judge=str(judge_path),
    )  # fmt: skip
    (out_dir / "ppo_summary.json").write_text(json.dumps(summary, indent=2, default=float), "utf-8")
    verdict = "PASSED" if check["passed"] else "FAILED -> see checks"
    print(f"[ppo] exploit check {verdict}: {check['checks']}")
    return summary


def _data_source(player_model_path) -> str:
    try:
        return S._load_player_model(str(player_model_path)).data_source
    except Exception:  # noqa: BLE001
        return "unknown"
