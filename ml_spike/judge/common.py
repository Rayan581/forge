"""FORGE Judge model: shared definitions (target, features, data loading, grouped splits).

The Judge answers one question: "how hard will a floor with THESE settings be FOR THIS PLAYER?"
It is trained on a synthetic corpus produced by the sim-v3 player simulator and validated on real
telemetry rows. The real corpus goes through exactly the same code path (a different input file).

Target: one scalar difficulty in [0, 1]
---------------------------------------
* Primary (when the player rated the floor): ``perceived = (rating - 1) / 4``, rating = the 1-5
  post-floor prompt ``floors.perceived_difficulty`` (1 = very easy, 5 = very hard).
* Fallback (no rating; all synthetic rows): a MEASURED difficulty built from the floor's outcome::

      measured = 0.40 * min(damage_taken / player_max_hp, 1)
               + 0.35 * min(deaths, 3) / 3
               + 0.25 * min(time_per_room / (2 * TARGET_TPR), 1)

  ``time_per_room = completion_time / rooms`` (rooms = ``rooms_total``, else ``room_count``) and
  ``TARGET_TPR = 7.5 s`` is the pace the game and the PPO reward call "well matched".
  The three caps reuse the normalisations of the PPO observation (DifficultyManager.build_observation:
  damage ratio clipped to [0, 1], deaths / 3, time / (2 x target)), so a pace exactly on target
  contributes 0.125. Weights: damage is the most continuous challenge signal (0.40), deaths the
  strongest but rare and discrete (0.35), time the most confounded by play style and exploration
  (0.25). These constants were fixed before any model was trained and are NOT tuned on test data.

``--target auto`` (default) uses the rating where it exists and the measured value otherwise;
``--target measured`` / ``--target rating`` force one definition (FYP-2: retrain on ratings).

Features (18)
-------------
* The 14 ``JUDGE_FEATURES`` (settings the floor was generated with).
* Player context from the PREVIOUS floor of the same session (``floor_num - 1``):
  ``prev_time_per_room``, ``prev_deaths``, ``prev_damage_frac`` (damage / max HP) and
  ``prev_difficulty_score`` (the game's 0-100 proxy for the previous floor's settings, so the model can
  tell "slow on an easy floor" from "slow on a hard floor").
  First floor of a session (or the previous floor row is missing): all four are NaN. LightGBM routes
  missing values down a learned default branch; the synthetic corpus contains first floors, so that
  branch is trained.
"""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from ml_spike.telemetry_data.telemetry_db import JUDGE_FEATURES
from ml_spike.train_ppo_difficulty import TARGET_TPR, difficulty_score

REPO_ROOT = Path(__file__).resolve().parents[2]
JUDGE_DIR = Path(__file__).resolve().parent
DEFAULT_CORPUS = JUDGE_DIR / "data" / "synthetic_corpus.csv"
DEFAULT_MODEL = JUDGE_DIR / "judge_model.txt"
DEFAULT_META = JUDGE_DIR / "judge_model.json"
FIGURES_DIR = JUDGE_DIR / "figures"

# ---- target definition (fixed; see module docstring) -----------------------------------------
W_DAMAGE, W_DEATHS, W_PACE = 0.40, 0.35, 0.25
DAMAGE_CAP = 1.0  # fraction of player max HP
DEATH_CAP = 3.0
PACE_CAP = 2.0 * TARGET_TPR  # seconds per room
DEFAULT_MAX_HP = 100.0  # Player.max_health, used when player_max_hp is NULL

TARGET_DEFINITION = {
    "name": "difficulty",
    "range": [0.0, 1.0],
    "primary": "(perceived_difficulty - 1) / 4 when the 1-5 rating exists",
    "fallback": (
        f"{W_DAMAGE}*min(damage_taken/player_max_hp, {DAMAGE_CAP}) + "
        f"{W_DEATHS}*min(deaths, {DEATH_CAP:g})/{DEATH_CAP:g} + "
        f"{W_PACE}*min((completion_time/rooms)/{PACE_CAP:g}, 1)"
    ),
    "constants": {
        "W_DAMAGE": W_DAMAGE,
        "W_DEATHS": W_DEATHS,
        "W_PACE": W_PACE,
        "DAMAGE_CAP": DAMAGE_CAP,
        "DEATH_CAP": DEATH_CAP,
        "PACE_CAP_S_PER_ROOM": PACE_CAP,
    },
}

