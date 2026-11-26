"""Pick the best of the trained seeds and ship it.

    python ml_spike/analysis/export_best.py <runs_dir> [seed|auto]

Selection ("auto") uses a held-out validation set that is disjoint from the evaluation
protocol: 200 episodes whose initial skill is drawn from the training population
U(0.05, 0.95) with seeds 50000+ (the evaluation uses fixed profiles and seeds 10000+).
Writes
  godot_prototype/ai/policy_weights.json   (8 outputs, meta.version = sim-v3)
  ml_spike/ppo_difficulty_model.zip        (SB3 checkpoint, action space [-1, 1])
"""

import glob
import importlib.util
import os
import shutil
import sys

import numpy as np
from stable_baselines3 import PPO

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
spec = importlib.util.spec_from_file_location(
    "tpd", os.path.join(HERE, "../train_ppo_difficulty.py")
)
tpd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpd)


def validation_reward(model, n=200):
    rewards = []
    for i in range(n):
        env = tpd.DungeonDifficultyEnv()
        obs, _ = env.reset(seed=50_000 + i)  # skill ~ U(0.05, 0.95), random shifts
        total, done = 0.0, False
        while not done:
            a, _ = model.predict(obs, deterministic=True)
            obs, r, done, _, _ = env.step(a)
            total += r
        rewards.append(total / tpd.MAX_LEVELS)
    return float(np.mean(rewards))


if __name__ == "__main__":
    runs = sys.argv[1]
    choice = sys.argv[2] if len(sys.argv) > 2 else "auto"
    paths = {int(os.path.basename(p)[8:-4]): p for p in glob.glob(f"{runs}/ppo_seed*.zip")}
    if choice == "auto":
        scores = {k: validation_reward(PPO.load(p, device="cpu")) for k, p in sorted(paths.items())}
        for k, v in scores.items():
            print(f"seed {k}: validation reward/floor = {v:.4f}")
        best = max(scores, key=scores.get)
    else:
        best = int(choice)
    print("best seed:", best)
    model = PPO.load(paths[best], device="cpu")
    tpd.export_policy_to_json(
        model, os.path.join(REPO, "godot_prototype", "ai", "policy_weights.json")
    )
    shutil.copy(paths[best], os.path.join(REPO, "ml_spike", "ppo_difficulty_model.zip"))
    size = os.path.getsize(os.path.join(REPO, "godot_prototype", "ai", "policy_weights.json"))
    print(f"policy_weights.json: {size / 1024:.1f} KB")
