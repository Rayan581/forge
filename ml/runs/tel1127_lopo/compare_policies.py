"""Compare exported policies: difficulty score by (held-constant) performance, on recorded situations,
by latent skill in sim-v4, and pacing / deaths in the old physics simulator (sim-v3).
usage: python compare_policies.py name=path [name=path ...] [--sim-run ml/runs/<run>]"""
import sys, json, numpy as np, sqlite3, pandas as pd
sys.path.insert(0, ".")
from ml import sim_v2 as S, ppo_train as P
from ml.player_data import sim
args = [a for a in sys.argv[1:] if not a.startswith("--")]
run = sys.argv[sys.argv.index("--sim-run") + 1] if "--sim-run" in sys.argv else "ml/runs/tel1127_mlp1"
args = [a for a in args if a != run]
pols = {a.split("=")[0]: S.json_policy_fn(a.split("=")[1]) for a in args}
def score(a): return sim.difficulty_score(S.params_from_action(a)[0])
def obs(t, d, r, p, lvl): return np.array([min(t/90,1), min(d/3,1), min(r,1), sim.norm(p["enemy_health"],"enemy_health"), sim.norm(p["enemy_damage"],"enemy_damage"), sim.norm(p["hazard_density"],"hazard_density"), sim.norm(p["room_count"],"room_count"), min(lvl/10,1)], np.float32)
start = dict(enemy_health=90, enemy_damage=30, hazard_density=.65, room_count=5)
print("Score on floors 6..13 when every floor goes the same way (time s, deaths, damage share):")
for t, d, r in [(12,0,0),(25,0,.1),(35,0,.3),(45,0,.5),(60,1,.8),(90,3,1)]:
    line = []
    for n, pol in pols.items():
        o = obs(t,d,r,start,6); out = []
        for k in range(8):
            a = pol(o); p, _ = S.params_from_action(a); out.append(score(a)); o = obs(t,d,r,p,7+k)
        line.append(f"{n}: {out[0]}->{out[-1]}")
    print(f"  {(t,d,r)}  " + " | ".join(line))
c = sqlite3.connect("file:ml/runs/tel1127_data/forge_merged.db?mode=ro", uri=True)
F = pd.read_sql("select * from floors where manual_override=0 and obs_0 is not null", c)
O = F[[f"obs_{i}" for i in range(8)]].to_numpy()
for n, pol in pols.items():
    s = np.array([score(a) for a in pol(O)]); print(f"recorded situations ({len(s)}) {n}: mean {s.mean():.1f}, range {s.min()}-{s.max()}")
cfg = json.load(open(f"{run}/3_sim/sim_config.json"))
env = S.DungeonDifficultyEnvV2(cfg["player_model"], cfg["judge"], cfg["sim"])
for n, pol in pols.items():
    rows = [r for i in range(60) for r in S.run_episode(env, pol, 70000 + i)]
    sk = np.array([r["skill"] for r in rows]); pr = np.array([r["proxy"] for r in rows]) * 100
    dd = np.array([r["deaths"] for r in rows]); pe = np.array([r["pace_err"] for r in rows])
    b = {f"{lo}-{hi}": f"{pr[(sk>=lo)&(sk<hi)].mean():.0f}" for lo, hi in [(0,.33),(.33,.66),(.66,1.01)]}
    print(f"sim-v4 {n}: score by skill {b}, deaths/floor {dd.mean():.2f}, pace err {pe.mean():.3f}, max score {pr.max():.0f}")
for n, pol in pols.items():
    pe, de = P._old_sim_pace(pol, 20)
    print(f"sim-v3 (physics) {n}: pace err {pe:.3f}, deaths/floor {de:.2f}")
