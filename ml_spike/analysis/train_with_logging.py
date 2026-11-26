"""Trains the sim-v3 FORGE PPO policy for one seed with CSV logging.

    python ml_spike/analysis/train_with_logging.py <seed> <out_dir> [timesteps]

Writes <out_dir>/seed<seed>/progress.csv (SB3 logger) and <out_dir>/ppo_seed<seed>.zip.
Uses 8 vectorised environments (DummyVecEnv) and exactly the same hyper-parameters as
train_ppo_difficulty.make_model().
"""

import importlib.util
import os
import sys

import torch

spec = importlib.util.spec_from_file_location(
    "tpd",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../train_ppo_difficulty.py"),
)
tpd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpd)
from stable_baselines3.common.logger import configure  # noqa: E402

if __name__ == "__main__":
    torch.set_num_threads(1)
    seed = int(sys.argv[1])
    out = sys.argv[2]
    steps = int(sys.argv[3]) if len(sys.argv) > 3 else 1_000_000
    os.makedirs(out, exist_ok=True)
    env = tpd.make_vec_env(8, seed)
    model = tpd.make_model(env, seed=seed)
    model.set_logger(configure(f"{out}/seed{seed}", ["csv"]))
    model.learn(total_timesteps=steps)
    tpd.finalize_model(model)
    model.save(f"{out}/ppo_seed{seed}")
    print("done", seed)
