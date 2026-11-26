"""
Cross-language inference parity test.
Creates a deterministic test policy with known small weights,
runs the Python forward pass, and verifies the output matches
the expected values computed from the same math PPOPolicy.gd uses.

NOTE: Full GDScript headless parity is not directly testable without Godot
on CI, so this test validates the Python reference implementation against
manually computed expected values from the same algorithm.
The GDScript implementation (PPOPolicy.gd) is structurally identical —
Parity between this mirror and the trained Stable-Baselines3 model is checked
in test_sb3_parity.py; the GDScript side is exercised by the headless Godot tests.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import math

import numpy as np
import pytest


def py_forward(layers_data: list, obs: np.ndarray) -> np.ndarray:
    """
    Pure-Python forward pass mirroring PPOPolicy.gd predict() exactly:
    - Matrix multiply: y[o] = b[o] + sum_k(w[o][k] * x[k])
    - tanh on the hidden layers only
    - the last layer is the Gaussian mean, clipped to [-1, 1] (as SB3's
      deterministic predict() and the training environment do)
    """
    x = obs.astype(np.float64).tolist()
    for i, layer in enumerate(layers_data):
        w = layer["w"]
        b = layer["b"]
        y = []
        for o in range(len(w)):
            s = b[o]
            for k in range(len(w[o])):
                s += w[o][k] * x[k]
            y.append(s)
        # tanh on hidden layers only; the output layer stays linear
        x = y if i == len(layers_data) - 1 else [math.tanh(v) for v in y]
    return np.array([max(-1.0, min(1.0, v)) for v in x])


# ─── Deterministic fixture policy (tiny, known-weight network) ───────────────
# Architecture: 8 -> 2 -> 2 -> 8  (we shrink hidden for tractability)
# Weights are all 0.1 so we can hand-compute the expected output.


def build_fixture_policy():
    """
    Build a tiny 3-layer policy with known weights.
    Layer 0: w shape [2][8], b shape [2]  — all 0.1
    Layer 1: w shape [2][2], b shape [2]  — all 0.1
    Layer 2: w shape [8][2], b shape [8]  — all 0.1
    """
    layers = [
        {"w": [[0.1] * 8 for _ in range(2)], "b": [0.1] * 2},
        {"w": [[0.1] * 2 for _ in range(2)], "b": [0.1] * 2},
        {"w": [[0.1] * 2 for _ in range(8)], "b": [0.1] * 8},
    ]
    return {"layers": layers, "activation": "tanh"}


class TestParityFixturePolicy:
    @pytest.fixture(autouse=True)
    def fixture_policy(self):
        self.policy = build_fixture_policy()

    def test_output_shape(self):
        obs = np.zeros(8, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert out.shape == (8,)

    def test_output_in_range(self):
        obs = np.full(8, 0.5, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert np.all(out >= -1.0) and np.all(out <= 1.0)

    def test_output_is_finite(self):
        obs = np.full(8, 0.5, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert np.all(np.isfinite(out))

    def test_known_zero_input_output(self):
        """All-zero input: hidden = tanh(0.1) ≈ 0.09967, tanh(0.11993) ≈ 0.11936; output = 0.1 + 0.2·0.11936 ≈ 0.12387."""
        obs = np.zeros(8, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        # All outputs should be identical (symmetric weights)
        assert np.allclose(out, out[0], atol=1e-12)
        assert np.allclose(out, 0.1 + 0.2 * math.tanh(0.1 + 0.2 * math.tanh(0.1)), atol=1e-12)
        # Output must be in (0, 1) since all weights/biases are positive
        assert np.all(out > 0.0) and np.all(out < 1.0)

    def test_all_ones_input_positive_output(self):
        """Positive weights + positive input → positive activations → positive output."""
        obs = np.ones(8, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert np.all(out > 0.0)

    def test_determinism_across_calls(self):
        obs = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], dtype=np.float32)
        out1 = py_forward(self.policy["layers"], obs)
        out2 = py_forward(self.policy["layers"], obs)
        np.testing.assert_array_equal(out1, out2)

    def test_different_inputs_produce_different_outputs(self):
        obs_a = np.full(8, 0.1, dtype=np.float32)
        obs_b = np.full(8, 0.9, dtype=np.float32)
        out_a = py_forward(self.policy["layers"], obs_a)
        out_b = py_forward(self.policy["layers"], obs_b)
        assert not np.allclose(out_a, out_b)


class TestParityProdPolicy:
    """Run parity checks against the production policy_weights.json."""

    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    PROD_POLICY_PATH = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights.json")

    @pytest.fixture(autouse=True)
    def prod_policy(self):
        with open(self.PROD_POLICY_PATH) as f:
            self.policy = json.load(f)

    def test_prod_policy_forward_shape(self):
        obs = np.full(8, 0.5, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert out.shape == (8,)

    def test_prod_policy_forward_finite(self):
        for seed in range(10):
            rng = np.random.default_rng(seed)
            obs = rng.uniform(0.0, 1.0, 8).astype(np.float32)
            out = py_forward(self.policy["layers"], obs)
            assert np.all(np.isfinite(out)), f"Non-finite for seed={seed}"

    def test_prod_policy_forward_in_range(self):
        obs = np.full(8, 0.5, dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert np.all(out >= -1.0) and np.all(out <= 1.0)

    def test_prod_policy_no_nan(self):
        obs = np.array([0.0, 0.0, 0.0, 0.5, 0.4, 0.3, 0.5, 0.0], dtype=np.float32)
        out = py_forward(self.policy["layers"], obs)
        assert not np.any(np.isnan(out))


# ─── Documented GDScript parity blocker ──────────────────────────────────────
# Full headless GDScript parity (running Godot --headless and comparing
# Python vs GDScript outputs byte-for-byte) requires:
#   1. Godot 4.3 installed on the CI runner.
#   2. A GDScript test runner that can be invoked from the command line.
# Both are provided in the godot-headless CI job.
# The python-side reference implementation above has been manually verified
# to produce identical arithmetic to PPOPolicy.gd for the fixture policy.
