"""Shared configuration for the FORGE ML pipeline (MLP1 -> Judge -> sim -> PPO -> SHAP -> baselines).

One JSON file holds every knob. ``ml/configs/default.json`` is the full run for real data;
``ml/configs/smoke.json`` is a tiny run that exercises every stage on SYNTHETIC data in a few minutes.
Values not given in the JSON file fall back to the defaults below, so a config file only needs the
keys it changes. Any value can also be overridden on the command line:

    python -m ml.pipeline all --config ml/configs/smoke.json --set ppo.total_timesteps=4096

Every stage writes into ``<run_dir>/<stage>/`` and records its outputs in ``<run_dir>/manifest.json``.
The next stage reads its inputs from that manifest, so the stages are already connected.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULTS: dict = {
    "run_name": "real",
    "runs_root": "ml/runs",
    "seed": 0,
    # ---- data -------------------------------------------------------------------------------
    "data": {
        # Telemetry export: the game's forge_telemetry.db (SQLite, v_corpus view) or the CSV from
        # ml_spike/analysis/export_telemetry.py. "auto" = the game's user:// DB if it exists.
        # "synthetic" = no real data (stage 0 writes a synthetic v_corpus CSV and uses that).
        "telemetry": "auto",
        "consented_only": True,
        # stage 0 (smoke data): how many simulated players to write as a v_corpus CSV
        "smoke_players": 60,
    },
    # ---- stage 1: MLP1 player model ---------------------------------------------------------
    "player_model": {
        "members": 5,
        "epochs": 200,
        # when the telemetry is missing / "synthetic": players simulated by the OLD simulator
        "synthetic_players": 150,
        "synthetic_floors": 30,
    },
    # ---- stage 2: Judge ----------------------------------------------------------------------
    "judge": {
        # what the Judge is trained on:
        #   auto      -> real telemetry if it has >= min_real_players players, else synthetic
        #   real      -> real telemetry only (fails if too few players)
        #   synthetic -> synthetic sim-v3 corpus; real telemetry is used only to validate
        #   mixed     -> synthetic corpus + real rows (real rows are always in the held-out check)
        #   mlp1_synth-> corpus SIMULATED by MLP1 trained on the recorded players (ml/judge_corpus.py):
        #                real players are split by install_id; MLP1 learns from one part, the
        #                other part is held out and is the Judge's only real-data check
        "train_on": "auto",
        "mlp1_players": 2000,  # simulated players in the MLP1 corpus
        "mlp1_holdout_frac": 0.34,  # share of real players held out (at least 1 on each side)
        "min_real_players": 7,
        "target": "auto",  # auto | measured | rating   (see ml_spike/judge/common.py)
        "synthetic_players": 3000,
        "test_frac": 0.2,
        "folds": 5,
        "shap_rows": 3000,
    },
    # ---- stage 3: new simulator (MLP1 outcomes + Judge difficulty) ----------------------------
    "sim": {
        "max_levels": 30,
        # Judge term of the reward: -judge_w * max(0, |D_judge - D_target| - judge_tol)
        "judge_w": 1.0,
        "judge_target": 0.27,  # measured difficulty of an on-pace, 0-death, 35 %-damage floor
        "judge_target_skill_slope": 0.0,  # D_target = judge_target + slope * (skill - 0.5)
        "judge_tol": 0.03,
        # "measured" = Judge output as is (target in measured-difficulty units); "rating" = Judge
        # output mapped onto the players' 1-5 ratings ((rating-1)/4) by a linear fit on the recorded
        # rated floors (stage 'sim' fits judge_rating_a/b), and judge_target is then a rating too
        # (3.5 stars -> 0.625). Pilot 2 (ml/configs/pilot2.json) uses "rating".
        "judge_scale": "measured",
        "judge_rating_a": 1.0,
        "judge_rating_b": 0.0,
        # the game scales the enemy count of PPO floors with their score (since 2026-11-27);
        # true = the simulator does the same (DifficultyManager.adaptive_count_scale)
        "adaptive_count_scale": False,
        # Penalty for settings outside the range the Judge / MLP1 were trained on (anti-exploit)
        "ood_w": 0.5,
        # Old-reward terms kept from sim-v3 (weights; 0 switches a term off)
        "pace_w": 1.0,
        "death_w": 0.5,
        "flow_dmg_w": 0.45,
        "room_w": 0.30,
        "complex_w": 0.20,
        "sev_w": 0.40,
        "cover_w": 0.80,
        "balance_w": 0.15,
        "smooth_w": 0.25,
        "sanity_episodes": 20,
    },
    # ---- stage 4: PPO retrain ----------------------------------------------------------------
    "ppo": {
        "seeds": [0, 1, 2],
        "total_timesteps": 1_000_000,
        "n_envs": 8,
        # "subproc" runs the 8 simulators in parallel processes (about 3-4x faster on a 4+ core CPU)
        "vec_env": "subproc",
        # extra PPO hyper-parameters passed to make_model (empty = the sim-v3 recipe)
        "hyper": {},
        # optional SB3 .zip to warm-start from (e.g. ml_spike/analysis/runs_v3/ppo_seed0.zip)
        "init_from": None,
        "validation_episodes": 100,
        "exploit_episodes": 60,
        # exploit check thresholds
        "exploit_gap_factor": 2.0,  # mean |judge - realised| must be <= factor * judge test MAE
        "exploit_gap_abs": 0.05,  # ... or <= judge test MAE + this
        "max_ood_rate": 0.10,
        "max_saturation_rate": 0.30,
        "max_old_sim_regression": 0.15,  # old-sim pacing error may grow at most this much
    },
    # ---- stage 5: policy SHAP ----------------------------------------------------------------
    "policy_shap": {"background": 100, "explain": 400},
    # ---- stage 6: BSP + baselines ------------------------------------------------------------
    "baselines": {
        # the PPO trained on the OLD simulator (sim-v3), exported for the game
        "old_policy": "godot_prototype/ai/policy_weights.json",
        "episodes": 60,
        "profiles": [0.10, 0.20, 0.45, 0.70, 0.90],
        "shift_floor": 10,
        "shift_delta": -0.30,
        "recover_thr": 0.15,  # recovered = pace error <= max(thr, pre-shift level + margin)
        "recover_margin": 0.05,
        "layouts_per_generator": 300,
        "bsp_min_rooms": 5,
        "bsp_max_rooms": 9,
    },
    # ---- stage 7: report ---------------------------------------------------------------------
    "report": {"dpi": 160},
}


def _deep_update(base: dict, upd: dict) -> dict:
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def _parse_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def load_config(path: str | os.PathLike | None = None, overrides: list[str] | None = None) -> dict:
    """DEFAULTS <- JSON file <- ``key.sub=value`` overrides (values parsed as JSON when possible)."""
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path, encoding="utf-8") as f:
            _deep_update(cfg, json.load(f))
        cfg["_config_file"] = str(path)
    for item in overrides or []:
        if "=" not in item:
            raise ValueError(f"--set expects key=value, got {item!r}")
        key, val = item.split("=", 1)
        node = cfg
        parts = key.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = _parse_value(val)
    return cfg


def resolve(path: str | os.PathLike | None) -> Path | None:
    """Repo-relative paths -> absolute (absolute paths are kept)."""
    if path in (None, ""):
        return None
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def run_dir(cfg: dict) -> Path:
    return resolve(cfg["runs_root"]) / cfg["run_name"]