CONTEXT_FEATURES = [
    "prev_time_per_room",
    "prev_deaths",
    "prev_damage_frac",
    "prev_difficulty_score",
]
FEATURES: List[str] = list(JUDGE_FEATURES) + CONTEXT_FEATURES
# Raw outcomes modelled as an extra. damage_exchange_ratio is not included: the simulator does not
# model damage dealt, so it is NULL in the synthetic corpus.
RAW_TARGETS = ["completion_time", "deaths", "damage_taken"]

# Plain-English names for the Insight Report.
FEATURE_LABELS = {
    "enemy_health": "enemy health",
    "enemy_damage": "enemy damage",
    "enemy_speed": "enemy speed",
    "enemy_aggro": "enemy aggro range",
    "hazard_density": "hazard density",
    "resource_scarcity": "resource scarcity",
    "room_count": "the number of rooms",
    "archetype_complexity": "archetype complexity",
    "archetype_mix_0": "the share of melee crawlers",
    "archetype_mix_1": "the share of ranged pyromancers",
    "archetype_mix_2": "the share of heavy brutes",
    "archetype_mix_3": "the share of agile skirmishers",
    "archetype_mix_4": "the share of swarmers",
    "enemy_count_scale": "the enemy count scale",
    "prev_time_per_room": "the previous floor's pace (s/room)",
    "prev_deaths": "deaths on the previous floor",
    "prev_damage_frac": "damage taken on the previous floor",
    "prev_difficulty_score": "the previous floor's settings",
}


# ---- target ---------------------------------------------------------------------------------
def _rooms(df: pd.DataFrame) -> np.ndarray:
    rooms = pd.to_numeric(df.get("rooms_total"), errors="coerce")
    if rooms is None:
        rooms = pd.Series(np.nan, index=df.index)
    fallback = pd.to_numeric(df["room_count"], errors="coerce")
    rooms = rooms.where(rooms > 0, fallback)
    return np.maximum(rooms.to_numpy(dtype=float), 1.0)


def _max_hp(df: pd.DataFrame) -> np.ndarray:
    if "player_max_hp" not in df:
        return np.full(len(df), DEFAULT_MAX_HP)
    hp = pd.to_numeric(df["player_max_hp"], errors="coerce").fillna(DEFAULT_MAX_HP)
    return np.where(hp > 0, hp, DEFAULT_MAX_HP).astype(float)


def measured_difficulty(df: pd.DataFrame) -> np.ndarray:
    """Outcome-based difficulty in [0, 1] (fallback target; fixed constants)."""
    dmg = pd.to_numeric(df["damage_taken"], errors="coerce").to_numpy(dtype=float) / _max_hp(df)
    deaths = pd.to_numeric(df["deaths"], errors="coerce").to_numpy(dtype=float)
    tpr = pd.to_numeric(df["completion_time"], errors="coerce").to_numpy(dtype=float) / _rooms(df)
    out = (
        W_DAMAGE * np.clip(dmg / DAMAGE_CAP, 0.0, 1.0)
        + W_DEATHS * np.clip(deaths / DEATH_CAP, 0.0, 1.0)
        + W_PACE * np.clip(tpr / PACE_CAP, 0.0, 1.0)
    )
    return out


def rating_difficulty(rating) -> np.ndarray:
    """(rating - 1) / 4 for the 1-5 prompt; NaN where there is no rating."""
    r = pd.to_numeric(pd.Series(rating), errors="coerce").to_numpy(dtype=float)
    return np.clip((r - 1.0) / 4.0, 0.0, 1.0)


