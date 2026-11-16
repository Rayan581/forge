"""Tests for the empirical Judge (ml_spike/judge): corpus, target, grouped split, model, SHAP, CLI.

Kept fast (tiny corpus, few trees). Data here is SYNTHETIC (sim-v3) or a hand-written fixture DB.
"""

import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from ml_spike.judge import common as C
from ml_spike.judge import explain, make_synthetic_corpus, train_judge
from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase


@pytest.fixture(scope="module")
def tiny_corpus():
    return make_synthetic_corpus.generate(n_players=80, seed=3)


@pytest.fixture(scope="module")
def tiny_model(tiny_corpus):
    df, _ = C.prepare(tiny_corpus)
    tr, te = C.grouped_holdout(df[C.group_column(df)].to_numpy(), 0.25, seed=0)
    X, y = C.feature_matrix(df), df["difficulty"].to_numpy(dtype=float)
    booster = train_judge.fit_lgb(X[tr], y[tr], seed=0, rounds=120)
    return booster, df, X, y, tr, te


def test_corpus_deterministic_for_seed():
    a = make_synthetic_corpus.generate(n_players=12, seed=7)
    b = make_synthetic_corpus.generate(n_players=12, seed=7)
    c = make_synthetic_corpus.generate(n_players=12, seed=8)
    pd.testing.assert_frame_equal(a, b)
    assert not a["completion_time"].equals(c["completion_time"])


def test_corpus_columns_match_v_corpus(tiny_corpus):
    v_cols = make_synthetic_corpus.v_corpus_columns()
    assert list(tiny_corpus.columns[: len(v_cols)]) == v_cols
    extra = list(tiny_corpus.columns[len(v_cols) :])
    assert extra == ["source"] + make_synthetic_corpus.SIM_COLUMNS
    assert set(tiny_corpus["source"]) == {"synthetic"}
    assert tiny_corpus["perceived_difficulty"].isna().all()  # never invented
    assert tiny_corpus[C.JUDGE_FEATURES].notna().all(axis=None)


def test_target_definition():
    df = pd.DataFrame(
        {
            "completion_time": [45.0, 1000.0, 10.0],
            "deaths": [0, 9, 0],
            "damage_taken": [0.0, 500.0, 50.0],
            "player_max_hp": [100.0, 100.0, None],
            "rooms_total": [6, 5, 0],
            "room_count": [6, 5, 4],
            "perceived_difficulty": [None, 5.0, 1.0],
        }
    )
    m = C.measured_difficulty(df)
    assert m[0] == pytest.approx(C.W_PACE * 0.5)  # on-target pace, no damage, no deaths
    assert m[1] == pytest.approx(1.0)  # every term saturated
    assert m[2] == pytest.approx(C.W_DAMAGE * 0.5 + C.W_PACE * (2.5 / C.PACE_CAP))
    target, kind = C.judge_target(df, "auto")
    assert list(kind) == ["measured", "rating", "rating"]
    assert target[1] == 1.0 and target[2] == 0.0


def test_player_context_from_previous_floor(tiny_corpus):
    df = C.add_player_context(tiny_corpus)
    first = df["floor_num"] == 1
    assert df.loc[first, C.CONTEXT_FEATURES].isna().all(axis=None)
    assert df.loc[~first, C.CONTEXT_FEATURES].notna().all(axis=None)
    s = df[df["session_id"] == df["session_id"].iloc[0]].sort_values("floor_num")
    assert s["prev_deaths"].iloc[1] == s["deaths"].iloc[0]


def test_grouped_split_has_no_session_overlap(tiny_corpus):
    groups = tiny_corpus["install_id"].to_numpy()
    tr, te = C.grouped_holdout(groups, 0.2, seed=1)
    assert set(groups[tr]).isdisjoint(groups[te]) and len(tr) + len(te) == len(groups)
    seen = []
    for ftr, fva in C.grouped_kfold(groups, 5, seed=1):
        assert set(groups[ftr]).isdisjoint(groups[fva])
        seen.extend(fva.tolist())
    assert sorted(seen) == list(range(len(groups)))


def test_tiny_model_beats_mean_predictor(tiny_model):
    booster, df, X, y, tr, te = tiny_model
    judge = C.regression_metrics(y[te], train_judge.predict(booster, X[te]))
    mean = C.regression_metrics(y[te], np.full(len(te), y[tr].mean()))
    assert judge["mae"] < mean["mae"]


def test_shap_additivity(tiny_model):
    booster, df, X, y, tr, te = tiny_model
    values, expected = explain.shap_values(booster, X[te][:50])
    raw = booster.predict(X[te][:50])
    np.testing.assert_allclose(values.sum(axis=1) + expected, raw, atol=1e-6)


def _fixture_db(path):
    db = TelemetryDatabase(db_path=path)
    db.upsert_session({"id": "sess_fx", "install_id": "fx", "started_at": 1, "consent": 1})
    for f in range(1, 4):
        db.upsert_floor_record(
            {
                "session_id": "sess_fx",
                "floor_num": f,
                "phase": "adaptive",
                "completion_time": 30.0 + 10 * f,
                "deaths": int(f == 3),
                "damage_taken": 20.0 * f,
                "player_max_hp": 100.0,
                "rooms_total": 6,
                "enemy_health": 40.0 + 10 * f,
                "enemy_damage": 12.0 + 4 * f,
                "enemy_speed": 120.0,
                "enemy_aggro": 250.0,
                "hazard_density": 0.3,
                "resource_scarcity": 0.4,
                "room_count": 6,
                "archetype_complexity": 0.4,
                "archetype_mix_0": 0.2,
                "archetype_mix_1": 0.3,
                "archetype_mix_2": 0.1,
                "archetype_mix_3": 0.2,
                "archetype_mix_4": 0.2,
                "enemy_count_scale": 1.0,
                "perceived_difficulty": 2.0 + f,
                "created_at": f,
            }
        )


def test_explain_cli_on_fixture_db(tiny_model, capsys):
    booster, df, *_ = tiny_model
    with tempfile.TemporaryDirectory() as tmp:
        dbp = os.path.join(tmp, "fx.db")
        _fixture_db(dbp)
        model = os.path.join(tmp, "m.txt")
        booster.save_model(model)
        rc = explain.main(
            ["--db", dbp, "--session", "sess_fx", "--model", model, "--meta", "missing.json"]
        )
    out = capsys.readouterr().out
    assert rc == 0
    for f in (1, 2, 3):
        assert f"Floor {f} (adaptive): predicted difficulty" in out
    assert "no previous floor" in out or "Floor 1" in out
    assert "player rating 5/5" in out
