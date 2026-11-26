"""Tests for the player model (MLP1). Run from the repository root:

    python -m pytest ml/tests -v

All learning tests use SYNTHETIC data from the old simulator and tiny sizes, so they check that the
pipeline is correct (shapes, no leakage, save/load, monotone prior, residual can learn). They say
nothing about real players.
"""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from ml import player_data as D
from ml import player_eval as E
from ml import player_model as M

sim = D.sim


# ---- shared small synthetic dataset (module-scoped: generated once) ---------------------------
@pytest.fixture(scope="module")
def syn():
    return D.generate_synthetic(n_players=10, floors_per_player=15, seed=1)


@pytest.fixture(scope="module")
def tiny_model(syn):
    train, val, _ = D.split_dataset(syn, seed=0)
    model = M.PlayerModel.fit(train, val, n_members=2, epochs=15, hidden=16)
    return model, train, val


# ---- contracts --------------------------------------------------------------------------------
def test_action_to_y_matches_frozen_contract():
    y = D.action_to_y(np.zeros(8))  # all-zero action = midpoint of every range, c = 0.5
    assert y.shape == (8,)
    assert np.allclose(y[[0, 1, 2, 3, 4, 5]], 0.5, atol=1e-6)
    assert y[7] == pytest.approx(0.5)
    # round trip of the 7 parameters (rooms are rounded: 7.0 is the midpoint of 5..9)
    params = D.y_to_params(y)
    assert params[0] == pytest.approx(70.0) and params[6] == pytest.approx(7.0)


def test_make_x_clips_like_the_game():
    x = D.make_x(completion_time=500.0, deaths=7, damage_ratio=1.7)
    assert np.allclose(x, [1.0, 1.0, 1.0])
    assert np.allclose(D.make_x(45.0, 1, 0.35), [0.5, 1 / 3, 0.35])


def test_synthetic_dataset_is_well_formed(syn):
    assert syn.source == "synthetic"
    assert syn.x.shape == (len(syn), 3) and syn.hist.shape == (len(syn), D.HISTORY_LEN, 3)
    assert np.isfinite(syn.x).all() and np.isfinite(syn.y).all()
    assert (syn.x >= 0).all() and (syn.x <= 1).all()
    np.testing.assert_allclose(syn.mix.sum(axis=1), 1.0, atol=1e-6)
    # history of floor k is the outcome of floors k-2, k-1 within the same player
    p = syn.player == syn.player[0]
    xs, hs = syn.x[p], syn.hist[p]
    np.testing.assert_allclose(hs[2, 1], xs[1])
    np.testing.assert_allclose(hs[2, 0], xs[0])


# ---- splitting --------------------------------------------------------------------------------
def test_split_by_player_has_no_player_overlap(syn):
    train, val, kind = D.split_dataset(syn, seed=3)
    assert kind == "by_player"
    assert not set(train.player) & set(val.player)
    assert len(train) + len(val) == len(syn)


def test_split_fallbacks_are_labelled(syn):
    one_player = syn.subset(np.where(syn.player == syn.player[0])[0])
    one_player.session = np.where(np.arange(len(one_player)) < 8, "s1", "s2")
    _, val, kind = D.split_dataset(one_player)
    assert kind == "by_session_within_one_player" and len(val) > 0
    one_player.session[:] = "s1"
    train, val, kind = D.split_dataset(one_player)
    assert kind == "temporal_within_one_player"
    assert train.floor.max() < val.floor.min()  # validation = the LAST floors


# ---- telemetry loader -------------------------------------------------------------------------
def _fake_corpus():
    rows = []
    for install, n in (("A", 6), ("B", 5)):
        for k in range(n):
            rows.append(dict(
                session_id=f"sess_{install}", install_id=install, floor_num=k + 1, consent=1,
                completion_time=30.0 + 5 * k, deaths=k % 2, damage_taken=10.0 + k, player_max_hp=100.0,
                enemy_health=60.0, enemy_damage=20.0, enemy_speed=130.0, enemy_aggro=250.0,
                hazard_density=0.3, resource_scarcity=0.4, room_count=6, archetype_complexity=0.5,
                manual_override=1 if (install == "B" and k == 2) else 0,
            ))  # fmt: skip
    rows[1]["enemy_speed"] = np.nan  # a row with a missing setting must be dropped
    return pd.DataFrame(rows)


def test_loader_reads_csv_and_sqlite_and_filters(tmp_path):
    df = _fake_corpus()
    csv = tmp_path / "c.csv"
    df.to_csv(csv, index=False)
    db = tmp_path / "c.db"
    with sqlite3.connect(db) as con:
        df.to_sql("v_corpus", con, index=False)
    for path in (csv, db):
        ds = D.load_telemetry(str(path))
        assert ds.source == "real"
        assert len(ds) == 11 - 1 - 1  # one missing-setting row, one manual-override row
        assert set(ds.player) == {"A", "B"}
        assert ds.notes["skill_source"] == "ema_proxy"


