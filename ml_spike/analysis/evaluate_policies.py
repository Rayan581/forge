"""Evaluate trained PPO policies vs. randomly-initialised policies on simulated
player profiles NOT seen in training (training: player_skill ~ U(0.3,0.6))."""

import glob
import importlib.util
import json
import os
import sys

import numpy as np

spec = importlib.util.spec_from_file_location(
    "tpd",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../train_ppo_difficulty.py"),
)
tpd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpd)
from stable_baselines3 import PPO  # noqa: E402

PROFILES = {  # initial player skill
    "novice (0.10)": 0.10,
    "novice (0.20)": 0.20,
    "seen-range (0.45)": 0.45,
    "skilled (0.70)": 0.70,
    "expert (0.80)": 0.80,
    "expert (0.90)": 0.90,
}
N_EP = 100  # episodes per profile (paired seeds)
TARGET_TPR = tpd.TARGET_TIME / 6.0


def run_episode(act_fn, skill, seed):
    env = tpd.DungeonDifficultyEnv()
    obs, _ = env.reset(seed=seed)
    env.player_skill = float(skill)
    obs = env._get_obs()
    R, errs, deaths, flow = [], [], [], []
    done = False
    while not done:
        a = act_fn(obs)
        obs, r, done, _, _ = env.step(a)
        R.append(r)
        tpr = env.last_time / max(1, env.params["room_count"])
        e = abs(tpr - TARGET_TPR) / TARGET_TPR
        errs.append(e)
        deaths.append(env.last_deaths)
        flow.append(1.0 if (e < 0.25 and env.last_deaths <= 1) else 0.0)
    return dict(
        reward=float(np.mean(R)),
        pace_err=float(np.mean(errs)),
        deaths=float(np.mean(deaths)),
        flow=float(np.mean(flow)),
    )


def model_fn(model):
    return lambda obs: model.predict(obs, deterministic=True)[0]


def json_policy_fn(path):
    """Exact NumPy mirror of PPOPolicy.gd: tanh hidden layers, linear output clipped to [-1, 1]."""
    layers = json.load(open(path))["layers"]
    W = [np.array(layer["w"], dtype=np.float64) for layer in layers]
    B = [np.array(layer["b"], dtype=np.float64) for layer in layers]

    def f(obs):
        x = np.asarray(obs, dtype=np.float64)
        for i, (w, b) in enumerate(zip(W, B)):
            x = w @ x + b
            if i < len(W) - 1:
                x = np.tanh(x)
        return np.clip(x, -1.0, 1.0).astype(np.float32)

    return f


def evaluate(act_fn, skill):
    rows = [run_episode(act_fn, skill, 10_000 + i) for i in range(N_EP)]
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}


if __name__ == "__main__":
    out = sys.argv[1]
    shipped = sys.argv[2]
    seeds_dir = sys.argv[3]
    trained_fns = {"shipped policy_weights.json": json_policy_fn(shipped)}
    trained = {}
    for p in sorted(glob.glob(f"{seeds_dir}/ppo_seed*.zip")):
        trained[os.path.basename(p)[:-4]] = PPO.load(p, device="cpu")
    # random-initialised policies: same architecture, untrained, several inits
    rand = {}
    for s in range(10):
        m = PPO(
            "MlpPolicy",
            tpd.DungeonDifficultyEnv(),
            policy_kwargs=dict(net_arch=[64, 64]),
            seed=1000 + s,
            device="cpu",
        )
        rand[f"random-init {s}"] = m
    res = {}
    for pname, skill in PROFILES.items():
        res[pname] = {}
        for name, fn in trained_fns.items():
            res[pname][name] = {k: v.tolist() for k, v in evaluate(fn, skill).items()}
        for name, m in trained.items():
            res[pname][name] = {k: v.tolist() for k, v in evaluate(model_fn(m), skill).items()}
        # random-init: pool the 10 initialisations (each evaluated on same paired seeds -> average per seed)
        pool = [evaluate(model_fn(m), skill) for m in rand.values()]
        res[pname]["random-init (mean of 10)"] = {
            k: np.mean([p[k] for p in pool], axis=0).tolist() for k in pool[0]
        }
        print(pname, "done", flush=True)
    json.dump(res, open(out, "w"))
