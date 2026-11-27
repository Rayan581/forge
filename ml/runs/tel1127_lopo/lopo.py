"""Leave-one-player-out comparison of Judge variants on the recorded players. Same held-out rows for every method."""
import sys, json, contextlib, io
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, ".")
from ml.config import load_config
from ml import judge_corpus as JC, train_player_model as T
from ml.player_model import PlayerModel
from ml_spike.judge import common as C, train_judge as TJ, make_synthetic_corpus as M

DB = "ml/runs/tel1127_data/forge_merged.db"
OUT = Path("ml/runs/tel1127_lopo"); OUT.mkdir(parents=True, exist_ok=True)
cfg = load_config("ml/configs/default.json", []); seed = int(cfg["seed"])
raw = C.read_corpus(DB, True)
real, counts = C.prepare(raw, "measured")
real["rating01"] = C.rating_difficulty(real["perceived_difficulty"])
players = sorted(real.install_id.unique())
print(counts)

def quiet(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()): return f(*a, **k)

sim_df = M.generate(int(cfg["judge"]["synthetic_players"]), seed)
sim_path = OUT / "sim_v3.csv"; sim_df.to_csv(sim_path, index=False)
meta = quiet(TJ.run, sim_path, OUT / "judge_sim", [], target="measured", seed=seed, raw_targets=False)
sim_booster = lgb.Booster(model_file=str(OUT / "judge_sim/judge_model.txt"))
sim_rounds = meta["params"]["num_boost_round"]
sim_p, _ = C.prepare(sim_df, "measured")

preds = []
for k, held in enumerate(players):
    d = OUT / f"fold{k}"; d.mkdir(exist_ok=True)
    tr, te = real[real.install_id != held], real[real.install_id == held]
    Xtr, Xte = C.feature_matrix(tr), C.feature_matrix(te)
    ym = tr.difficulty.to_numpy(float)
    P = {}
    P["sim_v3"] = (TJ.predict(sim_booster, Xtr), TJ.predict(sim_booster, Xte))
    both = pd.concat([sim_p, tr], ignore_index=True)
    b = TJ.fit_lgb(C.feature_matrix(both), both.difficulty.to_numpy(float), seed, rounds=sim_rounds)
    P["mixed"] = (TJ.predict(b, Xtr), TJ.predict(b, Xte))
    raw[raw.install_id != held].to_csv(d / "train_players.csv", index=False)
    quiet(T.main, ["--source", "real", "--telemetry", str(d / "train_players.csv"), "--members", str(cfg["player_model"]["members"]),
                   "--epochs", str(cfg["player_model"]["epochs"]), "--seed", str(seed), "--out", str(d / "mlp1.pt")])
    JC.generate(PlayerModel.load(str(d / "mlp1.pt")), int(cfg["judge"]["mlp1_players"]), seed).to_csv(d / "mlp1_corpus.csv", index=False)
    quiet(TJ.run, d / "mlp1_corpus.csv", d / "judge_mlp1", [], target="measured", seed=seed, raw_targets=False)
    b = lgb.Booster(model_file=str(d / "judge_mlp1/judge_model.txt"))
    P["mlp1_synth"] = (TJ.predict(b, Xtr), TJ.predict(b, Xte))
    prm = dict(TJ._params(seed), min_data_in_leaf=5, num_leaves=7)
    b = TJ.fit_lgb(Xtr, ym, seed, rounds=100, params=prm)
    P["real_only"] = (TJ.predict(b, Xtr), TJ.predict(b, Xte))
    a, c = np.polyfit(tr.proxy_difficulty, ym, 1)
    P["proxy_cal"] = (a * tr.proxy_difficulty.to_numpy() + c, a * te.proxy_difficulty.to_numpy() + c)
    P["proxy_raw"] = (tr.proxy_difficulty.to_numpy(), te.proxy_difficulty.to_numpy())
    P["mean"] = (np.full(len(tr), ym.mean()), np.full(len(te), ym.mean()))
    # rating: linear map prediction -> rating fitted on the TRAINING players only
    rt = tr.rating01.to_numpy(); ok = ~np.isnan(rt)
    for name, (ptr, pte) in P.items():
        if name == "mean": cal = np.full(len(te), rt[ok].mean())
        else:
            a, c = np.polyfit(ptr[ok], rt[ok], 1); cal = a * pte + c
        preds.append(pd.DataFrame(dict(method=name, player=held[:6], phase=te.phase, measured=te.difficulty,
                                       rating=te.rating01, pred=pte, pred_rating=cal)))
    print("fold", k, held[:6], len(te), "rows done", flush=True)

R = pd.concat(preds); R.to_csv(OUT / "predictions.csv", index=False)
rows = []
for name, g in R.groupby("method", sort=False):
    r = g.dropna(subset=["rating"])
    sm = [C.spearman(x.pred, x.measured) for _, x in g.groupby("player")]
    sr = [C.spearman(x.pred, x.rating) for _, x in r.groupby("player")]
    rows.append(dict(method=name, mae_measured=np.abs(g.pred - g.measured).mean(), rho_measured=np.nanmean(sm) if np.isfinite(sm).any() else np.nan,
        mae_rating_uncal=np.abs(r.pred - r.rating).mean(), mae_rating_cal=np.abs(r.pred_rating - r.rating).mean(),
        rho_rating=np.nanmean(sr) if np.isfinite(sr).any() else np.nan, n_measured=len(g), n_rating=len(r)))
S = pd.DataFrame(rows); S.to_csv(OUT / "summary.csv", index=False)
print(S.round(3).to_string(index=False))
per = R.assign(ae=(R.pred - R.measured).abs(), aer=(R.pred_rating - R.rating).abs()).groupby(["method", "player"])[["ae", "aer"]].mean().unstack()
per.to_csv(OUT / "per_player.csv"); print(per.round(3).to_string())
x = R[R.method == "mean"].dropna(subset=["rating"])
print("measured vs rating, per-player spearman:", {p: round(C.spearman(g.measured, g.rating), 2) for p, g in x.groupby("player")})
