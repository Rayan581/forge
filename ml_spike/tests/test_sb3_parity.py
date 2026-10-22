"""
Train/deploy parity: the exported policy_weights.json, run through the same
forward pass as PPOPolicy.gd, must reproduce the trained Stable-Baselines3
model's deterministic action (Gaussian mean clipped to [-1, 1]).

Before this test existed the game applied tanh to the output layer, which the
trained policy never did; mirroring PPOPolicy.gd against itself could not
catch that.
"""

import json
import os

import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL_PATH = os.path.join(REPO_ROOT, "ml_spike", "ppo_difficulty_model.zip")
POLICY_PATH = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights.json")

sb3 = pytest.importorskip("stable_baselines3")


def gd_forward(layers, obs):
    """Mirror of PPOPolicy.gd predict(): tanh hidden layers, clipped linear output."""
    x = np.asarray(obs, dtype=np.float64)
    for i, layer in enumerate(layers):
        x = np.asarray(layer["w"], dtype=np.float64) @ x + np.asarray(layer["b"], dtype=np.float64)
        if i < len(layers) - 1:
            x = np.tanh(x)
    return np.clip(x, -1.0, 1.0)


@pytest.fixture(scope="module")
def model():
    return sb3.PPO.load(MODEL_PATH, device="cpu")


@pytest.fixture(scope="module")
def layers():
    with open(POLICY_PATH) as f:
        return json.load(f)["layers"]


def test_exported_weights_match_checkpoint(model, layers):
    sd = model.policy.state_dict()
    pairs = [
        ("mlp_extractor.policy_net.0", 0),
        ("mlp_extractor.policy_net.2", 1),
        ("action_net", 2),
    ]
    for key, i in pairs:
        np.testing.assert_allclose(sd[key + ".weight"].cpu().numpy(), layers[i]["w"], atol=1e-6)
        np.testing.assert_allclose(sd[key + ".bias"].cpu().numpy(), layers[i]["b"], atol=1e-6)


def test_forward_pass_matches_sb3_predict(model, layers):
    rng = np.random.default_rng(0)
    for _ in range(500):
        obs = rng.uniform(0.0, 1.0, 8).astype(np.float32)
        want, _ = model.predict(obs, deterministic=True)
        got = gd_forward(layers, obs)
        np.testing.assert_allclose(got, want, atol=1e-5)
