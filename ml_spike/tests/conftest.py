"""
Shared pytest fixtures for FORGE ML/RL tests.
Uses deterministic seeds throughout to ensure reproducible CI runs.
"""
import sys
import os
import pytest
import numpy as np

# Ensure ml_spike is importable when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from train_ppo_difficulty import (
    DungeonDifficultyEnv,
    PARAM_RANGES,
    PARAM_ORDER,
    norm,
    denorm,
)


@pytest.fixture
def env():
    """A freshly reset DungeonDifficultyEnv with a fixed seed."""
    e = DungeonDifficultyEnv()
    e.reset(seed=42)
    return e


@pytest.fixture
def zero_action():
    """All-zero 7-dim action (maps to midpoints of each parameter range)."""
    return np.zeros(7, dtype=np.float32)


@pytest.fixture
def max_action():
    """All-ones 7-dim action (maps to max of each parameter range)."""
    return np.ones(7, dtype=np.float32)


@pytest.fixture
def min_action():
    """All minus-one 7-dim action (maps to min of each parameter range)."""
    return np.full(7, -1.0, dtype=np.float32)
