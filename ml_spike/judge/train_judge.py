"""Train and evaluate the empirical FORGE Judge (LightGBM) and compare it with the old linear proxy.

Pipeline (target and features are defined in ml_spike/judge/common.py):
  1. Read the training corpus (default: the SYNTHETIC sim-v3 corpus; generated if missing).
  2. Hold out 20 % of PLAYERS as the test set (grouped by install_id: no player on both sides).
  3. 5-fold grouped CV on the remaining players (early stopping per fold) -> number of trees.
  4. Fit on all training players, score the held-out test players. Baselines:
       * proxy_raw  : DifficultyManager.calculate_difficulty_score() / 100 (the hand-weighted Judge)
       * proxy_cal  : the same score with a linear rescale fitted on the training players
       * linear     : ordinary least squares on the same 18 features
       * mean       : training-set mean
  5. Score REAL telemetry rows (the game DB is synced into a temporary copy first; consented sessions
     only unless --include-unconsented). n is reported and is far too small to conclude anything.
  6. Save judge_model.txt (LightGBM native text) + judge_model.json (features, target definition,
     metrics, data counts, git commit).

Run from the repo root:
    python -m ml_spike.judge.make_synthetic_corpus            # optional; done automatically
    python -m ml_spike.judge.train_judge --real-db "%APPDATA%/Godot/app_userdata/FORGE - Adaptive Dungeon Prototype/forge_telemetry.db"

FYP-2: pass the exported real corpus as --corpus (CSV or .db) and --target rating; no code change.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import lightgbm as lgb
import numpy as np
import pandas as pd
from ml_spike.judge import common as C
from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase

LGB_PARAMS = {
    "objective": "regression",
    "metric": "l1",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 40,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbose": -1,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 4,
}
MAX_ROUNDS = 2000
EARLY_STOP = 100


def _params(seed: int) -> Dict:
    p = dict(LGB_PARAMS)
    p["seed"] = seed
    return p


def fit_lgb(X, y, seed=0, rounds=None, X_val=None, y_val=None, params=None) -> lgb.Booster:
    """LightGBM regressor; with a validation set it early-stops, else trains `rounds` trees."""
    prm = dict(params or _params(seed))
    dtrain = lgb.Dataset(X, label=y, feature_name=C.FEATURES, free_raw_data=False)
    if X_val is not None:
        dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)
        return lgb.train(
            prm,
            dtrain,
            num_boost_round=rounds or MAX_ROUNDS,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
        )
    return lgb.train(prm, dtrain, num_boost_round=rounds or 300)


def predict(booster: lgb.Booster, X) -> np.ndarray:
    return np.clip(booster.predict(X, num_iteration=booster.best_iteration or None), 0.0, 1.0)


class LinearBaseline:
    """OLS on the 18 features; NaN context -> training mean plus a has_prev indicator."""

    def fit(self, X, y):
        self.fill = np.nanmean(X, axis=0)
        self.fill = np.where(np.isnan(self.fill), 0.0, self.fill)
        A = self._design(X)
        self.coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        return self

    def _design(self, X):
        Xf = np.where(np.isnan(X), self.fill, X)
        has_prev = (~np.isnan(X[:, -1])).astype(float)[:, None]
        return np.hstack([np.ones((len(X), 1)), Xf, has_prev])

    def predict(self, X):
        return np.clip(self._design(X) @ self.coef, 0.0, 1.0)


def baseline_predictions(train_df, y_train, X_train, eval_df, X_eval) -> Dict[str, np.ndarray]:
    proxy_tr = train_df["proxy_difficulty"].to_numpy(dtype=float)
    a, b = np.polyfit(proxy_tr, y_train, 1)
    proxy_ev = eval_df["proxy_difficulty"].to_numpy(dtype=float)
    return {
        "proxy_raw": proxy_ev,
        "proxy_cal": np.clip(a * proxy_ev + b, 0.0, 1.0),
        "linear": LinearBaseline().fit(X_train, y_train).predict(X_eval),
        "mean": np.full(len(eval_df), float(np.mean(y_train))),
    }


def cross_validate(df: pd.DataFrame, X, y, groups, k=5, seed=0) -> Dict:
    folds: List[Dict] = []
    for i, (tr, va) in enumerate(C.grouped_kfold(groups, k, seed)):
        booster = fit_lgb(X[tr], y[tr], seed, X_val=X[va], y_val=y[va])
        res = {"fold": i, "best_iteration": int(booster.best_iteration)}
        res["judge"] = C.regression_metrics(y[va], predict(booster, X[va]))
        for name, pred in baseline_predictions(
            df.iloc[tr], y[tr], X[tr], df.iloc[va], X[va]
        ).items():
            res[name] = C.regression_metrics(y[va], pred)
        folds.append(res)
    summary = {}
    for name in ("judge", "proxy_raw", "proxy_cal", "linear", "mean"):
        for m in ("mae", "rmse", "r2"):
            vals = [f[name][m] for f in folds]
            summary[f"{name}_{m}_mean"] = float(np.mean(vals))
            summary[f"{name}_{m}_std"] = float(np.std(vals))
    rounds = int(round(np.mean([f["best_iteration"] for f in folds])))
    return {"folds": folds, "summary": summary, "rounds": rounds}


def raw_outcome_models(df_tr, df_te, X_tr, X_te, seed, rounds=400) -> Dict:
    """Extra: one LightGBM per raw outcome (same features). Only R^2 / MAE on the test players."""
    out = {}
    prm = _params(seed)
    prm["metric"] = "l2"
    for t in C.RAW_TARGETS:
        ytr = pd.to_numeric(df_tr[t], errors="coerce").to_numpy(dtype=float)
        yte = pd.to_numeric(df_te[t], errors="coerce").to_numpy(dtype=float)
        b = lgb.train(prm, lgb.Dataset(X_tr, label=ytr, feature_name=C.FEATURES), rounds)
        out[t] = C.regression_metrics(yte, b.predict(X_te))
    return out


def evaluate_real(booster, real_paths: List[str], consented_only: bool, train_df, X_train, y_train):
    """Score real telemetry rows (each game DB is synced into a temporary TelemetryDatabase)."""
    if not real_paths:
        return {"status": "no real DB given or found"}
    frames = []
    synced = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, path in enumerate(real_paths):
            path = str(path)
            if not os.path.exists(path):
                synced.append({"file": os.path.basename(path), "status": "missing"})
                continue
            if path.lower().endswith(".csv"):
                frames.append(C.read_corpus(path, consented_only))
                synced.append({"file": os.path.basename(path), "status": "csv"})
                continue
            db = TelemetryDatabase(os.path.join(tmp, f"real_{i}.db"))
            n_s, n_f = db.sync_from_game_db(path)
            synced.append({"file": os.path.basename(path), "sessions": n_s, "floors": n_f})
            frames.append(C.read_corpus(db.db_path, consented_only))
    if not frames:
        return {"status": "no readable real DB", "sources": synced}
    raw = pd.concat(frames, ignore_index=True).drop_duplicates(["session_id", "floor_num"])
    raw["source"] = "real"
    df, counts = C.prepare(raw, "auto")
    out: Dict = {"sources": synced, "counts": counts, "consented_only": consented_only}
    if df.empty:
        out["status"] = "no usable rows"
        return out
    X = C.feature_matrix(df)
    pred = predict(booster, X)
    base = baseline_predictions(train_df, y_train, X_train, df, X)
    measured = df["measured_difficulty"].to_numpy(dtype=float)
    rows_out = []
    for i, r in df.reset_index(drop=True).iterrows():
        rows_out.append(
            {
                "session_id": r["session_id"],
                "floor_num": int(r["floor_num"]),
                "phase": r.get("phase"),
                "rating": None
                if pd.isna(r.get("perceived_difficulty"))
                else float(r["perceived_difficulty"]),
                "target": float(r["difficulty"]),
                "target_kind": r["target_kind"],
                "measured": float(measured[i]),
                "judge": float(pred[i]),
                "proxy_raw": float(base["proxy_raw"][i]),
            }
        )
    out["rows"] = rows_out
    # (a) against the measured target (same definition the model was trained on)
    out["vs_measured"] = {
        name: C.regression_metrics(measured, p)
        for name, p in [("judge", pred)] + list(base.items())
    }
    # (b) against the player's own rating, where it exists
    rated = df["target_kind"].to_numpy() == "rating"
    if rated.any():
        yr = df["difficulty"].to_numpy(dtype=float)[rated]
        out["vs_rating"] = {
            name: C.regression_metrics(yr, p[rated])
            for name, p in [("judge", pred)] + list(base.items())
        }
        out["spearman_vs_rating"] = {
            "judge": C.spearman(pred[rated], yr),
            "proxy_raw": C.spearman(base["proxy_raw"][rated], yr),
            "measured_target": C.spearman(measured[rated], yr),
        }
    out["status"] = "ok (n too small to conclude)"
    return out


def run(
    corpus: Path,
    out_dir: Path,
    real_paths: List[str],
    consented_only: bool = True,
    target: str = "auto",
    seed: int = 0,
    test_frac: float = 0.2,
    folds: int = 5,
    raw_targets: bool = True,
) -> Dict:
    raw = C.read_corpus(corpus)
    df, counts = C.prepare(raw, target)
    groups = df[C.group_column(df)].to_numpy()
    n_groups = len(set(groups.tolist()))
    if n_groups < folds + 2:
        raise SystemExit(
            f"{corpus}: only {n_groups} player(s); a grouped {folds}-fold CV + held-out test needs "
            f"at least {folds + 2}. Collect more players (FYP-2 target: 25+)."
        )
    tr_idx, te_idx = C.grouped_holdout(groups, test_frac, seed)
    df_tr, df_te = df.iloc[tr_idx].reset_index(drop=True), df.iloc[te_idx].reset_index(drop=True)
    X_tr, X_te = C.feature_matrix(df_tr), C.feature_matrix(df_te)
    y_tr = df_tr["difficulty"].to_numpy(dtype=float)
    y_te = df_te["difficulty"].to_numpy(dtype=float)
    assert not set(df_tr[C.group_column(df)]) & set(df_te[C.group_column(df)]), "group leakage"

    print(f"corpus {corpus}: {counts}")
    print(f"train players {len(set(groups[tr_idx]))}, test players {len(set(groups[te_idx]))}")
    cv = cross_validate(df_tr, X_tr, y_tr, df_tr[C.group_column(df)].to_numpy(), folds, seed)
    print(f"CV ({folds} grouped folds): rounds={cv['rounds']}  " + _fmt(cv["summary"], "judge"))

    booster = fit_lgb(X_tr, y_tr, seed, rounds=cv["rounds"])
    test = {"judge": C.regression_metrics(y_te, predict(booster, X_te))}
    for name, pred in baseline_predictions(df_tr, y_tr, X_tr, df_te, X_te).items():
        test[name] = C.regression_metrics(y_te, pred)
    for name, m in test.items():
        print(f"  test {name:9s} MAE {m['mae']:.4f}  RMSE {m['rmse']:.4f}  R2 {m['r2']:.3f}")

    extra = raw_outcome_models(df_tr, df_te, X_tr, X_te, seed) if raw_targets else {}
    real = evaluate_real(booster, real_paths, consented_only, df_tr, X_tr, y_tr)
    if "vs_measured" in real:
        n = real["vs_measured"]["judge"]["n"]
        print(f"REAL rows (n={n}, n too small to conclude): {real['counts']}")
        for k in ("vs_measured", "vs_rating"):
            if k in real:
                j, p = real[k]["judge"], real[k]["proxy_raw"]
                print(f"  {k}: judge MAE {j['mae']:.3f} | proxy MAE {p['mae']:.3f} (n={j['n']})")
    else:
        print(f"REAL rows: {real.get('status')}")

    importance = dict(
        zip(C.FEATURES, booster.feature_importance("gain").astype(float).round(4).tolist())
    )
    sources = sorted(df["source"].astype(str).unique().tolist())
    meta = {
        "model": "LightGBM regressor (gbdt)",
        "lightgbm_version": lgb.__version__,
        "features": C.FEATURES,
        "context_features": C.CONTEXT_FEATURES,
        "first_floor_context": "NaN (LightGBM missing-value branch)",
        "target": C.TARGET_DEFINITION,
        "target_mode": target,
        "training_corpus": {
            "path": _rel(corpus),
            "sources": sources,
            "synthetic": all(s.startswith("synthetic") for s in sources),
            "counts": counts,
            "train_rows": int(len(df_tr)),
            "test_rows": int(len(df_te)),
            "train_players": int(df_tr[C.group_column(df)].nunique()),
            "test_players": int(df_te[C.group_column(df)].nunique()),
            "split": f"grouped by {C.group_column(df)}; test_frac={test_frac}; seed={seed}",
        },
        "params": {**_params(seed), "num_boost_round": cv["rounds"]},
        "cv": cv,
        "test_metrics": test,
        "raw_outcome_models": extra,
        "real_eval": real,
        "expected_value_mean_train": float(np.mean(y_tr)),
        "feature_reference": C.feature_reference(df_tr),
        "feature_importance_gain": importance,
        "git_commit": C.git_commit(),
        "trained_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out_dir / "judge_model.txt"))
    (out_dir / "judge_model.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"saved {out_dir / 'judge_model.txt'} and judge_model.json")
    return meta


def _fmt(summary: Dict, name: str) -> str:
    return " ".join(
        f"{m.upper()} {summary[f'{name}_{m}_mean']:.4f}+-{summary[f'{name}_{m}_std']:.4f}"
        for m in ("mae", "rmse", "r2")
    )


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(C.REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Train the FORGE Judge (LightGBM).")
    ap.add_argument("--corpus", default=str(C.DEFAULT_CORPUS), help="CSV or telemetry .db")
    ap.add_argument(
        "--real-db",
        action="append",
        default=None,
        help="game forge_telemetry.db (or exported CSV) to validate on; repeatable. "
        "Default: the game's user:// DB if it exists.",
    )
    ap.add_argument("--include-unconsented", action="store_true")
    ap.add_argument("--target", choices=["auto", "measured", "rating"], default="auto")
    ap.add_argument("--out-dir", default=str(C.JUDGE_DIR))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--players", type=int, default=3000, help="if the corpus must be generated")
    ap.add_argument("--no-raw-targets", action="store_true")
    args = ap.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.exists():
        if corpus.resolve() != C.DEFAULT_CORPUS.resolve():
            print(f"corpus not found: {corpus}", file=sys.stderr)
            return 2
        from ml_spike.judge import make_synthetic_corpus

        print("synthetic corpus missing; generating it ...")
        make_synthetic_corpus.main(["--players", str(args.players), "--seed", str(args.seed)])
    real = args.real_db
    if real is None:
        found = TelemetryDatabase.locate_game_db()
        real = [found] if found else []
    run(
        corpus,
        Path(args.out_dir),
        real,
        consented_only=not args.include_unconsented,
        target=args.target,
        seed=args.seed,
        raw_targets=not args.no_raw_targets,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
