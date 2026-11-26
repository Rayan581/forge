"""Judge corpus generated from the RECORDED players: MLP1 trained on real telemetry simulates players.

The Judge needs many players; the game has a handful. The old fallback (``judge.train_on =
"synthetic"``) trains the Judge on players from the hand-written sim-v3 physics. This module
replaces the physics with MLP1 (the player model, stage 1) trained on the recorded players, so the
outcomes in the corpus follow how real players actually did:

1. **Split the real players** (grouped by ``install_id``, the same unit as every other split) into
   a part MLP1 learns from and a part that is held out. The held-out players never reach MLP1 or
   the Judge's training corpus, so the Judge's real-data check is on players it has not seen in
   any form (no leakage through the generator).
2. **Train MLP1** on the training players' floors only.
3. **Simulate** ``n`` players exactly like sim-v4: the latent player (skill, reflex/tactics bias,
   drift, abrupt shifts) comes from ``DungeonDifficultyEnv``; each floor's settings come from the
   same mixture as the sim-v3 corpus (half the sessions open with the 5 calibration floors; uniform /
   near-preset / smooth-walk / static floors); the outcome (time, deaths, damage) is ONE draw of
   MLP1 for those settings, that skill and the player's last two floors
   (``sim_v2.sample_outcome``).
4. Write the rows in the ``v_corpus`` CSV format with ``source = "synthetic_mlp1"``,
   ``game_version = "synthetic_mlp1"`` and the latent ``sim_*`` columns (never used as features).
   Ratings are NULL (MLP1 does not predict them), so the Judge's target is the measured difficulty.

THESE ROWS ARE NOT REAL PLAYERS. They are simulated players whose outcomes follow a model fitted to
the recorded ones. With few recorded players MLP1 stays close to its physics prior (its residual is
small and bounded), so the corpus is mostly the prior plus what those players taught it. MLP1's
time output is capped at 90 s and deaths at 3 (the game's observation contract), so longer floors /
more deaths never appear in this corpus.

Standalone (an existing MLP1 model):
    python -m ml.judge_corpus --player-model ml/runs/real/1_player_model/player_model.pt --players 2000 --out corpus.csv
In the pipeline: ``python -m ml.pipeline judge --set judge.train_on=mlp1_synth``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from . import player_data as D
from .player_data import sim
from .player_model import PlayerModel
from .sim_v2 import sample_outcome

SOURCE = "synthetic_mlp1"
POLICY_VERSION = "mlp1-corpus"


def _corpus_module():
    from ml_spike.judge import make_synthetic_corpus as M

    return M


def generate(pm: PlayerModel, n_players: int, seed: int = 0) -> pd.DataFrame:
    """MLP1-simulated corpus (v_corpus columns + source + sim_*). Deterministic for (model, n, seed)."""
    M = _corpus_module()
    rng = np.random.default_rng([int(seed), 2027])
    player = sim.DungeonDifficultyEnv()  # latent player only; its physics is never used
    rows: List[Dict] = []
    for i in range(int(n_players)):
        player.reset(seed=int(seed) * 1_000_003 + i)
        sid = f"mlp1_{seed}_{i:05d}"
        n_floors = int(rng.integers(M.FLOORS_PER_SESSION[0], M.FLOORS_PER_SESSION[1] + 1))
        game_like = rng.random() < M.P_GAME_LIKE
        prev_action = None
        hist: List[np.ndarray] = []
        for f in range(1, n_floors + 1):
            if game_like and f <= len(sim.CAL_LEVELS):
                cal = sim.CAL_LEVELS[f - 1]
                p = M._cal_params(cal)
                mix = np.asarray(cal["mix"], dtype=np.float64)
                complexity = float(mix @ sim.ARCH_LEVELS)
                cs, phase, action = float(cal["cs"]), "calibration", None
            else:
                p, mix, complexity, cs, phase, action = M._sample_floor(rng, prev_action)
                prev_action = action
            rho, tau = player._axes()
            skill = float(player.skill)
            y = D.params_to_y([p[k] for k in sim.PARAM_ORDER], complexity)
            history = np.stack(hist[-D.HISTORY_LEN :]) if hist else None
            x = sample_outcome(pm, y, mix, cs, skill, history, rng)
            hist.append(np.asarray(x, dtype=np.float32))
            res = dict(
                time=float(x[0]) * D.TIME_NORM_S,
                deaths=int(round(float(x[1]) * D.DEATH_NORM)),
                gross=float(x[2]),  # damage / max HP; _row multiplies by PLAYER_HP
                rooms=int(round(p["room_count"])),
            )
            row = M._row(sid, f, phase, p, mix, complexity, cs, action, res, rho, tau, skill)
            row.update(source=SOURCE, game_version=SOURCE, policy_version=POLICY_VERSION)
            rows.append(row)
            player.level += 1
            player._advance_skill()
    df = pd.DataFrame(rows)
    df["created_at"] = np.arange(len(df))
    return df.reindex(columns=M.corpus_columns())


def split_real_players(raw: pd.DataFrame, holdout_frac: float, seed: int) -> tuple[list, list]:
    """Real players -> (MLP1 training ids, held-out ids), grouped by install_id (else session_id).

    At least one player on each side; needs >= 2 players."""
    from ml_spike.judge import common as C

    col = C.group_column(raw)
    ids = sorted(raw[col].astype(str).unique().tolist())
    if len(ids) < 2:
        raise ValueError(
            f"the telemetry has {len(ids)} player(s); the MLP1 corpus needs at least 2 "
            "(one to train MLP1, one held out to check the Judge). Use judge.train_on=synthetic."
        )
    n_hold = int(np.clip(round(holdout_frac * len(ids)), 1, len(ids) - 1))
    order = np.random.default_rng([int(seed), 77]).permutation(len(ids))
    held = sorted(ids[k] for k in order[:n_hold])
    train = sorted(ids[k] for k in order[n_hold:])
    return train, held


def build(telemetry: Path, out: Path, cfg: dict, consented_only: bool) -> dict:
    """Pipeline helper: split real players, train MLP1 on the training part, generate the corpus.

    Returns paths (relative to nothing; absolute) and a description of what was done."""
    from ml_spike.judge import common as C

    from . import train_player_model as T

    jc, pc, seed = cfg["judge"], cfg["player_model"], int(cfg["seed"])
    out.mkdir(parents=True, exist_ok=True)
    raw = C.read_corpus(telemetry, consented_only)
    col = C.group_column(raw)
    train_ids, held_ids = split_real_players(raw, float(jc["mlp1_holdout_frac"]), seed)
    is_train = raw[col].astype(str).isin(train_ids)
    train_csv, held_csv = out / "real_train_players.csv", out / "real_heldout_players.csv"
    raw[is_train].to_csv(train_csv, index=False)
    raw[~is_train].to_csv(held_csv, index=False)
    print(f"[judge/mlp1] real players: {len(train_ids)} train MLP1, {len(held_ids)} held out "
          f"(grouped by {col})")  # fmt: skip

    model_path = out / "player_model_corpus.pt"
    report = T.main(["--source", "real", "--telemetry", str(train_csv), "--members", str(pc["members"]),
                     "--epochs", str(pc["epochs"]), "--seed", str(seed), "--out", str(model_path)])  # fmt: skip
    pm = PlayerModel.load(str(model_path))
    n = int(jc["mlp1_players"])
    print(f"[judge/mlp1] simulating {n} players with MLP1 (SYNTHETIC rows, source={SOURCE})")
    corpus = generate(pm, n, seed)
    corpus_path = out / "mlp1_corpus.csv"
    corpus.to_csv(corpus_path, index=False)
    info = dict(
        corpus=str(corpus_path), heldout_csv=str(held_csv), train_csv=str(train_csv),
        player_model=str(model_path), group_column=col, train_players=train_ids,
        heldout_players=held_ids, mlp1_train_rows=int(report["n_train"] + report["n_val"]),
        mlp1_split=report["split_kind"], simulated_players=n, rows=int(len(corpus)), source=SOURCE,
    )  # fmt: skip
    (out / "mlp1_corpus_info.json").write_text(json.dumps(info, indent=2), "utf-8")
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player-model", required=True, help="MLP1 .pt (trained on real telemetry)")
    ap.add_argument("--players", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    pm = PlayerModel.load(args.player_model)
    df = generate(pm, args.players, args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"wrote {len(df)} SYNTHETIC (MLP1-generated, source={SOURCE}) floor rows from "
          f"{args.players} simulated players; MLP1 data source: {pm.data_source}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
