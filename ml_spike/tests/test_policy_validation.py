"""
Policy JSON validation tests.
Tests the shipped godot_prototype/ai/policy_weights.json against the
schema expected by PPOPolicy.gd, and validates a freshly exported policy
from a smoke-trained model.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import math

import numpy as np
import pytest

# Path to the shipped production policy
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROD_POLICY_PATH = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights.json")

EXPECTED_OBS_DIM = 8
EXPECTED_ACTION_DIM = 7
EXPECTED_HIDDEN_DIM = 64
EXPECTED_LAYERS = 3  # [hidden1, hidden2, action]
MAX_POLICY_SIZE_KB = 120.0


def load_policy(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


class TestProdPolicyExists:
    def test_file_exists(self):
        assert os.path.exists(PROD_POLICY_PATH), f"Policy not found at {PROD_POLICY_PATH}"

    def test_file_size_under_120kb(self):
        size_kb = os.path.getsize(PROD_POLICY_PATH) / 1024
        assert (
            size_kb < MAX_POLICY_SIZE_KB
        ), f"Policy is {size_kb:.1f} KB, exceeds {MAX_POLICY_SIZE_KB} KB target"


class TestProdPolicySchema:
    @pytest.fixture(autouse=True)
    def policy(self):
        self.data = load_policy(PROD_POLICY_PATH)

    def test_has_layers_key(self):
        assert "layers" in self.data

    def test_has_activation_key(self):
        assert "activation" in self.data

    def test_activation_is_tanh(self):
        assert self.data["activation"] == "tanh"

    def test_correct_number_of_layers(self):
        assert (
            len(self.data["layers"]) == EXPECTED_LAYERS
        ), f"Expected {EXPECTED_LAYERS} layers, got {len(self.data['layers'])}"

    def test_each_layer_has_w_and_b(self):
        for i, layer in enumerate(self.data["layers"]):
            assert "w" in layer, f"Layer {i} missing 'w'"
            assert "b" in layer, f"Layer {i} missing 'b'"

    def test_first_layer_input_dim(self):
        w = self.data["layers"][0]["w"]
        in_dim = len(w[0]) if w else 0
        assert (
            in_dim == EXPECTED_OBS_DIM
        ), f"First layer input dim: expected {EXPECTED_OBS_DIM}, got {in_dim}"

    def test_hidden_layer_dims(self):
        for i in range(2):
            w = self.data["layers"][i]["w"]
            b = self.data["layers"][i]["b"]
            out_dim = len(w)
            assert (
                out_dim == EXPECTED_HIDDEN_DIM
            ), f"Layer {i} out_dim: expected {EXPECTED_HIDDEN_DIM}, got {out_dim}"
            assert len(b) == EXPECTED_HIDDEN_DIM

    def test_action_layer_output_dim(self):
        w = self.data["layers"][-1]["w"]
        b = self.data["layers"][-1]["b"]
        assert len(w) == EXPECTED_ACTION_DIM
        assert len(b) == EXPECTED_ACTION_DIM

    def test_weights_are_finite(self):
        for i, layer in enumerate(self.data["layers"]):
            w = np.array(layer["w"])
            b = np.array(layer["b"])
            assert np.all(np.isfinite(w)), f"Layer {i} weights contain NaN/inf"
            assert np.all(np.isfinite(b)), f"Layer {i} biases contain NaN/inf"

    def test_w_b_dimensions_consistent(self):
        for i, layer in enumerate(self.data["layers"]):
            w = np.array(layer["w"])
            b = np.array(layer["b"])
            assert w.shape[0] == b.shape[0], f"Layer {i}: w rows={w.shape[0]} != b len={b.shape[0]}"


class TestProdPolicyInference:
    """
    Python reference forward-pass — mirrors PPOPolicy.gd logic exactly.
    Used to verify the production policy produces sensible outputs.
    """

    def _forward(self, policy_data: dict, obs: np.ndarray) -> np.ndarray:
        x = obs.copy().astype(np.float64)
        layers = policy_data["layers"]
        for i, layer in enumerate(layers):
            w = np.array(layer["w"], dtype=np.float64)
            b = np.array(layer["b"], dtype=np.float64)
            x = w @ x + b
            x = np.tanh(x)  # tanh applied to all layers including last
        return x

    @pytest.fixture(autouse=True)
    def policy(self):
        self.data = load_policy(PROD_POLICY_PATH)

    def test_inference_output_shape(self):
        obs = np.full(EXPECTED_OBS_DIM, 0.5, dtype=np.float32)
        out = self._forward(self.data, obs)
        assert out.shape == (EXPECTED_ACTION_DIM,)

    def test_inference_output_in_range(self):
        """tanh output must always be in (-1, 1)."""
        for seed in range(5):
            rng = np.random.default_rng(seed)
            obs = rng.uniform(0.0, 1.0, EXPECTED_OBS_DIM).astype(np.float32)
            out = self._forward(self.data, obs)
            assert np.all(out > -1.0) and np.all(out < 1.0)

    def test_inference_is_deterministic(self):
        obs = np.full(EXPECTED_OBS_DIM, 0.3, dtype=np.float32)
        out1 = self._forward(self.data, obs)
        out2 = self._forward(self.data, obs)
        np.testing.assert_array_equal(out1, out2)

    def test_inference_all_zeros_obs(self):
        obs = np.zeros(EXPECTED_OBS_DIM, dtype=np.float32)
        out = self._forward(self.data, obs)
        assert out.shape == (EXPECTED_ACTION_DIM,)
        assert np.all(np.isfinite(out))

    def test_inference_all_ones_obs(self):
        obs = np.ones(EXPECTED_OBS_DIM, dtype=np.float32)
        out = self._forward(self.data, obs)
        assert out.shape == (EXPECTED_ACTION_DIM,)
        assert np.all(np.isfinite(out))
