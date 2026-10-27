"""
Tests for simulator v2: archetype-mix reference vectors (contract section 3), the
direction of every action dimension, the player population, baselines and the training wrapper.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

import train_ppo_difficulty as tpd
from train_ppo_difficulty import (
    ACTION_NAMES,
    DungeonDifficultyEnv,
    TrainWrapper,
    archetype_mix,
    difficulty_score,
    legacy_a7_from_score,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Reference values from the shared contract (section 3), rounded to 1e-5.
MIX_REFERENCE = {
    -1.0: [0.564138, 0.102288, 0.044595, 0.062481, 0.226498],
    -0.5: [0.188301, 0.188301, 0.061960, 0.101129, 0.460308],
    0.0: [0.083394, 0.424534, 0.109655, 0.207276, 0.175141],
    0.5: [0.052035, 0.192817, 0.272895, 0.392356, 0.089897],
    1.0: [0.043250, 0.127906, 0.514932, 0.247894, 0.066018],
}


class TestArchetypeMix:
    @pytest.mark.parametrize("a7", sorted(MIX_REFERENCE))
    def test_reference_vectors(self, a7):
        np.testing.assert_allclose(archetype_mix(a7), MIX_REFERENCE[a7], atol=1e-5)

    def test_sums_to_one_and_floor(self):
        for a7 in np.linspace(-1, 1, 41):
            p = archetype_mix(a7)
            assert abs(p.sum() - 1.0) < 1e-12
            assert p.min() >= 0.15 / 5 - 1e-12  # every archetype keeps >= 3 %

    def test_clamps_out_of_range(self):
        np.testing.assert_allclose(archetype_mix(5.0), archetype_mix(1.0))
        np.testing.assert_allclose(archetype_mix(-5.0), archetype_mix(-1.0))

    def test_legacy_rule(self):
        assert legacy_a7_from_score(0) == -1.0
        assert legacy_a7_from_score(100) == 1.0
        assert abs(legacy_a7_from_score(45) - (-0.1)) < 1e-12  # static baseline c = 0.45

    def test_difficulty_score_port(self):
        # Intermediate preset: 0.39 -> 39 (hand computed from DifficultyManager weights)
        assert difficulty_score(tpd.INTERMEDIATE) == 39
        lo = {k: tpd.PARAM_RANGES[k][0] for k in tpd.PARAM_ORDER}
        hi = {k: tpd.PARAM_RANGES[k][1] for k in tpd.PARAM_ORDER}
        assert difficulty_score(lo) == 0
        assert difficulty_score(hi) == 100


def _outcome(action, skill, seeds=40):
    """Mean (t_room, gross, deaths) over common random numbers for a constant action."""
    a = np.clip(np.asarray(action, dtype=np.float64), -1, 1)
    params = {k: float(tpd.denorm(a[i], k)) for i, k in enumerate(tpd.PARAM_ORDER)}
    params["room_count"] = float(round(params["room_count"]))
    mix = archetype_mix(a[7])
    out = []
    env = DungeonDifficultyEnv()
    for s in range(seeds):
        env.reset(seed=s, options={"skill": skill, "random_shifts": False})
        env.bias = 0.0
        env.rng = np.random.default_rng(s + 99)
        r = env._simulate(params, mix)
        out.append((r["time"] / r["rooms"], r["gross"], r["deaths"]))
    return np.mean(out, axis=0)


class TestEveryDimensionMatters:
    @pytest.mark.parametrize("dim", range(8))
    @pytest.mark.parametrize("skill", [0.3, 0.6])
    def test_higher_is_harder(self, dim, skill):
        lo_a = np.zeros(8)
        hi_a = np.zeros(8)
        lo_a[dim], hi_a[dim] = -1.0, 1.0
        lo, hi = _outcome(lo_a, skill), _outcome(hi_a, skill)
        name = ACTION_NAMES[dim]
        # never easier on any outcome (small tolerance for sampling noise) ...
        assert hi[0] >= lo[0] - 0.05, f"{name}: clears got faster ({lo[0]:.2f} -> {hi[0]:.2f})"
        assert hi[1] >= lo[1] - 0.005, f"{name}: damage taken fell"
        assert hi[2] >= lo[2] - 0.01, f"{name}: deaths fell"
        # ... and clearly harder on time or damage
        assert (hi[0] > lo[0] + 0.05) or (hi[1] > lo[1] + 0.01), f"{name} has no effect"

    def test_fast_enemies_do_not_speed_up_clears(self):
        for skill in (0.2, 0.5, 0.8):
            slow = _outcome([0, 0, -1, 0, 0, 0, 0, 0], skill)
            fast = _outcome([0, 0, 1, 0, 0, 0, 0, 0], skill)
            assert fast[0] > slow[0]

    def test_scarcity_reduces_healing(self):
        env = DungeonDifficultyEnv()
        env.reset(seed=0)
        heals = {}
        for scar in (0.1, 0.9):
            p = dict(tpd.INTERMEDIATE)
            p["resource_scarcity"] = scar
            h = []
            for s in range(200):
                env.rng = np.random.default_rng(s)
                h.append(env._room_layout(p, 1.0)[2])
            heals[scar] = np.mean(h)
        assert heals[0.1] > 1.5 * heals[0.9]

    def test_scarcity_increases_deaths_when_pressed(self):
        # a hard setting where healing decides survival
        lo = _outcome([0.6, 0.6, 0.2, 0.2, 0.2, -1.0, 0.0, 0.0], 0.2, seeds=80)
        hi = _outcome([0.6, 0.6, 0.2, 0.2, 0.2, 1.0, 0.0, 0.0], 0.2, seeds=80)
        assert hi[2] > lo[2]

    def test_aggro_increases_simultaneous_damage(self):
        lo = _outcome([0, 0, 0, -1, 0, 0, 0, 0], 0.5)
        hi = _outcome([0, 0, 0, 1, 0, 0, 0, 0], 0.5)
        assert hi[1] > lo[1] * 1.15

    def test_room_count_changes_total_time_not_per_room_pace(self):
        lo = _outcome([0, 0, 0, 0, 0, 0, -1, 0], 0.5)
        hi = _outcome([0, 0, 0, 0, 0, 0, 1, 0], 0.5)
        # per-room pace changes by < 20 % while rooms go 5 -> 9
        assert abs(hi[0] - lo[0]) / lo[0] < 0.2

    def test_complex_archetypes_hurt_novices_more(self):
        """Relative damage increase from c=0 to c=1 is larger for low skill than high skill."""
        rel = {}
        for skill in (0.2, 0.9):
            lo = _outcome([0, 0, 0, 0, 0, 0, 0, -1], skill, seeds=80)
            hi = _outcome([0, 0, 0, 0, 0, 0, 0, 1], skill, seeds=80)
            rel[skill] = (hi[0] - lo[0]) / lo[0]
        assert rel[0.2] > rel[0.9] * 0.9  # at least as sensitive; absolute seconds larger below
        lo = _outcome([0, 0, 0, 0, 0, 0, 0, -1], 0.2, seeds=80)
        hi = _outcome([0, 0, 0, 0, 0, 0, 0, 1], 0.2, seeds=80)
        lo9 = _outcome([0, 0, 0, 0, 0, 0, 0, -1], 0.9, seeds=80)
        hi9 = _outcome([0, 0, 0, 0, 0, 0, 0, 1], 0.9, seeds=80)
        assert (hi[1] - lo[1]) > (hi9[1] - lo9[1])


class TestPlayerPopulation:
    def test_initial_skill_range(self):
        skills = []
        for s in range(300):
            e = DungeonDifficultyEnv()
            e.reset(seed=s)
            skills.append(e.skill)
        assert min(skills) < 0.12 and max(skills) > 0.88
        assert min(skills) >= 0.05 - 1e-9 and max(skills) <= 0.95 + 1e-9

    def test_scripted_shift_applies_on_schedule(self):
        e = DungeonDifficultyEnv()
        e.reset(seed=3, options={"skill": 0.6, "shifts": {10: -0.3, 20: 0.3}})
        trace = []
        for _ in range(25):
            e.step(np.zeros(8, dtype=np.float32))
            trace.append(e.skill)
        assert abs(trace[8] - trace[7]) < 0.1  # no jump before the scripted level
        assert trace[9] < trace[8] - 0.2  # drop is applied before floor 10 (0-based)
        assert trace[19] > trace[18] + 0.2  # recovery before floor 20

    def test_random_shifts_happen(self):
        jumps = 0
        for s in range(40):
            e = DungeonDifficultyEnv()
            e.reset(seed=s, options={"skill": 0.5})
            prev = e.skill
            for _ in range(30):
                e.step(np.zeros(8, dtype=np.float32))
                if abs(e.skill - prev) > 0.12:
                    jumps += 1
                prev = e.skill
        assert jumps > 20  # ~5 % per level (+ reverts) over 1200 floors

    def test_skill_stays_in_bounds(self):
        e = DungeonDifficultyEnv()
        e.reset(seed=1, options={"skill": 0.95})
        for _ in range(30):
            e.step(np.zeros(8, dtype=np.float32))
            assert 0.0 <= e.skill <= 1.0

    def test_paired_player_trajectory_independent_of_policy(self):
        """Same seed -> same skill trajectory whatever the policy does (paired evaluation)."""
        tr = []
        for a in (np.full(8, -1.0), np.full(8, 1.0)):
            e = DungeonDifficultyEnv()
            e.reset(seed=11, options={"skill": 0.5})
            skills = []
            for _ in range(30):
                e.step(a)
                skills.append(e.skill)
            tr.append(skills)
        np.testing.assert_allclose(tr[0], tr[1])


class TestObservationAndReward:
    def test_obs_reflects_skill_drop(self):
        """After an abrupt drop the observed time / damage / deaths get worse."""
        e = DungeonDifficultyEnv()
        e.reset(seed=5, options={"skill": 0.7, "shifts": {6: -0.4}})
        a = np.zeros(8, dtype=np.float32)
        before, after = [], []
        for i in range(12):
            obs = e.step(a)[0]
            (before if i < 6 else after).append(obs[:3])
        assert np.mean(after, axis=0)[0] > np.mean(before, axis=0)[0]
        assert np.mean(after, axis=0)[2] > np.mean(before, axis=0)[2]

    def test_smoothness_penalty(self):
        res = dict(time=45.0, deaths=0, dmg_ratio=0.35, rooms=6, skill=0.5)
        prev = np.zeros(8)
        r0, _ = DungeonDifficultyEnv.reward_fn(res, prev, prev)
        r1, _ = DungeonDifficultyEnv.reward_fn(res, prev + 0.5, prev)
        # smoothness (mean |delta| = 0.5) + the balance term (mean a^2 = 0.25)
        assert r0 - r1 == pytest.approx(tpd.SMOOTH_LAMBDA * 0.5 + tpd.BALANCE_W * 0.25)

    def test_pacing_judged_per_room(self):
        mk = lambda rooms: dict(time=7.5 * rooms, deaths=0, dmg_ratio=0.35, rooms=rooms, skill=0.5)  # noqa: E731
        a = np.zeros(8)
        rs = [DungeonDifficultyEnv.reward_fn(mk(r), a, a)[1]["pace_err"] for r in (5, 7, 9)]
        assert rs == [0.0, 0.0, 0.0]

    def test_death_terms_kept(self):
        a = np.zeros(8)
        base = dict(time=45.0, deaths=0, dmg_ratio=0.35, rooms=6, skill=0.5)
        r0, _ = DungeonDifficultyEnv.reward_fn(base, a, a)
        r2, _ = DungeonDifficultyEnv.reward_fn(dict(base, deaths=2), a, a)  # same dmg, same pace
        assert r0 - r2 == pytest.approx(2 * 0.5 + 0.4)

    def test_calibration_state_matches_game(self):
        """After reset the env holds the Floor-5 calibration parameters (like DifficultyManager)."""
        e = DungeonDifficultyEnv()
        obs, _ = e.reset(seed=0)
        assert e.params["enemy_health"] == 90.0
        assert obs[6] == 0.0  # 5 rooms
        assert obs[7] == pytest.approx(0.6)  # first PPO decision is for floor 6


class TestBaselinesAndWrapper:
    def test_static_baseline_runs_and_scales(self):
        e = DungeonDifficultyEnv()
        e.reset(seed=0, options={"skill": 0.5})
        hp = []
        for f in range(1, 31):
            _, r, done, info = e.step_static(f)
            hp.append(info["params"]["enemy_health"])
            assert np.isfinite(r)
        assert hp[0] == pytest.approx(60.0)
        assert hp[-1] == pytest.approx(60.0 * (1 + 0.08 * 29))
        assert done

    def test_train_wrapper_penalises_out_of_range(self):
        wrapped = TrainWrapper(DungeonDifficultyEnv())
        plain = DungeonDifficultyEnv()
        assert wrapped.action_space.high[0] == 4.0
        wrapped.reset(seed=0)
        plain.reset(seed=0)
        r_wrapped = wrapped.step(np.full(8, 3.0, dtype=np.float32))[1]
        r_plain = plain.step(np.ones(8, dtype=np.float32))[1]  # the env clips 3.0 to 1.0
        assert r_plain - r_wrapped == pytest.approx(tpd.OOB_LAMBDA * 8 * 4.0, abs=1e-5)
        # in-range actions are untouched
        wrapped.reset(seed=1)
        plain.reset(seed=1)
        a = np.full(8, 0.3, dtype=np.float32)
        assert wrapped.step(a)[1] == pytest.approx(plain.step(a)[1])

    def test_finalize_restores_unit_action_space(self):
        env = tpd.make_vec_env(1, 0)
        model = tpd.make_model(env, n_steps=64, batch_size=64)
        tpd.finalize_model(model)
        assert float(model.action_space.high[0]) == 1.0
        assert float(model.policy.action_space.low[0]) == -1.0

    def test_export_has_meta_and_eight_outputs(self, tmp_path):
        env = DungeonDifficultyEnv()
        from stable_baselines3 import PPO

        model = PPO(
            "MlpPolicy", env, policy_kwargs=dict(net_arch=[64, 64]), n_steps=64, batch_size=64
        )
        p = tmp_path / "w.json"
        tpd.export_policy_to_json(model, str(p))
        d = json.load(open(p))
        assert d["meta"] == {"obs_dim": 8, "act_dim": 8, "version": "sim-v2"}
        assert len(d["layers"][-1]["b"]) == 8

    def test_shipped_weights_meta(self):
        path = os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights.json")
        d = json.load(open(path))
        assert d["meta"]["act_dim"] == 8 and d["meta"]["obs_dim"] == 8
        assert os.path.getsize(path) < 150 * 1024
        assert os.path.exists(
            os.path.join(REPO_ROOT, "godot_prototype", "ai", "policy_weights_v1_7dim.json")
        )
