"""
Tests for simulator v3: skill-dependent effects of enemy_damage and resource_scarcity, the two
v3 experience priors, and the shipped policy actually personalising those two attributes.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

import train_ppo_difficulty as tpd
from train_ppo_difficulty import DungeonDifficultyEnv, archetype_mix

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEIGHTS = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights.json")
DMG, SCAR = 1, 5  # indices in the action vector


def _time_per_room(action, skill, seeds=60):
    a = np.clip(np.asarray(action, dtype=np.float64), -1, 1)
    params = {k: float(tpd.denorm(a[i], k)) for i, k in enumerate(tpd.PARAM_ORDER)}
    params["room_count"] = float(round(params["room_count"]))
    mix = archetype_mix(a[7])
    env = DungeonDifficultyEnv()
    out = []
    for s in range(seeds):
        env.reset(seed=s, options={"skill": skill, "random_shifts": False})
        env.bias = 0.0
        env.rng = np.random.default_rng(s + 99)
        r = env._simulate(params, mix)
        out.append(r["time"] / r["rooms"])
    return float(np.mean(out))


def _policy(path=WEIGHTS):
    layers = json.load(open(path))["layers"]
    W = [np.array(layer["w"]) for layer in layers]
    B = [np.array(layer["b"]) for layer in layers]

    def f(obs):
        x = np.asarray(obs, dtype=np.float64)
        for i, (w, b) in enumerate(zip(W, B)):
            x = w @ x + b
            if i < len(W) - 1:
                x = np.tanh(x)
        return np.clip(x, -1.0, 1.0)

    return f


class TestSkillDependentEffects:
    def test_damage_slows_low_reflex_players_more(self):
        """Hard-hitting enemies make low-reflex players play defensively; high-reflex ones barely care."""
        lo = np.zeros(8)
        hi = np.zeros(8)
        lo[DMG], hi[DMG] = -1.0, 1.0
        d_low = _time_per_room(hi, 0.15) - _time_per_room(lo, 0.15)
        d_high = _time_per_room(hi, 0.85) - _time_per_room(lo, 0.85)
        assert d_low > 0 and d_high > 0
        assert d_low > 1.3 * d_high

    def test_scarcity_slows_low_tactics_players_more(self):
        lo = np.zeros(8)
        hi = np.zeros(8)
        lo[SCAR], hi[SCAR] = -1.0, 1.0
        d_low = _time_per_room(hi, 0.15) - _time_per_room(lo, 0.15)
        d_high = _time_per_room(hi, 0.85) - _time_per_room(lo, 0.85)
        assert d_low > 0 and d_high > 0
        assert d_low > 1.3 * d_high

    def test_healing_usable_fraction_grows_with_tactics(self):
        assert (
            tpd.HEAL_USE_BASE + tpd.HEAL_USE_GAIN * 1.0
            > tpd.HEAL_USE_BASE + tpd.HEAL_USE_GAIN * 0.0
        )
        assert tpd.HEAL_USE_BASE + tpd.HEAL_USE_GAIN * 1.0 <= 1.0

    def test_expected_pickups_mirror_generator_step(self):
        """Treasure rooms: 2 for scarcity <= 0.2, else 1 (DungeonGenerator.gd) -> supply cliff."""
        p = dict(tpd.INTERMEDIATE, hazard_density=0.35)
        gen = {
            s: DungeonDifficultyEnv.expected_pickups(dict(p, resource_scarcity=s))
            for s in (0.1, 0.2, 0.3, 0.9)
        }
        assert gen[0.2] - gen[0.3] > 2.0  # an extra treasure room (~3 pickups) minus the coin term
        assert gen[0.3] >= gen[0.9] >= 0.0
        # and it agrees with the sampled layout on average
        env = DungeonDifficultyEnv()
        env.reset(seed=0)
        sampled = []
        for s in range(400):
            env.rng = np.random.default_rng(s)
            sampled.append(
                env._room_layout(dict(p, resource_scarcity=0.5), 1.0)[2] / tpd.HEAL_PER_PICKUP
            )
        assert np.mean(sampled) == pytest.approx(
            DungeonDifficultyEnv.expected_pickups(dict(p, resource_scarcity=0.5)), abs=0.35
        )


class TestV3Priors:
    BASE = dict(time=45.0, deaths=0, dmg_ratio=0.35, rooms=6, skill=0.5)

    def _r(self, **kw):
        a = np.zeros(8)
        return DungeonDifficultyEnv.reward_fn(dict(self.BASE, **kw), a, a)[0]

    def test_priors_skipped_without_measures(self):
        """Hand-made result dicts without sev / cover (older tests, other callers) get no prior term."""
        assert self._r(reflex=0.2, tactics=0.8) == pytest.approx(self._r())

    def test_severity_band_target_rises_with_reflex(self):
        for reflex in (0.1, 0.9):
            target = tpd.SEV_LO + (tpd.SEV_HI - tpd.SEV_LO) * reflex
            at = self._r(reflex=reflex, sev=target)
            off = self._r(reflex=reflex, sev=target + 0.15)
            assert at - off == pytest.approx(tpd.SEV_W * 0.15 / 0.30)
        # the same severity is fine for an expert and penalised for a novice
        sev = 0.30
        assert self._r(reflex=0.9, sev=sev) > self._r(reflex=0.1, sev=sev)

    def test_cover_target_falls_with_tactics(self):
        cover = 1.5
        assert self._r(tactics=0.9, cover=cover) > self._r(tactics=0.1, cover=cover)
        cover = 2.5
        assert self._r(tactics=0.1, cover=cover) > self._r(tactics=0.9, cover=cover)

    def test_simulate_reports_measures(self):
        env = DungeonDifficultyEnv()
        env.reset(seed=1, options={"skill": 0.5})
        res = env._simulate(dict(tpd.INTERMEDIATE), archetype_mix(0.0))
        for k in ("reflex", "tactics", "sev", "cover"):
            assert k in res and np.isfinite(res[k])
        assert 0.0 < res["sev"] < 0.6


class TestShippedPolicyPersonalises:
    """Acceptance: the exported policy chooses different damage / scarcity for different players."""

    @staticmethod
    def _mean_actions(skill, floors=12, episodes=12):
        pol = _policy()
        acts = []
        for s in range(episodes):
            env = DungeonDifficultyEnv()
            obs, _ = env.reset(seed=700 + s, options={"skill": skill, "random_shifts": False})
            for _ in range(floors):
                a = pol(obs)
                obs, _, _, _, _ = env.step(a)
                acts.append(a)
        return (np.mean(acts, axis=0) + 1.0) / 2.0  # position in range

    def test_meta_is_sim_v3(self):
        d = json.load(open(WEIGHTS))
        assert d["meta"]["version"] == "sim-v3"
        assert d["meta"]["act_dim"] == 8 and d["meta"]["obs_dim"] == 8

    def test_v2_weights_kept(self):
        path = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights_v2.json")
        assert json.load(open(path))["meta"]["version"] == "sim-v2"

    def test_damage_and_scarcity_differ_between_low_and_high_skill(self):
        lo, hi = self._mean_actions(0.10), self._mean_actions(0.90)
        assert hi[DMG] - lo[DMG] >= 0.15, (lo[DMG], hi[DMG])
        assert hi[SCAR] - lo[SCAR] >= 0.15, (lo[SCAR], hi[SCAR])

    def test_mean_output_differs_for_low_and_high_skill_first_observation(self):
        """The policy's mean damage / scarcity output already differs on the very first
        observation (after the cold-start floors) of a low- and a high-skill player."""
        pol = _policy()
        outs = {}
        for skill in (0.10, 0.90):
            vs = []
            for s in range(30):
                env = DungeonDifficultyEnv()
                obs, _ = env.reset(seed=900 + s, options={"skill": skill})
                vs.append(pol(obs))
            outs[skill] = np.mean(vs, axis=0)
        assert outs[0.90][DMG] - outs[0.10][DMG] > 0.10
        assert outs[0.90][SCAR] - outs[0.10][SCAR] > 0.10
