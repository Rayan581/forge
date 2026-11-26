"""Tests for the connected pipeline (stages 2-7). Run: python -m pytest ml/tests -v"""

from __future__ import annotations

import json

import numpy as np
import pytest

from ml import config as CFG
from ml import judge_bridge as JB
from ml import layouts as L
from ml import sim_v2 as S
from ml.player_data import sim

PM = str(CFG.REPO_ROOT / "ml" / "artifacts" / "player_model_synthetic.pt")
JUDGE = str(CFG.REPO_ROOT / "ml_spike" / "judge" / "judge_model.txt")


@pytest.fixture(scope="module")
def env():
    return S.DungeonDifficultyEnvV2(PM, JUDGE, CFG.DEFAULTS["sim"])


# ---- config -----------------------------------------------------------------------------------
def test_config_overrides(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"ppo": {"seeds": [3]}}))
    cfg = CFG.load_config(p, ["ppo.total_timesteps=123", "sim.judge_w=0.5", "run_name=x"])
    assert cfg["ppo"]["seeds"] == [3]
    assert cfg["ppo"]["total_timesteps"] == 123
    assert cfg["sim"]["judge_w"] == 0.5
    assert cfg["ppo"]["n_envs"] == CFG.DEFAULTS["ppo"]["n_envs"]  # untouched default kept
    assert CFG.run_dir(cfg).name == "x"


# ---- Judge bridge -----------------------------------------------------------------------------
def test_judge_bridge_matches_judge_module():
    from ml_spike.judge import common as C

    assert JB.JUDGE_FEATURES == C.FEATURES
    assert (JB.W_DAMAGE, JB.W_DEATHS, JB.W_PACE) == (C.W_DAMAGE, C.W_DEATHS, C.W_PACE)
    assert JB.PACE_CAP == C.PACE_CAP
    import pandas as pd

    df = pd.DataFrame(dict(damage_taken=[30.0], deaths=[1], completion_time=[50.0], rooms_total=[6],
                           room_count=[6], player_max_hp=[100.0]))  # fmt: skip
    assert JB.measured_difficulty(50.0, 1, 0.30, 6) == pytest.approx(C.measured_difficulty(df)[0])


def test_judge_scorer_predicts_in_range(env):
    p, a7 = S.params_from_action(np.zeros(8))
    x = env.judge.features(p, sim.archetype_mix(a7), 1.0, None, complexity=(a7 + 1) / 2)
    assert x.shape == (18,) and np.isnan(x[-4:]).all()  # first floor: context is NaN
    d = env.judge.predict(x)[0]
    assert 0.0 <= d <= 1.0
    assert env.judge.ood_fraction(x) == 0.0
    far = x.copy()
    far[0] = 1e6
    assert env.judge.ood_fraction(far) > 0.0


# ---- new simulator ----------------------------------------------------------------------------
def test_env_contract_and_episode(env):
    obs, _ = env.reset(seed=1)
    assert obs.shape == (8,) and obs.dtype == np.float32
    assert env.observation_space.contains(obs)
    rows = S.run_episode(env, lambda o: np.zeros(8), 1)
    assert len(rows) == CFG.DEFAULTS["sim"]["max_levels"]
    r = rows[0]
    for k in ("judge", "measured", "target", "ood", "proxy", "pace_err"):
        assert np.isfinite(r[k])
    assert all(np.isfinite(x["reward"]) for x in rows)


def test_env_is_deterministic_for_a_seed(env):
    a = [r["reward"] for r in S.run_episode(env, lambda o: np.full(8, 0.2), 5)]
    b = [r["reward"] for r in S.run_episode(env, lambda o: np.full(8, 0.2), 5)]
    assert a == b


def test_sample_from_action_is_the_settings_path(env):
    """step() uses MLP1.sample_from_action; step_params() the explicit-settings path. Same draw."""
    env.reset(seed=3)
    a = np.array([0.3, -0.2, 0.1, 0.5, -0.4, 0.0, 0.25, 0.6])
    p, a7 = S.params_from_action(a)
    state = env.rng.bit_generator.state
    x1 = env.pm.sample_from_action(a, env.player.skill, env._hist_arr(), env.rng)
    env.rng.bit_generator.state = state
    x2 = env.sample_settings(p, sim.archetype_mix(a7), 1.0, env.player.skill, (a7 + 1) / 2)
    np.testing.assert_allclose(x1, x2, atol=1e-6)


def test_static_floor_outside_box_runs(env):
    env.reset(seed=0)
    for floor in (1, 25):
        p, a7 = S.static_schedule(floor)
        _obs, r, _d, _t, info = env.step_params(p, a7)
        assert np.isfinite(r)
    assert info["params"]["enemy_health"] > sim.PARAM_RANGES["enemy_health"][1]  # past the box


