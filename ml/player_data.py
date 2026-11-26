"""FORGE player model (MLP1): data handling.

This file turns raw floors into the arrays the player model trains on. It has four jobs:

1. ``FloorDataset``       - a tiny container (plain numpy arrays, no pandas needed downstream).
2. ``load_telemetry``     - build a dataset from the telemetry export (SQLite ``.db`` or the CSV
                            from ``ml_spike/analysis/export_telemetry.py``).
3. ``generate_synthetic`` - build the SAME kind of dataset from the OLD hand-written simulator
                            (``DungeonDifficultyEnv``). Everything trained on this is SYNTHETIC.
4. ``split_dataset``      - train / validation split by player, with an honest fallback when there is
                            only one player (which is the case for the real data we have today).

Contracts (frozen, copied from ml_spike/train_ppo_difficulty.py):
    observation x (we model the first 3 of the 8 entries):
        x[0] = norm_time   = clip(completion_time / 90 s, 0, 1)
        x[1] = norm_deaths = clip(deaths / 3, 0, 1)
        x[2] = norm_dmg    = clip(damage_taken / player_max_hp, 0, 1)
    action (8-D, each in [-1, 1]):
        [health, damage, speed, aggro, hazard, scarcity, room_count, archetype_complexity]

Inside the player model we describe a floor's difficulty configuration by ``y`` (8 numbers):
    y[0:7] = the 7 game parameters scaled to 0..1 with PARAM_RANGES   (norm_raw, i.e. NOT clipped)
    y[7]   = c = archetype complexity in 0..1  (c = (a7 + 1) / 2)
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass, field

import numpy as np

# The old simulator lives in ml_spike/ (no package __init__), so we put that folder on the path.
_ML_SPIKE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml_spike")
if _ML_SPIKE not in sys.path:
    sys.path.insert(0, _ML_SPIKE)

import train_ppo_difficulty as sim  # noqa: E402  (the existing training script, NOT modified)

PARAM_ORDER = list(sim.PARAM_ORDER)  # 7 game parameters, same order as the action
Y_DIM = 8  # 7 parameters + archetype complexity c
X_DIM = 3  # we predict norm_time, norm_deaths, norm_dmg
HISTORY_LEN = 2  # how many previous observations the model sees
TIME_NORM_S = sim.TARGET_TIME * 2.0  # 90 s, same as DungeonDifficultyEnv._get_obs
DEATH_NORM = 3.0
# Used as "previous observation" for the very first floor of a session (no history yet).
NEUTRAL_X = np.array([0.30, 0.0, 0.30], dtype=np.float32)
SKILL_PRIOR = 0.5  # skill estimate before we have seen any floor
EMA_ALPHA = 0.3  # smoothing of the skill estimate (same alpha as the game's profile EMA)


# --------------------------------------------------------------------------------------------
# Conversions between the three ways of writing a difficulty configuration
# --------------------------------------------------------------------------------------------
def params_to_y(params, c) -> np.ndarray:
    """7 raw game parameters (in PARAM_ORDER) + complexity c -> y (8,)."""
    y = np.empty(Y_DIM, dtype=np.float32)
    for i, key in enumerate(PARAM_ORDER):
        y[i] = sim.norm_raw(float(params[i]), key)
    y[7] = float(np.clip(c, 0.0, 1.0))
    return np.clip(y, -0.5, 1.5)  # calibration floors (3-4 rooms) fall slightly below 0


def y_to_params(y) -> np.ndarray:
    """Inverse of params_to_y for the 7 parameters (raw units)."""
    out = np.empty(len(PARAM_ORDER), dtype=np.float64)
    for i, key in enumerate(PARAM_ORDER):
        lo, hi = sim.PARAM_RANGES[key]
        out[i] = lo + float(y[i]) * (hi - lo)
    return out


def action_to_y(action) -> np.ndarray:
    """The 8-D PPO action in [-1, 1] -> y. Mirrors DungeonDifficultyEnv.step (rooms are rounded)."""
    a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
    params = [float(sim.denorm(a[i], key)) for i, key in enumerate(PARAM_ORDER)]
    params[6] = float(round(params[6]))
    return params_to_y(params, (a[7] + 1.0) / 2.0)


def make_x(completion_time, deaths, damage_ratio) -> np.ndarray:
    """Outcome numbers -> the first 3 observation entries (same clipping as the game)."""
    return np.array(
        [
            np.clip(completion_time / TIME_NORM_S, 0.0, 1.0),
            np.clip(deaths / DEATH_NORM, 0.0, 1.0),
            np.clip(damage_ratio, 0.0, 1.0),
        ],
        dtype=np.float32,
    )


def competence(x) -> float:
    """Crude 0..1 'how well did the player do' score from one observation.

    Same weights as the Judge's measured difficulty (0.40 damage, 0.35 deaths, 0.25 pace), flipped:
    1 = easy and clean, 0 = slow, dying, hurt. Rooms are not part of x, so pace is judged from
    norm_time alone (norm_time 0.5 = 45 s counts as the slowest pace).
    """
    return float(1.0 - (0.40 * x[2] + 0.35 * x[1] + 0.25 * min(x[0] * 2.0, 1.0)))


def ema_skill_estimates(xs: np.ndarray, alpha: float = EMA_ALPHA) -> np.ndarray:
    """Skill estimate BEFORE each floor of one session, from the floors played so far.

    est[0] = SKILL_PRIOR; est[k] = EMA of competence(x[0..k-1]). Never looks at x[k] itself, so
    there is no leakage of the floor we are trying to predict. This is a PROXY: the real skill is
    latent. It is what we have for real telemetry; the simulator passes its latent skill instead.
    """
    est = np.empty(len(xs), dtype=np.float32)
    cur = SKILL_PRIOR
    for k in range(len(xs)):
        est[k] = cur
        comp = competence(xs[k])
        cur = comp if k == 0 else (1 - alpha) * cur + alpha * comp
    return est


# --------------------------------------------------------------------------------------------
# Container
# --------------------------------------------------------------------------------------------
@dataclass
class FloorDataset:
    """One row per floor. ``source`` is 'real' or 'synthetic' and travels with the model."""

    y: np.ndarray  # (N, 8) difficulty configuration
    skill: np.ndarray  # (N,) skill estimate in 0..1
    hist: np.ndarray  # (N, HISTORY_LEN, 3) previous observations, most recent LAST
    x: np.ndarray  # (N, 3) target observation
    mix: np.ndarray  # (N, 5) archetype mix actually used on that floor
    count_scale: np.ndarray  # (N,) enemy count scale (1.0 on adaptive floors)
    player: np.ndarray  # (N,) player / install id (string)
    session: np.ndarray  # (N,) session id (string)
    floor: np.ndarray  # (N,) floor number within the session
    source: str = "synthetic"
    notes: dict = field(default_factory=dict)

    def __len__(self):
        return len(self.x)

    def subset(self, idx) -> "FloorDataset":
        idx = np.asarray(idx)
        return FloorDataset(
            y=self.y[idx], skill=self.skill[idx], hist=self.hist[idx], x=self.x[idx],
            mix=self.mix[idx], count_scale=self.count_scale[idx], player=self.player[idx],
            session=self.session[idx], floor=self.floor[idx], source=self.source,
            notes=dict(self.notes),
        )  # fmt: skip


def _history_for_session(xs: np.ndarray, first_prev=None) -> np.ndarray:
    """(T, 3) outcomes of one session -> (T, HISTORY_LEN, 3) previous outcomes (most recent last)."""
    T = len(xs)
    hist = np.empty((T, HISTORY_LEN, X_DIM), dtype=np.float32)
    # Before the first floor there is no history: use the cold-start summary if we have one
    # (the simulator does), otherwise a neutral constant.
    start = NEUTRAL_X if first_prev is None else np.asarray(first_prev, dtype=np.float32)
    for k in range(T):
        for j in range(HISTORY_LEN):  # j = 0 is the oldest slot, j = HISTORY_LEN-1 the newest
            idx = k - (HISTORY_LEN - j)  # index of the floor that many floors back
            hist[k, j] = xs[idx] if idx >= 0 else start
    return hist


# --------------------------------------------------------------------------------------------
# 1) Real telemetry
# --------------------------------------------------------------------------------------------
_SETTING_COLS = [
    "enemy_health", "enemy_damage", "enemy_speed", "enemy_aggro",
    "hazard_density", "resource_scarcity", "room_count", "archetype_complexity",
]  # fmt: skip
_MIX_COLS = [f"archetype_mix_{i}" for i in range(5)]


def _read_table(path: str):
    """Read the telemetry corpus (``v_corpus`` view of the SQLite DB, or an exported CSV)."""
    import pandas as pd

    ext = os.path.splitext(path)[1].lower()
    if ext in (".db", ".sqlite", ".sqlite3"):
        con = sqlite3.connect(path)
        try:
            return pd.read_sql_query("SELECT * FROM v_corpus ORDER BY session_id, floor_num", con)
        finally:
            con.close()
    if ext == ".csv":
        return pd.read_csv(path)
    raise ValueError(
        f"Unsupported telemetry file '{path}'. Use the SQLite DB (forge_telemetry.db) or the CSV "
        "from ml_spike/analysis/export_telemetry.py. The legacy session_telemetry.json has no "
        "per-floor difficulty settings, so it cannot be used for the player model."
    )


def load_telemetry(
    path: str,
    consented_only: bool = False,
    skill_column: str | None = None,
    max_rows: int | None = None,
) -> FloorDataset:
    """Telemetry export -> FloorDataset.

    * Rows with manual_override = 1 (developer tools changed the floor) are dropped.
    * Rows with any missing setting or outcome are dropped (counted in ``notes``).
    * Player id = install_id (one install = one player). Session id = session_id.
    * Skill: by default the EMA proxy from the player's previous floors (see ema_skill_estimates).
      ``skill_column`` can name a column that already holds a skill value (the synthetic Judge
      corpus has ``sim_skill``); that is only for testing the loader on synthetic corpora.
    * If the archetype_mix_* columns are present they are used for the base term, otherwise the mix
      is derived from archetype_complexity exactly as the game does.
    """
    df = _read_table(path)
    n_in = len(df)
    if max_rows:
        df = df.head(max_rows)
    if consented_only and "consent" in df:
        df = df[df["consent"] == 1]
    if "manual_override" in df:
        df = df[df["manual_override"].fillna(0).astype(int) == 0]
    need = _SETTING_COLS + ["completion_time", "deaths", "damage_taken"]
    missing_cols = [c for c in need if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Telemetry is missing columns: {missing_cols}")
    n_before = len(df)
    df = df.dropna(subset=need).copy()
    n_dropped_missing = n_before - len(df)
    if "player_max_hp" not in df:
        df["player_max_hp"] = sim.PLAYER_HP
    df["player_max_hp"] = df["player_max_hp"].fillna(sim.PLAYER_HP).where(lambda s: s > 0, sim.PLAYER_HP)
    if "install_id" not in df:
        df["install_id"] = df["session_id"]
    df = df.sort_values(["install_id", "session_id", "floor_num"]).reset_index(drop=True)
    if len(df) == 0:
        raise ValueError("No usable floors in the telemetry file.")

    ys, skills, hists, xs_all, mixes, scales, players, sessions, floors = ([] for _ in range(9))
    for (_player, sess), g in df.groupby(["install_id", "session_id"], sort=False):
        g = g.sort_values("floor_num")
        xs = np.stack(
            [
                make_x(r.completion_time, r.deaths, r.damage_taken / r.player_max_hp)
                for r in g.itertuples()
            ]
        )
        for r in g.itertuples():
            params = [getattr(r, k) for k in PARAM_ORDER]
            ys.append(params_to_y(params, r.archetype_complexity))
            if all(hasattr(r, m) and not np.isnan(getattr(r, m)) for m in _MIX_COLS):
                mixes.append([getattr(r, m) for m in _MIX_COLS])
            else:
                mixes.append(sim.archetype_mix(2.0 * r.archetype_complexity - 1.0))
            scale = getattr(r, "enemy_count_scale", 1.0)
            scales.append(1.0 if (scale is None or np.isnan(scale)) else float(scale))
        if skill_column is not None:
            skills.append(g[skill_column].to_numpy(dtype=np.float32))
        else:
            skills.append(ema_skill_estimates(xs))
        hists.append(_history_for_session(xs))
        xs_all.append(xs)
        players.extend([str(g["install_id"].iloc[0])] * len(g))
        sessions.extend([str(sess)] * len(g))
        floors.extend(g["floor_num"].astype(int).tolist())

    return FloorDataset(
        y=np.stack(ys).astype(np.float32),
        skill=np.concatenate(skills).astype(np.float32),
        hist=np.concatenate(hists),
        x=np.concatenate(xs_all),
        mix=np.asarray(mixes, dtype=np.float64),
        count_scale=np.asarray(scales, dtype=np.float64),
        player=np.asarray(players),
        session=np.asarray(sessions),
        floor=np.asarray(floors),
        source="real" if skill_column is None else "synthetic",
        notes=dict(
            path=os.path.basename(path), rows_in_file=int(n_in), dropped_missing=int(n_dropped_missing),
            skill_source=skill_column or "ema_proxy",
        ),
    )  # fmt: skip


# --------------------------------------------------------------------------------------------
# 2) Synthetic data from the OLD simulator
# --------------------------------------------------------------------------------------------
def generate_synthetic(n_players: int = 60, floors_per_player: int = 30, seed: int = 0) -> FloorDataset:
    """Play ``n_players`` simulated players through the OLD DungeonDifficultyEnv.

    Actions are a random walk in [-1, 1]^8 (with occasional fresh random jumps) so the whole
    configuration space is covered, not just what a trained PPO would pick. Each simulated player has
    its own latent skill, which we record (it is the 'skill' input; the future DungeonDifficultyEnvV2
    holds the same latent skill and passes it in).

    EVERYTHING produced here is SYNTHETIC: a model trained on it can at best reproduce the old
    simulator. It tests the pipeline; it says nothing about real players.
    """
    rng = np.random.default_rng(seed)
    env = sim.DungeonDifficultyEnv()
    ys, skills, hists, xs, mixes, scales, players, sessions, floors = ([] for _ in range(9))
    for p in range(n_players):
        obs, _ = env.reset(seed=int(seed * 100003 + p))
        prev_x = obs[:X_DIM].astype(np.float32)  # CR0-style summary of the cold start
        a = rng.uniform(-1, 1, sim.ACT_DIM)
        session_x = []
        for k in range(min(floors_per_player, sim.MAX_LEVELS)):
            a = rng.uniform(-1, 1, sim.ACT_DIM) if rng.random() < 0.15 else np.clip(a + rng.normal(0, 0.35, sim.ACT_DIM), -1, 1)
            skill_before = env.skill  # the skill used to play THIS floor (step() advances it)
            y = action_to_y(a)
            obs, _r, _done, _t, info = env.step(a.astype(np.float32))
            x = obs[:X_DIM].astype(np.float32)
            session_x.append(x)
            ys.append(y)
            skills.append(skill_before)
            mixes.append(np.asarray(info["mix"], dtype=np.float64))
            scales.append(1.0)
            players.append(f"syn_player_{p}")
            sessions.append(f"syn_session_{p}")
            floors.append(6 + k)
        session_x = np.stack(session_x)
        # history of floor k = the two floors before it (first floors use the cold-start summary)
        hists.append(_history_for_session(session_x, first_prev=prev_x))
        xs.append(session_x)
    return FloorDataset(
        y=np.stack(ys).astype(np.float32),
        skill=np.asarray(skills, dtype=np.float32),
        hist=np.concatenate(hists),
        x=np.concatenate(xs),
        mix=np.stack(mixes),
        count_scale=np.asarray(scales, dtype=np.float64),
        player=np.asarray(players),
        session=np.asarray(sessions),
        floor=np.asarray(floors),
        source="synthetic",
        notes=dict(generator="DungeonDifficultyEnv (sim-v3), random-walk actions", seed=seed),
    )  # fmt: skip


# --------------------------------------------------------------------------------------------
# 3) Splitting
# --------------------------------------------------------------------------------------------
def split_dataset(ds: FloorDataset, val_frac: float = 0.25, seed: int = 0):
    """Return (train, val, kind) where ``kind`` says what the split really tests.

    Preferred: split by PLAYER, so no player appears on both sides (no leakage).
    Fallbacks, used when there are too few players, and labelled in ``kind``:
      * one player, >= 2 sessions -> hold out whole SESSIONS ("by_session_within_one_player")
      * one player, one session   -> hold out the LAST floors ("temporal_within_one_player")
    The fallbacks measure memorisation-vs-generalisation inside ONE person; they cannot say anything
    about unseen players.
    """
    rng = np.random.default_rng(seed)
    players = np.unique(ds.player)
    if len(players) >= 2:
        n_val = max(1, int(round(val_frac * len(players))))
        val_players = rng.choice(players, size=n_val, replace=False)
        is_val = np.isin(ds.player, val_players)
        kind = "by_player"
    else:
        sessions = np.unique(ds.session)
        if len(sessions) >= 2:
            n_val = max(1, int(round(val_frac * len(sessions))))
            val_sessions = rng.choice(sessions, size=n_val, replace=False)
            is_val = np.isin(ds.session, val_sessions)
            kind = "by_session_within_one_player"
        else:
            order = np.argsort(ds.floor, kind="stable")
            n_val = max(1, int(round(val_frac * len(ds))))
            is_val = np.zeros(len(ds), dtype=bool)
            is_val[order[-n_val:]] = True
            kind = "temporal_within_one_player"
    return ds.subset(np.where(~is_val)[0]), ds.subset(np.where(is_val)[0]), kind
