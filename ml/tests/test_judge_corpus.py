"""Tests for the MLP1-generated Judge corpus (ml/judge_corpus.py). Run: python -m pytest ml/tests -v"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ml import config as CFG
from ml import judge_corpus as JC
from ml import player_data as D
from ml.player_model import PlayerModel

PM = str(CFG.REPO_ROOT / "ml" / "artifacts" / "player_model_synthetic.pt")


@pytest.fixture(scope="module")
def pm():
    return PlayerModel.load(PM)


@pytest.fixture(scope="module")
def corpus(pm):
    return JC.generate(pm, 12, seed=3)


def test_corpus_has_v_corpus_format_and_is_labelled(corpus):
    from ml_spike.judge import make_synthetic_corpus as M

    assert list(corpus.columns) == M.corpus_columns()
    assert (corpus["source"] == JC.SOURCE).all()
    assert (corpus["game_version"] == JC.SOURCE).all()
    assert corpus["perceived_difficulty"].isna().all()  # MLP1 does not invent ratings
    assert (corpus["install_id"] == corpus["session_id"]).all()  # one simulated player per session
    assert corpus["session_id"].nunique() == 12
    assert (corpus["generator"] == "forge").all()


def test_outcomes_stay_in_mlp1_range(corpus):
    assert corpus["completion_time"].between(0.0, D.TIME_NORM_S).all()
    assert corpus["deaths"].isin(range(0, int(D.DEATH_NORM) + 1)).all()
    frac = corpus["damage_taken"] / corpus["player_max_hp"]
    assert frac.between(0.0, 1.0).all()
    assert corpus["rooms_total"].equals(corpus["room_count"])
    assert set(corpus["phase"]) <= {"calibration", "adaptive", "static"}


def test_corpus_is_deterministic_and_seed_dependent(pm, corpus):
    again = JC.generate(pm, 12, seed=3)
    pd.testing.assert_frame_equal(corpus, again)
    other = JC.generate(pm, 12, seed=4)
    assert not np.allclose(other["completion_time"].head(20), corpus["completion_time"].head(20))


def test_outcome_draw_matches_the_simulator(pm):
    """The corpus and sim-v4 draw outcomes through the same function, so equal inputs give equal x."""
    from ml import sim_v2 as S
    from ml.player_data import sim
    from ml_spike.judge import make_synthetic_corpus as M

    p = M._cal_params(sim.CAL_LEVELS[2])
    y = D.params_to_y([p[k] for k in sim.PARAM_ORDER], 0.4)
    mix = sim.archetype_mix(-0.2)
    a = S.sample_outcome(pm, y, mix, 1.0, 0.5, None, np.random.default_rng(9))
    b = S.sample_outcome(pm, y, mix, 1.0, 0.5, None, np.random.default_rng(9))
    assert a.shape == (3,) and np.array_equal(a, b)


def _players(n):
    rows = []
    for p in range(n):
        for s in range(2):
            rows.append(dict(install_id=f"p{p}", session_id=f"p{p}_s{s}", floor_num=1))
    return pd.DataFrame(rows)


def test_split_is_grouped_by_player_and_deterministic():
    df = _players(5)
    tr, held = JC.split_real_players(df, 0.34, seed=1)
    assert set(tr).isdisjoint(held)
    assert set(tr) | set(held) == {f"p{i}" for i in range(5)}
    assert len(held) == 2 and len(tr) == 3
    assert JC.split_real_players(df, 0.34, seed=1) == (tr, held)
    tr2, held2 = JC.split_real_players(_players(2), 0.9, seed=0)
    assert len(tr2) == 1 and len(held2) == 1  # always at least one player on each side


def test_split_needs_two_players():
    with pytest.raises(ValueError, match="at least 2"):
        JC.split_real_players(_players(1), 0.34, seed=0)


def test_pipeline_judge_on_mlp1_corpus_holds_players_out(tmp_path):
    """smoke-data -> judge (train_on=mlp1_synth): held-out players never reach MLP1 or the Judge."""
    from ml import pipeline as P

    sets = [
        f"runs_root={tmp_path.as_posix()}", "run_name=m", "data.telemetry=synthetic",
        "data.smoke_players=6", "player_model.members=1", "player_model.epochs=3",
        "judge.train_on=mlp1_synth", "judge.mlp1_players=40", "judge.folds=2",
        "judge.shap_rows=80",
    ]  # fmt: skip
    for stage in ("smoke-data", "judge"):
        assert P.main([stage] + sum((["--set", s] for s in sets), [])) == 0
    man = json.loads((tmp_path / "m" / "manifest.json").read_text())
    j = man["stages"]["judge"]
    assert j["train_on"] == "mlp1_synth" and j["data_source"] == "synthetic"
    assert j["corpus_kind"] == "mlp1"
    assert j["mlp1_train_players"] + j["mlp1_heldout_players"] == 6
    meta = json.loads((CFG.REPO_ROOT / j["meta"]).read_text())
    info = meta["pipeline"]["mlp1_corpus"]
    assert set(info["train_players"]).isdisjoint(info["heldout_players"])
    assert meta["training_corpus"]["synthetic"] is True
    assert meta["training_corpus"]["sources"] == [JC.SOURCE]
    # MLP1 saw only the training players; the Judge was checked only on the held-out ones
    train = pd.read_csv(CFG.REPO_ROOT / info["train_csv"])
    held = pd.read_csv(CFG.REPO_ROOT / info["heldout_csv"])
    assert set(train["install_id"].astype(str)) == set(info["train_players"])
    assert set(held["install_id"].astype(str)) == set(info["heldout_players"])
    real = meta["real_eval"]
    assert real["sources"][0]["file"] == "real_heldout_players.csv"


def test_pipeline_mlp1_needs_two_players(tmp_path):
    from ml import pipeline as P

    sets = [f"runs_root={tmp_path.as_posix()}", "run_name=one", "data.telemetry=synthetic",
            "data.smoke_players=1", "judge.train_on=mlp1_synth"]  # fmt: skip
    assert P.main(["smoke-data"] + sum((["--set", s] for s in sets), [])) == 0
    with pytest.raises(SystemExit, match="at least 2"):
        P.main(["judge"] + sum((["--set", s] for s in sets), []))