def test_scripted_shift_reaches_player(env):
    env.reset(seed=0, options={"skill": 0.7, "shifts": {3: -0.3}})
    skills = []
    for _ in range(6):
        skills.append(env.player.skill)
        env.step(np.zeros(8))
    assert skills[3] < skills[2] - 0.2  # shift key 3 = before the 4th floor (index 3)


def test_judge_term_in_reward(env):
    base = dict(time=45.0, deaths=0, dmg_ratio=0.35, rooms=6, c=0.5, skill=0.5, reflex=0.5,
                tactics=0.5, judge=0.27, target=0.27, ood=0.0, sev=0.2, cover=2.5)  # fmt: skip
    r0, _ = env.reward(base, np.zeros(8), None)
    r1, _ = env.reward(dict(base, judge=0.60), np.zeros(8), None)
    r2, _ = env.reward(dict(base, ood=0.5), np.zeros(8), None)
    assert r1 < r0 and r2 < r0


# ---- layouts ----------------------------------------------------------------------------------
def test_bsp_layouts_are_solvable_and_deterministic():
    counts = set()
    for seed in range(200):
        lay = L.bsp_layout(np.random.default_rng(seed), 5, 9)
        chk = L.solvable(lay)
        assert chk["ok"], (seed, chk)
        assert 5 <= len(lay.rooms) <= 9
        counts.add(len(lay.rooms))
        again = L.bsp_layout(np.random.default_rng(seed), 5, 9)
        assert sorted(again.rooms) == sorted(lay.rooms) and again.exit == lay.exit
    assert len(counts) >= 3  # the BSP produces varied room counts


def test_forge_port_matches_room_count_and_is_solvable():
    rng = np.random.default_rng(0)
    for n in range(3, 10):
        for _ in range(50):
            lay = L.random_walk_layout(n, rng)
            assert len(lay.rooms) == n and L.solvable(lay)["ok"]
            assert L.bfs_depths(lay.rooms, lay.start)[lay.exit] == max(
                L.bfs_depths(lay.rooms, lay.start).values()
            )


def test_layout_distance():
    lay = L.random_walk_layout(6, np.random.default_rng(1))
    assert L.pairwise_distance([lay, lay]) == 0.0
    rows, _ = L.variety_table(20, 0, [5, 9])
    assert set(rows) == {"forge_ppo", "static_8pct", "bsp"}
    assert all(r["solvable_pct"] == 100.0 for r in rows.values())


# ---- whole pipeline on synthetic data ---------------------------------------------------------
def test_pipeline_end_to_end_smoke(tmp_path):
    """Every stage 0-7 runs on SYNTHETIC data and hands its artifacts to the next."""
    from ml import pipeline as P

    sets = [
        f"runs_root={tmp_path.as_posix()}", "run_name=t", "data.telemetry=synthetic",
        "data.smoke_players=25", "player_model.members=1", "player_model.epochs=3",
        "judge.folds=2", "judge.shap_rows=100", "sim.sanity_episodes=1", "sim.max_levels=8",
        "ppo.seeds=[0]", "ppo.total_timesteps=256", "ppo.n_envs=1", "ppo.vec_env=dummy",
        'ppo.hyper={"n_steps": 128, "batch_size": 64, "n_epochs": 1}',
        "ppo.validation_episodes=1", "ppo.exploit_episodes=2",
        "policy_shap.background=10", "policy_shap.explain=10",
        "baselines.episodes=1", "baselines.profiles=[0.5]", "baselines.layouts_per_generator=10",
        "report.dpi=60",
    ]  # fmt: skip
    argv = ["all"] + sum((["--set", s] for s in sets), [])
    assert P.main(argv) == 0
    man = json.loads((tmp_path / "t" / "manifest.json").read_text())
    assert set(man["stages"]) == set(P.STAGES)
    assert man["stages"]["player"]["data_source"] == "synthetic"
    assert man["stages"]["judge"]["data_source"] == "synthetic"
    shap_res = json.loads((CFG.REPO_ROOT / man["stages"]["policy-shap"]["result"]).read_text())
    assert shap_res["additivity_max_err"] < 1e-6
    pol = json.loads((CFG.REPO_ROOT / man["stages"]["ppo"]["policy_json"]).read_text())
    assert pol["meta"]["version"] == S.SIM_VERSION and pol["meta"]["act_dim"] == 8
    md = (CFG.REPO_ROOT / man["stages"]["report"]["results_md"]).read_text()
    assert "SYNTHETIC" in md and "Exploit check" in md


def test_missing_stage_gives_clear_error(tmp_path):
    from ml import pipeline as P

    with pytest.raises(SystemExit, match="has not been run"):
        P.main(["sim", "--set", f"runs_root={tmp_path.as_posix()}", "--set", "run_name=empty"])
