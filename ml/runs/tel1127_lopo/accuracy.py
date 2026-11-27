import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from ml import player_data as D, player_eval as E
from ml.player_model import PlayerModel
raw = pd.read_csv if False else None
DB = "ml/runs/tel1127_data/forge_merged.db"
ds = D.load_telemetry(DB, consented_only=True)
players = sorted(set(ds.player)); tot = {}; n = 0
for k, p in enumerate(players):
    te = ds.subset(np.flatnonzero(ds.player == p)); tr = ds.subset(np.flatnonzero(ds.player != p))
    m = PlayerModel.load(f"ml/runs/tel1127_lopo/fold{k}/mlp1.pt")
    r = E.evaluate_mae(m, te, tr)
    for name, v in r.items():
        if isinstance(v, dict):
            for key, val in v.items():
                if isinstance(val, (int, float)):
                    tot.setdefault((name, key), 0.0); tot[(name, key)] += val * len(te)
    n += len(te)
    if k == 0: print({a: (list(b) if isinstance(b, dict) else b) for a, b in r.items()})
print("MLP1 leave-one-player-out, rows", n)
for (name, key), v in tot.items(): print(f"  {name:14s} {key:14s} {v/n:.3f}")
R = pd.read_csv("ml/runs/tel1127_lopo/predictions.csv")
print("Judge variants (pooled held-out rows)")
for name, g in R.groupby("method", sort=False):
    r2 = 1 - ((g.pred - g.measured) ** 2).sum() / ((g.measured - g.measured.mean()) ** 2).sum()
    q = g.dropna(subset=["rating"]); stars = np.clip(np.round(q.pred_rating * 4 + 1), 1, 5); true = np.round(q.rating * 4 + 1)
    print(f"  {name:11s} R2_measured {r2:5.2f}  rating exact {np.mean(stars == true):.0%}  within1 {np.mean(abs(stars - true) <= 1):.0%}")
res = {}
for k, p in enumerate(players):
    te = ds.subset(np.flatnonzero(ds.player == p)); tr = ds.subset(np.flatnonzero(ds.player != p))
    r = E.evaluate_mae(PlayerModel.load(f"ml/runs/tel1127_lopo/fold{k}/mlp1.pt"), te, tr)
    for name, v in r["mae"].items():
        for o, val in v.items(): res[(name, o)] = res.get((name, o), 0) + val * len(te) / n
print("MLP1 held-out MAE (natural units)")
for k_, v in res.items(): print("  ", k_, round(v, 3))
x = ds.x * E.UNIT_SCALE; print("real means (time s, deaths, dmg):", x.mean(0).round(2), "std", x.std(0).round(2))
