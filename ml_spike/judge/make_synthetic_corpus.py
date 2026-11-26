"""Synthetic Judge corpus from the sim-v3 player simulator (SYNTHETIC DATA, not real players).

Every row is one simulated floor, written with the same column names as the telemetry view
``v_corpus`` plus ``source = "synthetic"`` and three simulator-only columns (``sim_skill``,
``sim_reflex``, ``sim_tactics``: the latent player state, never used as features). Columns the
simulator does not model (damage dealt, kills, frame times, ratings, ...) are left EMPTY rather
than invented, so ``perceived_difficulty`` is always NULL here and the trainer falls back to the
measured target.

Sessions: one simulated player per session (``install_id = session_id``). A player starts at
skill ~ U(0.05, 0.95) with a reflex/tactics bias and drifts / shifts abruptly between floors exactly
as in ``DungeonDifficultyEnv`` (sim-v3), so the previous-floor context carries real information.
Half the sessions start with the game's 5 calibration floors (as real sessions do); every other floor
is drawn from a mixture that covers the whole action space:

* 45 % uniform: all 8 actions ~ U[-1, 1]; enemy_count_scale = 1 (70 %) or U(0.7, 1.3)
* 25 % near a preset: a calibration level or the Intermediate preset, jittered by N(0, 0.15)
  in action space
* 20 % smooth walk: previous action + N(0, 0.15) (PPO-like floor-to-floor changes)
* 10 % static baseline: Intermediate x (1 + 0.08 (k - 1)) for k ~ U{1..20}, a7 = -0.1

Run (writes ml_spike/judge/data/synthetic_corpus.csv, gitignored; deterministic for a seed):
    python -m ml_spike.judge.make_synthetic_corpus --players 3000 --seed 0
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from ml_spike.analysis import export_telemetry as _et
from ml_spike.judge.common import DEFAULT_CORPUS
from ml_spike.train_ppo_difficulty import (
    ARCH_LEVELS,
    CAL_LEVELS,
    INTERMEDIATE,
    PARAM_ORDER,
    PLAYER_HP,
    STATIC_A7,
    STATIC_STEP,
    DungeonDifficultyEnv,
    archetype_mix,
    denorm,
    difficulty_score,
    to_action,
)

SIM_COLUMNS = ["sim_skill", "sim_reflex", "sim_tactics"]
FLOORS_PER_SESSION = (6, 14)  # inclusive range
P_GAME_LIKE = 0.5  # sessions that open with the 5 calibration floors
MIX_P = {"uniform": 0.45, "preset": 0.25, "walk": 0.20, "static": 0.10}
JITTER = 0.15
POLICY_VERSION = "sim-v3"


def v_corpus_columns() -> List[str]:
    """Column names of the v_corpus view, read from schema.sql (single source of truth)."""
    conn = sqlite3.connect(":memory:")
    try:
        _et.migrate(conn)
        return _et.corpus_header(conn)
    finally:
        conn.close()


def corpus_columns() -> List[str]:
    return v_corpus_columns() + ["source"] + SIM_COLUMNS


def _cal_params(cal: Dict) -> Dict[str, float]:
    return dict(
        enemy_health=float(cal["hp"]),
        enemy_damage=float(cal["dmg"]),
        enemy_speed=float(cal["spd"]),
        enemy_aggro=float(cal["agr"]),
        hazard_density=float(cal["haz"]),
        resource_scarcity=float(cal["scar"]),
        room_count=float(cal["rooms"]),
    )


def _params_from_action(a: np.ndarray) -> Dict[str, float]:
    p = {k: float(denorm(a[i], k)) for i, k in enumerate(PARAM_ORDER)}
    p["room_count"] = float(round(p["room_count"]))
    return p


def _sample_floor(rng: np.random.Generator, prev_action):
    """Returns (params, mix, complexity, count_scale, phase, action8 or None)."""
    kind = rng.choice(list(MIX_P), p=list(MIX_P.values()))
    if kind == "walk" and prev_action is None:
        kind = "uniform"
    cs = 1.0
    if kind == "uniform":
        a = rng.uniform(-1.0, 1.0, 8)
        if rng.random() >= 0.7:
            cs = float(rng.uniform(0.7, 1.3))
    elif kind == "walk":
        a = np.clip(prev_action + rng.normal(0.0, JITTER, 8), -1.0, 1.0)
    elif kind == "preset":
        idx = int(rng.integers(len(CAL_LEVELS) + 1))
        if idx < len(CAL_LEVELS):
            cal = CAL_LEVELS[idx]
            base7 = to_action(_cal_params(cal))
            a7 = 2.0 * float(np.asarray(cal["mix"]) @ ARCH_LEVELS) - 1.0
            cs = float(cal["cs"])
        else:
            base7 = to_action(dict(INTERMEDIATE))
            a7 = STATIC_A7
        a = np.clip(np.append(base7, a7) + rng.normal(0.0, JITTER, 8), -1.0, 1.0)
    else:  # static baseline floor k (health / damage grow past the PPO range, like the game)
        k = int(rng.integers(1, 21))
        f = 1.0 + STATIC_STEP * (k - 1)
        p = dict(INTERMEDIATE)
        p["enemy_health"] *= f
        p["enemy_damage"] *= f
        mix = archetype_mix(STATIC_A7)
        a = np.append(to_action(p), STATIC_A7)
        return p, mix, (STATIC_A7 + 1.0) / 2.0, 1.0, "static", a
    p = _params_from_action(a)
    mix = archetype_mix(a[7])
    return p, mix, (float(a[7]) + 1.0) / 2.0, cs, "adaptive", a


def _row(sid, floor_num, phase, p, mix, complexity, cs, action, res, rho, tau, skill) -> Dict:
    row = {
        "session_id": sid,
        "install_id": sid,
        "mode": "unknown",
        "policy_version": POLICY_VERSION,
        "game_version": "synthetic",
        "consent": 0,
        "floor_num": floor_num,
        "phase": phase,
        "completion_time": float(res["time"]),
        "deaths": int(res["deaths"]),
        "damage_taken": float(res["gross"]) * PLAYER_HP,  # gross damage, like the game logs it
        "player_max_hp": PLAYER_HP,
        "rooms_total": int(res["rooms"]),
        "room_count": int(round(p["room_count"])),
        "archetype_complexity": float(complexity),
        "enemy_count_scale": float(cs),
        "difficulty_score": float(difficulty_score(p)),
        "manual_override": 0,
        "generator": "forge",
        "source": "synthetic",
        "sim_skill": skill,
        "sim_reflex": rho,
        "sim_tactics": tau,
    }
    for k in PARAM_ORDER[:6]:
        row[k] = float(p[k])
    for i in range(5):
        row[f"archetype_mix_{i}"] = float(mix[i])
    if action is not None:
        for i in range(8):
            row[f"action_{i}"] = float(action[i])
    return row


def generate(n_players: int = 3000, seed: int = 0) -> pd.DataFrame:
    """Deterministic for (n_players, seed)."""
    rng = np.random.default_rng([seed, 2026])
    env = DungeonDifficultyEnv()
    rows: List[Dict] = []
    for i in range(n_players):
        env.reset(seed=int(seed) * 1_000_003 + i)
        sid = f"syn_{seed}_{i:05d}"
        n_floors = int(rng.integers(FLOORS_PER_SESSION[0], FLOORS_PER_SESSION[1] + 1))
        game_like = rng.random() < P_GAME_LIKE
        prev_action = None
        for f in range(1, n_floors + 1):
            if game_like and f <= len(CAL_LEVELS):
                cal = CAL_LEVELS[f - 1]
                p = _cal_params(cal)
                mix = np.asarray(cal["mix"], dtype=np.float64)
                complexity = float(mix @ ARCH_LEVELS)
                cs, phase, action = float(cal["cs"]), "calibration", None
            else:
                p, mix, complexity, cs, phase, action = _sample_floor(rng, prev_action)
                prev_action = action
            rho, tau = env._axes()
            skill = float(env.skill)
            res = env._simulate(p, mix, cs)
            rows.append(_row(sid, f, phase, p, mix, complexity, cs, action, res, rho, tau, skill))
            env.level += 1
            env._advance_skill()
    df = pd.DataFrame(rows)
    df["created_at"] = np.arange(len(df))
    return df.reindex(columns=corpus_columns())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the synthetic Judge corpus (sim-v3).")
    ap.add_argument("--players", type=int, default=3000, help="simulated players (= sessions)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(DEFAULT_CORPUS))
    args = ap.parse_args(argv)
    df = generate(args.players, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(
        f"wrote {len(df)} SYNTHETIC floor rows ({df['session_id'].nunique()} simulated players, "
        f"seed {args.seed}) to {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
