"""Re-runs the FORGE PPO training (identical env / hyper-parameters to
train_ppo_difficulty.py) with logging enabled, for N seeds."""

import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location(
    "tpd",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../train_ppo_difficulty.py"),
)
tpd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpd)
from stable_baselines3 import PPO  # noqa: E402
from stable_baselines3.common.logger import configure  # noqa: E402
from stable_baselines3.common.monitor import Monitor  # noqa: E402

seed = int(sys.argv[1])
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
env = Monitor(tpd.DungeonDifficultyEnv())
model = PPO(
    "MlpPolicy",
    env,
    policy_kwargs=dict(net_arch=[64, 64]),
    verbose=0,
    n_steps=2048,
    batch_size=256,
    learning_rate=3e-4,
    seed=seed,
)
model.set_logger(configure(f"{out}/seed{seed}", ["csv"]))
model.learn(total_timesteps=300_000)
model.save(f"{out}/ppo_seed{seed}")
print("done", seed)