def judge_target(df: pd.DataFrame, mode: str = "auto") -> Tuple[np.ndarray, np.ndarray]:
    """Returns (target, kind) with kind in {"rating", "measured", "none"} per row."""
    measured = measured_difficulty(df)
    if "perceived_difficulty" in df:
        rated = rating_difficulty(df["perceived_difficulty"])
    else:
        rated = np.full(len(df), np.nan)
    has_rating = ~np.isnan(rated)
    if mode == "measured":
        return measured, np.where(np.isnan(measured), "none", "measured")
    if mode == "rating":
        return rated, np.where(has_rating, "rating", "none")
    if mode != "auto":
        raise ValueError(f"unknown target mode {mode!r}")
    target = np.where(has_rating, rated, measured)
    return target, np.where(has_rating, "rating", "measured")


def proxy_difficulty(df: pd.DataFrame) -> np.ndarray:
    """The old hand-weighted Judge: DifficultyManager.calculate_difficulty_score() / 100."""
    cols = [
        "enemy_health",
        "enemy_damage",
        "enemy_speed",
        "enemy_aggro",
        "hazard_density",
        "resource_scarcity",
    ]
    vals = df[cols].astype(float).to_dict("records")
    return np.array([difficulty_score(v) / 100.0 for v in vals], dtype=float)


# ---- features -------------------------------------------------------------------------------
def add_player_context(df: pd.DataFrame) -> pd.DataFrame:
    """Adds CONTEXT_FEATURES from the floor_num - 1 row of the same session (NaN if absent).

    Call this on ALL floor rows of a session before any filtering, so a floor's context still comes
    from its true predecessor even when that predecessor is later excluded from training."""
    out = df.copy()
    out["floor_num"] = pd.to_numeric(out["floor_num"], errors="coerce").astype(int)
    rooms = _rooms(out)
    prev = pd.DataFrame(
        {
            "session_id": out["session_id"].to_numpy(),
            "floor_num": out["floor_num"].to_numpy() + 1,  # this row is the PREVIOUS floor of +1
            "prev_time_per_room": pd.to_numeric(out["completion_time"], errors="coerce").to_numpy()
            / rooms,
            "prev_deaths": pd.to_numeric(out["deaths"], errors="coerce").to_numpy(dtype=float),
            "prev_damage_frac": pd.to_numeric(out["damage_taken"], errors="coerce").to_numpy()
            / _max_hp(out),
            "prev_difficulty_score": _safe_proxy_score(out),
        }
    )
    prev = prev.drop_duplicates(["session_id", "floor_num"], keep="last")
    out = out.drop(columns=[c for c in CONTEXT_FEATURES if c in out.columns])
    merged = out.merge(prev, on=["session_id", "floor_num"], how="left")
    merged.index = out.index
    return merged


def _safe_proxy_score(df: pd.DataFrame) -> np.ndarray:
    """difficulty_score per row, NaN where a setting is missing."""
    out = np.full(len(df), np.nan)
    cols = JUDGE_FEATURES[:6]
    ok = df[cols].notna().all(axis=1).to_numpy()
    if ok.any():
        out[ok] = proxy_difficulty(df.loc[ok]) * 100.0
    return out


def feature_matrix(df: pd.DataFrame) -> np.ndarray:
    return df[FEATURES].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)


