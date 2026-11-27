"""Rating-trained Judge vs the rest, leave-one-player-out on the real rated floors (6 players incl.
tonight's Pilot 2 run as its own player). Every method is fitted on the other players only.

  mean          : average rating of the training players
  formula       : old difficulty_score, linear map to rating
  judge_mlp1    : current mlp1_synth Judge (fold's own: MLP1+Judge never saw the held-out player), linear map
  judge_rating  : that Judge fine-tuned on real ratings (LightGBM boosting from the mapped Judge output)
Separately (outcomes of the SAME floor, so not a prediction): which weights on damage / deaths /
time per room best match the ratings, vs the hand weights 0.40 / 0.35 / 0.25.
"""
import sys, json, contextlib, io
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, ".")
from ml.config import load_config
from ml import judge_corpus as JC, train_player_model as T
from ml.player_model import PlayerModel
from ml_spike.judge import common as C, train_judge as TJ

DB = "ml/runs/tel1127_data/forge_merged_v2.db"; L = Path("ml/runs/tel1127_lopo"); OUT = L / "rating_judge"; OUT.mkdir(exist_ok=True)
cfg = load_config("ml/configs/default.json", []); seed = 0
raw = C.read_corpus(DB, True)
df, counts = C.prepare(raw, "measured")
df["r"] = C.rating_difficulty(df["perceived_difficulty"])
df = df[~df.r.isna()].reset_index(drop=True)
players = sorted(df.install_id.unique()); print(counts, "rated rows", len(df), "players", len(players))
old_order = sorted(p for p in players if not p.startswith("pc1127"))
def quiet(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()): return f(*a, **k)

def fold_judge(held):
    if held in old_order:
        return lgb.Booster(model_file=str(L / f"fold{old_order.index(held)}/judge_mlp1/judge_model.txt"))
    d = OUT / "fold_new"; d.mkdir(exist_ok=True)
    if not (d / "judge_mlp1/judge_model.txt").exists():
        raw[raw.install_id != held].to_csv(d / "train_players.csv", index=False)
        quiet(T.main, ["--source", "real", "--telemetry", str(d / "train_players.csv"), "--members", "5", "--epochs", "200", "--seed", "0", "--out", str(d / "mlp1.pt")])
        JC.generate(PlayerModel.load(str(d / "mlp1.pt")), 2000, 0).to_csv(d / "mlp1_corpus.csv", index=False)
        quiet(TJ.run, d / "mlp1_corpus.csv", d / "judge_mlp1", [], target="measured", seed=0, raw_targets=False)
    return lgb.Booster(model_file=str(d / "judge_mlp1/judge_model.txt"))

def outcome_feats(g):
    rooms = C._rooms(g); hp = C._max_hp(g)
    return np.column_stack([np.clip(g.damage_taken / hp, 0, 1), np.clip(g.deaths / 3, 0, 1), np.clip(g.completion_time / rooms / C.PACE_CAP, 0, 1)])
HAND = np.array([0.40, 0.35, 0.25])
FT = dict(objective="regression", metric="l1", learning_rate=0.05, num_leaves=4, min_data_in_leaf=10, lambda_l2=5.0, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, verbose=-1, deterministic=True, seed=0, num_threads=4)
FT_ROUNDS = 40

rows = []
for held in players:
    tr, te = df[df.install_id != held], df[df.install_id == held]
    Xtr, Xte, ytr = C.feature_matrix(tr), C.feature_matrix(te), tr.r.to_numpy()
    P = {"mean": np.full(len(te), ytr.mean())}
    a, b = np.polyfit(tr.proxy_difficulty, ytr, 1); P["formula"] = a * te.proxy_difficulty.to_numpy() + b
    J = fold_judge(held); jtr, jte = TJ.predict(J, Xtr), TJ.predict(J, Xte)
    a, b = np.polyfit(jtr, ytr, 1); base_tr, base_te = a * jtr + b, a * jte + b
    P["judge_mlp1"] = base_te
    ft = lgb.train(FT, lgb.Dataset(Xtr, label=ytr, init_score=base_tr, feature_name=C.FEATURES), FT_ROUNDS)
    P["judge_rating"] = base_te + ft.predict(Xte, raw_score=True)
    # outcome weights (same-floor outcomes): learned vs hand, each mapped to rating on training players
    O_tr, O_te = outcome_feats(tr), outcome_feats(te)
    A = np.column_stack([O_tr, np.ones(len(O_tr))]); w = np.linalg.lstsq(A, ytr, rcond=None)[0]
    P["outcome_learned"] = np.column_stack([O_te, np.ones(len(O_te))]) @ w
    h_tr, h_te = O_tr @ HAND, O_te @ HAND; a, b = np.polyfit(h_tr, ytr, 1); P["outcome_hand"] = a * h_te + b
    for m, p in P.items():
        rows.append(pd.DataFrame(dict(method=m, player=held[:8], phase=te.phase.values, y=te.r.values, p=np.clip(p, 0, 1))))
R = pd.concat(rows); R.to_csv(OUT / "predictions.csv", index=False)
def stars(x): return np.clip(np.round(x * 4 + 1), 1, 5)
summ = []
for m, g in R.groupby("method", sort=False):
    for scope, h in [("all", g), ("adaptive+static", g[g.phase != "calibration"])]:
        rho = [C.spearman(x.p, x.y) for _, x in h.groupby("player") if len(x) >= 5]
        summ.append(dict(method=m, floors=scope, n=len(h), mae_stars=4 * np.abs(h.p - h.y).mean(), exact=np.mean(stars(h.p) == stars(h.y)),
                         within1=np.mean(np.abs(stars(h.p) - stars(h.y)) <= 1), rank_per_player=np.nanmean(rho) if rho else np.nan, rank_pooled=C.spearman(h.p, h.y)))
S = pd.DataFrame(summ); S.to_csv(OUT / "summary.csv", index=False); print(S.round(3).to_string(index=False))
O = outcome_feats(df); w = np.linalg.lstsq(np.column_stack([O, np.ones(len(O))]), df.r, rcond=None)[0]
wn = np.clip(w[:3], 0, None); wn = wn / wn.sum()
print("learned outcome weights (all players): raw", np.round(w, 3), "normalised damage/deaths/time", np.round(wn, 2), "vs hand", HAND)
boot = []
rng = np.random.default_rng(0)
for _ in range(500):
    idx = np.concatenate([np.flatnonzero(df.install_id == p) for p in rng.choice(players, len(players))])
    ww = np.linalg.lstsq(np.column_stack([O[idx], np.ones(len(idx))]), df.r.values[idx], rcond=None)[0][:3]
    ww = np.clip(ww, 0, None); boot.append(ww / max(ww.sum(), 1e-9))
print("player-bootstrap 90% range of normalised weights:", np.round(np.percentile(boot, [5, 95], axis=0), 2).tolist())
print("per-player MAE (stars):"); print((R.assign(e=4 * (R.p - R.y).abs()).groupby(["method", "player"]).e.mean().unstack()).round(2).to_string())