def test_skill_estimate_never_uses_the_floor_it_predicts():
    xs = np.array([[0.2, 0, 0.1], [0.5, 0.33, 0.5], [0.9, 1.0, 0.9]], dtype=np.float32)
    est = D.ema_skill_estimates(xs)
    assert est[0] == D.SKILL_PRIOR
    xs2 = xs.copy()
    xs2[2] = [0.0, 0.0, 0.0]  # change the last outcome: the estimate FOR that floor must not move
    assert D.ema_skill_estimates(xs2)[2] == pytest.approx(est[2])


def test_loader_rejects_legacy_json(tmp_path):
    p = tmp_path / "session_telemetry.json"
    p.write_text("[]")
    with pytest.raises(ValueError, match="cannot be used"):
        D.load_telemetry(str(p))


# ---- base term --------------------------------------------------------------------------------
def test_base_term_is_deterministic_and_monotone():
    y = D.action_to_y(np.zeros(8))
    mix = sim.archetype_mix(0.0)
    a = M.analytic_base(y, 0.5, mix)
    assert np.array_equal(a, M.analytic_base(y, 0.5, mix))
    # same floor, better player -> not longer, not more damage
    strong = M.analytic_base(y, 0.9, mix)
    assert strong[0] <= a[0] and strong[2] <= a[2]
    # same player, harder floor (health, damage, speed, aggro up) -> not shorter, not less damage
    hard = y.copy()
    hard[:4] = np.clip(hard[:4] + 0.3, 0, 1)
    h = M.analytic_base(hard, 0.5, mix)
    assert h[0] >= a[0] and h[2] >= a[2]


# ---- model: distribution, bounds, save/load, sampling ----------------------------------------
def test_prediction_is_a_distribution_and_residual_is_bounded(tiny_model):
    model, _, val = tiny_model
    pred = model.predict_dataset(val)
    assert (pred["std"] > 0).all()
    # every member's mean is within RES_MAX of the analytic base
    assert np.abs(pred["member_mean"] - pred["base"][None]).max() <= M.RES_MAX + 1e-5


def test_save_load_roundtrip(tiny_model, tmp_path):
    model, _, val = tiny_model
    path = str(tmp_path / "m.pt")
    model.save(path)
    loaded = M.PlayerModel.load(path)
    assert loaded.data_source == "synthetic"
    np.testing.assert_allclose(loaded.predict_dataset(val)["mean"], model.predict_dataset(val)["mean"], atol=1e-6)


def test_sample_from_action_is_stochastic_valid_and_seedable(tiny_model):
    model, _, _ = tiny_model
    action = np.zeros(8)
    hist = [[0.4, 0.0, 0.3], [0.5, 0.0, 0.4]]
    a = model.sample_from_action(action, 0.5, hist, np.random.default_rng(7))
    b = model.sample_from_action(action, 0.5, hist, np.random.default_rng(7))
    np.testing.assert_array_equal(a, b)  # same rng seed -> same draw
    draws = np.stack([model.sample_from_action(action, 0.5, hist, np.random.default_rng(i)) for i in range(40)])
    assert draws.dtype == np.float32 and draws.shape == (40, 3)
    assert (draws >= 0).all() and (draws <= 1).all()
    assert draws[:, 0].std() > 0  # time is noisy, not a point prediction
    assert np.allclose(draws[:, 1] * 3, np.round(draws[:, 1] * 3))  # deaths are whole numbers
    # history may be empty or short
    model.sample_from_action(action, 0.5, None)
    model.sample_from_action(action, 0.5, [[0.4, 0.0, 0.3, 0, 0, 0, 0, 0.5]])  # full 8-D obs also accepted


def test_evaluation_reports_are_complete_and_labelled(tiny_model):
    model, train, val = tiny_model
    acc = E.evaluate_mae(model, val, train)
    assert set(acc["mae"]) == {"model", "base_only", "train_average"}
    assert set(acc["mae"]["model"]) == {"time", "deaths", "damage"}
    cal = E.evaluate_calibration(model, val, n_draws=5)
    for name in ("time", "deaths", "damage"):
        assert 0.0 <= cal["coverage"][name]["0.8"] <= 1.0
        assert sum(cal["pit_hist_10_bins"][name]) == pytest.approx(1.0, abs=0.02)
    mono = E.monotonicity_check(model, val, n_points=50)
    assert set(mono["higher_skill_violations"]) == {"time", "deaths", "damage"}


# ---- can the residual actually learn a correction? --------------------------------------------
def test_residual_learns_a_simulator_gap(monkeypatch):
    """Emulate a sim-to-real gap: generate data from a simulator whose enemy damage is 1.7x stronger
    than the analytic base assumes. The residual should beat the base term on damage."""
    with monkeypatch.context() as mp:
        mp.setattr(sim, "DMG_K", sim.DMG_K * 1.7)
        data = D.generate_synthetic(n_players=40, floors_per_player=20, seed=5)
    # base term is computed AFTER the patch is undone, i.e. with the original constants
    train, val, _ = D.split_dataset(data, seed=0)
    model = M.PlayerModel.fit(train, val, n_members=3, epochs=60)
    acc = E.evaluate_mae(model, val, train)["mae"]
    assert acc["model"]["damage"] < 0.85 * acc["base_only"]["damage"]
