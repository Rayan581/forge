"""
Tests for the DungeonDifficultyEnv Gymnasium environment.
Covers observation/action spaces, reset, step, reward, and termination.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from train_ppo_difficulty import (
    MAX_LEVELS,
    PARAM_ORDER,
    PARAM_RANGES,
    TARGET_TIME,
    DungeonDifficultyEnv,
    denorm,
    norm,
)


class TestNormDenorm:
    def test_norm_midpoint(self):
        """Midpoint of each range normalizes to ~0.5."""
        for key, (lo, hi) in PARAM_RANGES.items():
            mid = (lo + hi) / 2.0
            assert abs(norm(mid, key) - 0.5) < 1e-6, key

    def test_norm_clips_below(self):
        for key, (lo, _) in PARAM_RANGES.items():
            assert norm(lo - 100, key) == 0.0

    def test_norm_clips_above(self):
        for key, (_, hi) in PARAM_RANGES.items():
            assert norm(hi + 100, key) == 1.0

    def test_denorm_zero_action(self):
        """Action value 0.0 should map to midpoint of range."""
        for key, (lo, hi) in PARAM_RANGES.items():
            mid = (lo + hi) / 2.0
            assert abs(denorm(0.0, key) - mid) < 1e-5, key

    def test_denorm_minus_one(self):
        """Action value -1.0 should map to lo."""
        for key, (lo, _) in PARAM_RANGES.items():
            assert abs(denorm(-1.0, key) - lo) < 1e-5, key

    def test_denorm_plus_one(self):
        """Action value +1.0 should map to hi."""
        for key, (_, hi) in PARAM_RANGES.items():
            assert abs(denorm(1.0, key) - hi) < 1e-5, key


class TestObservationSpace:
    def test_reset_obs_shape(self, env):
        obs, info = env.reset(seed=0)
        assert obs.shape == (8,), f"Expected (8,), got {obs.shape}"

    def test_reset_obs_in_bounds(self, env):
        obs, _ = env.reset(seed=0)
        assert np.all(obs >= 0.0), "Obs below 0"
        assert np.all(obs <= 1.0), "Obs above 1"

    def test_obs_dtype(self, env):
        obs, _ = env.reset(seed=7)
        assert obs.dtype == np.float32

    def test_obs_space_dtype(self, env):
        assert env.observation_space.dtype == np.float32

    def test_obs_within_declared_space(self, env):
        for seed in range(5):
            obs, _ = env.reset(seed=seed)
            assert env.observation_space.contains(obs), (
                f"Obs {obs} not in observation_space for seed={seed}"
            )


class TestActionSpace:
    def test_action_space_shape(self, env):
        assert env.action_space.shape == (8,)

    def test_action_space_bounds(self, env):
        assert np.all(env.action_space.low == -1.0)
        assert np.all(env.action_space.high == 1.0)


class TestStep:
    def test_step_returns_five_tuple(self, env, zero_action):
        result = env.step(zero_action)
        assert len(result) == 5

    def test_step_obs_shape(self, env, zero_action):
        obs, _, _, _, _ = env.step(zero_action)
        assert obs.shape == (8,)

    def test_step_obs_in_bounds(self, env, zero_action):
        obs, _, _, _, _ = env.step(zero_action)
        assert np.all(obs >= 0.0) and np.all(obs <= 1.0)

    def test_step_reward_is_finite(self, env, zero_action):
        _, reward, _, _, _ = env.step(zero_action)
        assert np.isfinite(reward), f"Reward is not finite: {reward}"

    def test_step_truncated_is_false(self, env, zero_action):
        _, _, _, truncated, _ = env.step(zero_action)
        assert truncated is False

    def test_episode_terminates(self, env, zero_action):
        env.reset(seed=1)
        terminated = False
        for _ in range(MAX_LEVELS + 5):
            _, _, terminated, _, _ = env.step(zero_action)
            if terminated:
                break
        assert terminated, "Episode never terminated"

    def test_episode_terminates_at_max_levels(self, env, zero_action):
        env.reset(seed=2)
        terminated = False
        steps = 0
        while not terminated:
            _, _, terminated, _, _ = env.step(zero_action)
            steps += 1
            assert steps <= MAX_LEVELS + 2, "Ran past MAX_LEVELS without termination"

    def test_max_action_keeps_obs_valid(self, env, max_action):
        env.reset(seed=3)
        for _ in range(5):
            obs, reward, terminated, _, _ = env.step(max_action)
            assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
            assert np.isfinite(reward)
            if terminated:
                break

    def test_min_action_keeps_obs_valid(self, env, min_action):
        env.reset(seed=4)
        for _ in range(5):
            obs, reward, terminated, _, _ = env.step(min_action)
            assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
            assert np.isfinite(reward)
            if terminated:
                break


class TestReproducibility:
    def test_fixed_seed_identical_obs(self):
        """Same seed must produce identical observations."""
        e1 = DungeonDifficultyEnv()
        e2 = DungeonDifficultyEnv()
        obs1, _ = e1.reset(seed=99)
        obs2, _ = e2.reset(seed=99)
        np.testing.assert_array_equal(obs1, obs2)

    def test_fixed_seed_identical_rewards(self):
        action = np.zeros(8, dtype=np.float32)
        rewards1, rewards2 = [], []
        for e, r_list in [(DungeonDifficultyEnv(), rewards1), (DungeonDifficultyEnv(), rewards2)]:
            e.reset(seed=77)
            for _ in range(10):
                _, reward, terminated, _, _ = e.step(action)
                r_list.append(reward)
                if terminated:
                    break
        assert rewards1 == rewards2
