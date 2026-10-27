"""
PPO smoke test — verifies model init, short training, save/load, and inference.
Does NOT run the full 300k-step research training.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import numpy as np
import pytest
from stable_baselines3 import PPO

from train_ppo_difficulty import DungeonDifficultyEnv, export_policy_to_json


class TestPPOSmoke:
    SMOKE_STEPS = 1024  # fast — finishes in <30s on any CI runner

    def test_env_constructs(self):
        env = DungeonDifficultyEnv()
        assert env is not None

    def test_ppo_initializes(self):
        env = DungeonDifficultyEnv()
        model = PPO(
            "MlpPolicy",
            env,
            policy_kwargs=dict(net_arch=[64, 64]),
            verbose=0,
            n_steps=256,
            batch_size=64,
        )
        assert model is not None

    def test_ppo_smoke_training(self):
        env = DungeonDifficultyEnv()
        model = PPO(
            "MlpPolicy",
            env,
            policy_kwargs=dict(net_arch=[64, 64]),
            verbose=0,
            n_steps=256,
            batch_size=64,
            seed=42,
        )
        model.learn(total_timesteps=self.SMOKE_STEPS)
        # If we reached here without exception the training loop works
        assert True

    def test_ppo_save_and_load(self, tmp_path):
        env = DungeonDifficultyEnv()
        model = PPO(
            "MlpPolicy",
            env,
            policy_kwargs=dict(net_arch=[64, 64]),
            verbose=0,
            n_steps=256,
            batch_size=64,
            seed=1,
        )
        model.learn(total_timesteps=self.SMOKE_STEPS)
        save_path = str(tmp_path / "smoke_model")
        model.save(save_path)
        assert os.path.exists(save_path + ".zip")

        loaded = PPO.load(save_path, env=env)
        assert loaded is not None

    def test_ppo_inference_produces_valid_action(self, tmp_path):
        env = DungeonDifficultyEnv()
        model = PPO(
            "MlpPolicy",
            env,
            policy_kwargs=dict(net_arch=[64, 64]),
            verbose=0,
            n_steps=256,
            batch_size=64,
            seed=2,
        )
        model.learn(total_timesteps=self.SMOKE_STEPS)
        obs, _ = env.reset(seed=10)
        action, _ = model.predict(obs, deterministic=True)
        assert action.shape == (8,)
        assert np.all(action >= -1.0)
        assert np.all(action <= 1.0)
        assert np.all(np.isfinite(action))

    def test_policy_export_produces_valid_json(self, tmp_path):
        env = DungeonDifficultyEnv()
        model = PPO(
            "MlpPolicy",
            env,
            policy_kwargs=dict(net_arch=[64, 64]),
            verbose=0,
            n_steps=256,
            batch_size=64,
            seed=3,
        )
        model.learn(total_timesteps=self.SMOKE_STEPS)
        export_path = str(tmp_path / "test_policy.json")
        export_policy_to_json(model, export_path)

        assert os.path.exists(export_path)
        with open(export_path) as f:
            data = json.load(f)

        assert "layers" in data
        assert "activation" in data
        assert data["activation"] == "tanh"
        assert len(data["layers"]) == 3  # 2 hidden + 1 action layer
        for layer in data["layers"]:
            assert "w" in layer
            assert "b" in layer
            w = np.array(layer["w"])
            b = np.array(layer["b"])
            assert np.all(np.isfinite(w))
            assert np.all(np.isfinite(b))
