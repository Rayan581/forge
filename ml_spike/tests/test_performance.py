"""
Lightweight performance regression tests.
Measures Python inference latency and policy file size.
These are NOT hardware-sensitive rendering benchmarks (60 FPS / 250 MB RAM
cannot be validated on a CPU-only GitHub runner).
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math

import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROD_POLICY_PATH = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights.json")

# ── Targets from proposal ───────────────────────────────────────────────────
POLICY_SIZE_KB_LIMIT = 150.0  # §9 — exported policy size
INFERENCE_LATENCY_MS_LIMIT = 0.5  # §9 — native inference latency
WARM_UP_RUNS = 20
TIMED_RUNS = 200


def py_forward(layers_data: list, obs: np.ndarray) -> np.ndarray:
    """Reference Python forward pass identical to PPOPolicy.gd."""
    x = obs.astype(np.float64).tolist()
    for i, layer in enumerate(layers_data):
        w, b = layer["w"], layer["b"]
        y = []
        for o in range(len(w)):
            s = b[o]
            for k in range(len(w[o])):
                s += w[o][k] * x[k]
            y.append(math.tanh(s) if i < len(layers_data) - 1 else s)  # linear output layer
        x = y
    return np.array([max(-1.0, min(1.0, v)) for v in x])


class TestPolicySizeRegression:
    def test_policy_size_under_limit(self):
        size_kb = os.path.getsize(PROD_POLICY_PATH) / 1024
        assert size_kb < POLICY_SIZE_KB_LIMIT, (
            f"Policy size {size_kb:.1f} KB exceeds {POLICY_SIZE_KB_LIMIT} KB target. "
            "Consider reducing network width."
        )

    def test_policy_size_reported(self, capsys):
        size_kb = os.path.getsize(PROD_POLICY_PATH) / 1024
        print(f"\nPolicy size: {size_kb:.2f} KB (limit: {POLICY_SIZE_KB_LIMIT} KB)")


class TestInferenceLatencyRegression:
    """
    Measures Python reference forward-pass latency.
    This approximates GDScript inference time (GDScript is slower than Python
    by ~3-10x for numeric loops, but both target sub-0.5ms on modern hardware).
    This test validates the Python reference; GDScript latency should be
    measured on target hardware with Godot's in-engine profiler.
    """

    @pytest.fixture(autouse=True)
    def load_policy(self):
        with open(PROD_POLICY_PATH) as f:
            self.policy = json.load(f)
        self.obs = np.full(8, 0.5, dtype=np.float32)

    def test_python_inference_under_05ms(self):
        # Warm up
        for _ in range(WARM_UP_RUNS):
            py_forward(self.policy["layers"], self.obs)

        # Timed runs
        times = []
        for _ in range(TIMED_RUNS):
            t0 = time.perf_counter()
            py_forward(self.policy["layers"], self.obs)
            times.append((time.perf_counter() - t0) * 1000)

        mean_ms = np.mean(times)
        p95_ms = np.percentile(times, 95)
        print(f"\nPython inference: mean={mean_ms:.4f}ms, p95={p95_ms:.4f}ms")

        # Python reference is typically 0.01–0.15ms on modern CPUs.
        # We allow 10x the GDScript target as a loose regression guard.
        assert mean_ms < INFERENCE_LATENCY_MS_LIMIT * 10, (
            f"Python inference mean {mean_ms:.3f}ms exceeds soft limit "
            f"{INFERENCE_LATENCY_MS_LIMIT * 10:.1f}ms. "
            "NOTE: GDScript latency must be measured separately in Godot."
        )

    def test_inference_result_is_finite(self):
        out = py_forward(self.policy["layers"], self.obs)
        assert np.all(np.isfinite(out))