# ---- loading --------------------------------------------------------------------------------
def read_v_corpus(db_path: str | Path, consented_only: bool = False) -> pd.DataFrame:
    """All rows of v_corpus from a game or synced telemetry DB, opened READ-ONLY."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        df = pd.read_sql_query("SELECT * FROM v_corpus ORDER BY session_id, floor_num", conn)
    finally:
        conn.close()
    if consented_only:
        df = df[pd.to_numeric(df["consent"], errors="coerce") == 1]
    return df.reset_index(drop=True)


def read_corpus(path: str | Path, consented_only: bool = False) -> pd.DataFrame:
    """A corpus from CSV (synthetic or exported real) or a telemetry .db (v_corpus)."""
    path = Path(path)
    if path.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
        df = read_v_corpus(path, consented_only)
    else:
        df = pd.read_csv(path)
        if consented_only and "consent" in df:
            df = df[pd.to_numeric(df["consent"], errors="coerce") == 1].reset_index(drop=True)
    if "source" not in df:
        df["source"] = "real"
    return df


def prepare(df: pd.DataFrame, target_mode: str = "auto") -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Context features + target; drops manual-override rows and rows with missing settings/target.

    Returns (rows usable for the Judge, counts)."""
    counts = {"rows_in": int(len(df))}
    df = add_player_context(df)
    if "manual_override" in df:
        mo = pd.to_numeric(df["manual_override"], errors="coerce").fillna(0).astype(int) == 1
    else:
        mo = pd.Series(False, index=df.index)
    counts["excluded_manual_override"] = int(mo.sum())
    df = df[~mo].copy()
    missing = df[JUDGE_FEATURES].isna().any(axis=1)
    counts["excluded_missing_settings"] = int(missing.sum())
    df = df[~missing].copy()
    target, kind = judge_target(df, target_mode)
    df["difficulty"] = target
    df["target_kind"] = kind
    df["measured_difficulty"] = measured_difficulty(df)
    df["proxy_difficulty"] = proxy_difficulty(df)
    no_target = np.isnan(df["difficulty"].to_numpy(dtype=float))
    counts["excluded_no_target"] = int(no_target.sum())
    df = df[~no_target].reset_index(drop=True)
    counts["rows_used"] = int(len(df))
    counts["rows_with_rating"] = int((df["target_kind"] == "rating").sum())
    counts["sessions"] = int(df["session_id"].nunique())
    counts["players"] = int(df[group_column(df)].nunique())
    return df, counts


def group_column(df: pd.DataFrame) -> str:
    """Split unit: the player (install_id) when known, else the session."""
    if "install_id" in df and df["install_id"].notna().all():
        return "install_id"
    return "session_id"


# ---- grouped splits (no player appears on both sides) -----------------------------------------
def grouped_holdout(
    groups: Sequence, test_frac: float = 0.2, seed: int = 0
) -> Tuple[np.ndarray, np.ndarray]:
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    n_test = max(1, int(round(test_frac * len(uniq))))
    test_groups = set(uniq[:n_test].tolist())
    is_test = np.array([g in test_groups for g in groups])
    return np.flatnonzero(~is_test), np.flatnonzero(is_test)


def grouped_kfold(
    groups: Sequence, k: int = 5, seed: int = 0
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    fold_of = {g: i % k for i, g in enumerate(uniq)}
    folds = np.array([fold_of[g] for g in groups])
    for i in range(k):
        yield np.flatnonzero(folds != i), np.flatnonzero(folds == i)


# ---- metrics / misc -------------------------------------------------------------------------
def regression_metrics(y: np.ndarray, pred: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    err = pred - y
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
    }


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    a = pd.Series(np.asarray(a, dtype=float))
    b = pd.Series(np.asarray(b, dtype=float))
    if len(a) < 3 or a.nunique() < 2 or b.nunique() < 2:
        return float("nan")
    return float(a.rank().corr(b.rank()))


def git_commit(repo: Path = REPO_ROOT) -> str:
    """HEAD commit; falls back to reading .git/HEAD when git is not on PATH."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=10
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    head = repo / ".git" / "HEAD"
    try:
        ref = head.read_text(encoding="utf-8").strip()
        if ref.startswith("ref: "):
            return (repo / ".git" / ref[5:]).read_text(encoding="utf-8").strip()
        return ref
    except OSError:
        return "unknown"


def feature_reference(df: pd.DataFrame) -> Dict[str, Dict[str, Optional[float]]]:
    """Quartiles per feature (used by the Insight Report to call a value high / low)."""
    ref = {}
    for f in FEATURES:
        col = pd.to_numeric(df[f], errors="coerce").dropna()
        if col.empty:
            ref[f] = {"q25": None, "q50": None, "q75": None}
        else:
            q = col.quantile([0.25, 0.5, 0.75]).to_list()
            ref[f] = {"q25": float(q[0]), "q50": float(q[1]), "q75": float(q[2])}
    return ref
