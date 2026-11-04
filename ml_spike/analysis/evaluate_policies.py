"""Evaluate the sim-v2 PPO policy against three baselines on simulated player profiles.

Baselines
  (i)   10 random-initialised policies (same architecture, deterministic output)
  (ii)  Python port of PPOPolicy._fallback_heuristic (7-dim; a7 from the difficulty score)
  (iii) static +8 % mode (Intermediate preset, hp/dmg x(1+0.08*(floor-1)), a7 = -0.1)

Usage (from the repository root):
  python ml_spike/analysis/evaluate_policies.py <runs_dir> <best_seed> [out_md] [--skip-checks]

<runs_dir> must hold ppo_seed<k>.zip written by train_with_logging.py.  The *exported*
JSON (godot_prototype/ai/policy_weights.json) is evaluated through the NumPy mirror of
PPOPolicy.gd, so the numbers below are what the game will do.
"""

import glob
import importlib.util
import json
import os
import sys

import numpy as np
from scipy import stats
from stable_baselines3 import PPO

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tpd = _load("tpd", "../train_ppo_difficulty.py")

PROFILES = {  # initial player skill
    "novice (0.10)": 0.10,
    "novice (0.20)": 0.20,
    "mid (0.45)": 0.45,
    "skilled (0.70)": 0.70,
    "expert (0.80)": 0.80,
    "expert (0.90)": 0.90,
}
N_EP = 100  # paired episodes per profile
N_LEVELS = tpd.MAX_LEVELS
SEED0 = 10_000
PACE_OK = 0.15


# ----------------------------------------------------------------- policies
def heuristic_action(obs):
    """Python port of PPOPolicy._fallback_heuristic() (7 outputs) + the contract's legacy
    rule for index 7: a7 = 2 * difficulty_score / 100 - 1 computed from the denormalised params."""
    nt, nd, ndm, hp, dmg, haz, rooms = [float(x) for x in obs[:7]]
    sig = (0.5 - nt) * 1.4 - nd * 1.5 - ndm * 0.8
    sig = float(np.clip(sig, -1.0, 1.0))
    step = 0.12
    a = [
        np.clip(hp * 2.0 - 1.0 + sig * step, -1, 1),
        np.clip(dmg * 2.0 - 1.0 + sig * step, -1, 1),
        np.clip(sig * 0.5, -1, 1),
        np.clip(sig * 0.5, -1, 1),
        np.clip(haz * 2.0 - 1.0 + sig * step, -1, 1),
        np.clip(sig * 0.3, -1, 1),
        np.clip(rooms * 2.0 - 1.0 + sig * step, -1, 1),
    ]
    params = {k: float(tpd.denorm(a[i], k)) for i, k in enumerate(tpd.PARAM_ORDER)}
    a7 = tpd.legacy_a7_from_score(tpd.difficulty_score(params))
    return np.array(a + [a7], dtype=np.float32)


def json_policy_fn(path):
    """Exact NumPy mirror of PPOPolicy.gd: tanh hidden layers, linear output clipped to [-1, 1]."""
    layers = json.load(open(path))["layers"]
    W = [np.array(layer["w"], dtype=np.float64) for layer in layers]
    B = [np.array(layer["b"], dtype=np.float64) for layer in layers]

    def f(obs):
        x = np.asarray(obs, dtype=np.float64)
        for i, (w, b) in enumerate(zip(W, B)):
            x = w @ x + b
            if i < len(W) - 1:
                x = np.tanh(x)
        return np.clip(x, -1.0, 1.0).astype(np.float32)

    return f


def model_fn(model):
    return lambda obs: model.predict(obs, deterministic=True)[0]


# ----------------------------------------------------------------- episodes
def run_episode(policy, skill, seed, shifts=None):
    """policy: callable obs->8-dim action, or the string 'static'."""
    env = tpd.DungeonDifficultyEnv()
    opts = {"skill": skill}
    if shifts is not None:
        opts["shifts"] = shifts
    obs, _ = env.reset(seed=seed, options=opts)
    rec = {k: [] for k in ["reward", "pace", "deaths", "dmg", "score", "challenge", "skill"]}
    acts, params, mixes, levels = [], [], [], []
    for lv in range(N_LEVELS):
        if isinstance(policy, str):
            obs, r, done, info = env.step_static(lv + 1)
            # report the same quantities for the static mode (unclipped normalised "action")
            vec = np.append(tpd.to_action(info["params"]), tpd.STATIC_A7)
            p = dict(info["params"])
        else:
            a = np.asarray(policy(obs), dtype=np.float64)
            obs, r, done, _, info = env.step(a)
            vec = np.clip(a, -1.0, 1.0)
            p = dict(env.params)
        rec["reward"].append(r)
        rec["pace"].append(info["pace_err"])
        rec["deaths"].append(info["deaths"])
        rec["dmg"].append(info["dmg_ratio"])
        rec["score"].append(tpd.difficulty_score(p))
        rec["challenge"].append(info["challenge"])
        rec["skill"].append(env.skill)
        acts.append(vec)
        params.append([p[k] for k in tpd.PARAM_ORDER])
        mixes.append(tpd.archetype_mix(vec[7]))
        levels.append(lv)
        if done:
            break
    out = {k: np.array(v, dtype=np.float64) for k, v in rec.items()}
    out["acts"] = np.array(acts)
    out["params"] = np.array(params)
    out["mix"] = np.array(mixes)
    return out


def evaluate(policy, skill, shifts=None, n=N_EP):
    return [run_episode(policy, skill, SEED0 + i, shifts) for i in range(n)]


def summarize(eps):
    """Per-episode scalars -> dict of arrays (length n_episodes)."""
    d = {
        "reward": [e["reward"].mean() for e in eps],
        "pace": [e["pace"].mean() for e in eps],
        "deaths": [e["deaths"].mean() for e in eps],
        # mean over dims of |a_t - a_{t-1}|, floors 2..N (the first step has no predecessor)
        "dact": [np.abs(np.diff(e["acts"], axis=0)).mean() for e in eps],
        "score": [e["score"].mean() for e in eps],
        "challenge": [e["challenge"].mean() for e in eps],
    }
    d = {k: np.array(v) for k, v in d.items()}
    d["acts"] = np.mean([e["acts"].mean(axis=0) for e in eps], axis=0)
    d["params"] = np.mean([e["params"].mean(axis=0) for e in eps], axis=0)
    d["mix"] = np.mean([e["mix"].mean(axis=0) for e in eps], axis=0)
    return d


def pooled(sums):
    """Average several policies' per-episode arrays (paired by episode)."""
    out = {}
    for k in ["reward", "pace", "deaths", "dact", "score", "challenge"]:
        out[k] = np.mean([s[k] for s in sums], axis=0)
    for k in ["acts", "params", "mix"]:
        out[k] = np.mean([s[k] for s in sums], axis=0)
    return out


# ------------------------------------------------------------------ markdown
def ms(x, nd=2):
    return f"{np.mean(x):.{nd}f}"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def recovery_floors(curve, start, thr=PACE_OK, horizon=10):
    """First floor offset (>=1; the first affected floor is 1) from `start` after which the
    cross-episode mean pacing error stays <= thr for two consecutive floors; None if never."""
    for m in range(horizon):
        i = start + m
        if i + 1 < len(curve) and curve[i] <= thr and curve[i + 1] <= thr:
            return m + 1
    return None


def main():
    runs = sys.argv[1]
    best = int(sys.argv[2])
    out_md = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
    skip_checks = "--skip-checks" in sys.argv
    out_md = out_md or os.path.join(HERE, "results_sim_v2.md")
    fig_dir = os.path.join(HERE, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    shipped = os.path.join(REPO, "godot_prototype", "ai", "policy_weights.json")

    seeds = sorted(glob.glob(f"{runs}/ppo_seed*.zip"))
    models = {int(os.path.basename(p)[8:-4]): PPO.load(p, device="cpu") for p in seeds}
    rand_models = [
        PPO(
            "MlpPolicy",
            tpd.DungeonDifficultyEnv(),
            policy_kwargs=dict(net_arch=[64, 64]),
            seed=1000 + s,
            device="cpu",
        )
        for s in range(10)
    ]
    pol = {"trained (exported)": json_policy_fn(shipped)}
    for k, m in models.items():
        pol[f"seed {k}"] = model_fn(m)

    R = {}  # R[profile][name] = summary
    for pname, skill in PROFILES.items():
        R[pname] = {}
        for name, fn in pol.items():
            R[pname][name] = summarize(evaluate(fn, skill))
        rs = [summarize(evaluate(model_fn(m), skill)) for m in rand_models]
        R[pname]["random-init (10)"] = pooled(rs)
        R[pname]["heuristic"] = summarize(evaluate(heuristic_action, skill))
        R[pname]["static +8%"] = summarize(evaluate("static", skill))
        print(pname, "done", flush=True)

    base_names = ["random-init (10)", "heuristic", "static +8%"]
    md = ["# Simulator v2 — evaluation of the retrained PPO policy\n"]
    md.append(
        f"Protocol: {N_EP} paired episodes x {N_LEVELS} levels per profile (episode i uses seed "
        f"{SEED0}+i for every policy, so all policies face the same player trajectory: skill "
        "drift + random abrupt shifts of the default population, and the same noise stream "
        "family).  `trained (exported)` is `godot_prototype/ai/policy_weights.json` run through "
        f"the NumPy mirror of PPOPolicy.gd (seed {best}); `seed k` rows are the SB3 checkpoints "
        "of the three training runs.  Pacing error = |t_room - 7.5 s| / 7.5 s.\n"
    )

    # ---- main metrics table
    for metric, label, nd in [
        ("reward", "Reward / level (higher is better)", 3),
        ("pace", "Pacing error |t_room - target| / target (lower is better)", 3),
        ("deaths", "Deaths / level (lower is better)", 3),
        ("dact", "Mean per-floor |delta action| (mean over the 8 dims, floors 2-30)", 3),
    ]:
        names = ["trained (exported)", "seed 0", "seed 1", "seed 2"] + base_names
        names = [n for n in names if n in R[next(iter(PROFILES))]]
        rows = []
        for pname in PROFILES:
            rows.append([pname] + [ms(R[pname][n][metric], nd) for n in names])
        md.append(f"## {label}\n")
        md.append(table(["profile"] + names, rows) + "\n")

    # ---- paired significance for the exported policy vs each baseline
    md.append("## Trained (exported) vs baselines — paired comparison\n")
    rows = []
    wins = {b: {"reward": 0, "pace": 0, "both": 0} for b in base_names}
    for pname in PROFILES:
        t = R[pname]["trained (exported)"]
        for b in base_names:
            bs = R[pname][b]
            dr = t["reward"] - bs["reward"]
            dp = bs["pace"] - t["pace"]  # positive = trained better
            _, pr = stats.ttest_rel(t["reward"], bs["reward"])
            _, pp = stats.ttest_rel(t["pace"], bs["pace"])
            wr = dr.mean() > 0
            wp = dp.mean() > 0
            wins[b]["reward"] += wr
            wins[b]["pace"] += wp
            wins[b]["both"] += wr and wp
            rows.append(
                [
                    pname,
                    b,
                    f"{dr.mean():+.3f} (p={pr:.1e})",
                    f"{-dp.mean():+.3f} (p={pp:.1e})",
                    "yes" if (wr and wp) else "NO",
                ]
            )
    md.append(
        table(["profile", "baseline", "reward diff (trained - base)", "pacing-error diff", "trained better on both"], rows)
        + "\n"
    )  # fmt: skip
    md.append(
        "Profiles (of 6) on which the trained policy has the better mean on BOTH reward and "
        "pacing error: " + ", ".join(f"vs {b}: **{wins[b]['both']}/6**" for b in base_names) + "\n"
    )

    # ---- parameters chosen
    md.append("## Mean parameter value chosen per profile (trained, exported)\n")
    rows = []
    hdr = ["profile", "HP", "Dmg", "Speed", "Aggro", "Hazard", "Scarcity", "Rooms", "a7 (c)"]
    for pname in PROFILES:
        pr = R[pname]["trained (exported)"]["params"]
        a7 = R[pname]["trained (exported)"]["acts"][7]
        rows.append(
            [pname, f"{pr[0]:.1f}", f"{pr[1]:.1f}", f"{pr[2]:.0f}", f"{pr[3]:.0f}"]
            + [f"{pr[4]:.2f}", f"{pr[5]:.2f}", f"{pr[6]:.1f}", f"{a7:+.2f} ({(a7 + 1) / 2:.2f})"]
        )
    rngs = ["*range*"] + [f"*{lo:g}-{hi:g}*" for lo, hi in tpd.PARAM_RANGES.values()] + ["*-1..1*"]
    md.append(table(hdr, [rngs] + rows) + "\n")
    md.append(
        "Mean archetype mix produced by that a7 (crawler, pyromancer, brute, skirmisher, swarmer):\n"
    )
    rows = [[p] + [f"{x:.2f}" for x in R[p]["trained (exported)"]["mix"]] for p in PROFILES]
    md.append(
        table(["profile"] + [n.title().replace("_", " ") for n in tpd.ARCH_NAMES], rows) + "\n"
    )

    # ---- acceptance (a): normalised means
    norm_means = np.zeros((len(PROFILES), 8))
    for i, pname in enumerate(PROFILES):
        a = R[pname]["trained (exported)"]["acts"]  # mean action in [-1,1]
        norm_means[i] = (a + 1.0) / 2.0
    pinned = [
        bool(np.all(norm_means[:, j] <= 0.05) or np.all(norm_means[:, j] >= 0.95)) for j in range(8)
    ]
    md.append(
        "## Criterion (a): per-profile mean position inside each range (0 = min bound, 1 = max bound)\n"
    )
    rows = [
        [tpd.ACTION_NAMES[j]]
        + [f"{norm_means[i, j]:.2f}" for i in range(len(PROFILES))]
        + ["PINNED" if pinned[j] else "ok"]
        for j in range(8)
    ]
    md.append(table(["dim"] + list(PROFILES) + ["within 5% of a bound on all 6?"], rows) + "\n")

    # ---- sigma
    md.append("## Criterion (b): learned action standard deviation (exp(log_std))\n")
    rows = []
    sig = {}
    for k, m in models.items():
        s = np.exp(m.policy.log_std.detach().cpu().numpy())
        sig[k] = s
        rows.append([f"seed {k}"] + [f"{x:.2f}" for x in s] + [f"{s.max():.2f}"])
    md.append(table(["run"] + tpd.ACTION_NAMES + ["max"], rows) + "\n")

    # ---- spearman
    md.append("## Criterion (c): challenge chosen vs initial skill (trained, exported)\n")
    skills = list(PROFILES.values())
    sc = [R[p]["trained (exported)"]["score"].mean() for p in PROFILES]
    ch = [R[p]["trained (exported)"]["challenge"].mean() for p in PROFILES]
    rho_s = stats.spearmanr(skills, sc)[0]
    rho_c = stats.spearmanr(skills, ch)[0]
    rows = [[p, f"{a:.1f}", f"{b:.3f}"] for p, a, b in zip(PROFILES, sc, ch)]
    md.append(
        table(["profile", "game difficulty score (0-100)", "simulator load index"], rows) + "\n"
    )
    md.append(
        f"Spearman rho (initial skill vs mean difficulty score) = **{rho_s:.3f}**; vs simulator load index = **{rho_c:.3f}**.\n"
    )

    # ---- abrupt scenario
    md.append("## Abrupt-shift scenario\n")
    md.append(
        "Skill drops by 0.30 at level 10 (0-based; the first affected floor is floor 10) and "
        f"recovers (+0.30) at level 20; no random shifts; {N_EP} paired episodes.  The table "
        f"gives the number of floors from the shift (the shifted floor counts as 1) until the "
        f"cross-episode mean pacing error is <= {PACE_OK} on two consecutive floors "
        "(`never` = not within 10 floors).\n"
    )
    shifts = {10: -0.3, 20: +0.3}
    scen = {}
    curves = {}
    rows = []
    for s0 in [0.45, 0.70, 0.80]:
        cur = {}
        for name, fn in [
            ("trained (exported)", pol["trained (exported)"]),
            ("heuristic", heuristic_action),
            ("static +8%", "static"),
        ] + [("random-init (seed 1000)", model_fn(rand_models[0]))]:
            eps = evaluate(fn, s0, shifts)
            curve = np.mean([e["pace"] for e in eps], axis=0)
            dth = np.mean([e["deaths"] for e in eps], axis=0)
            cur[name] = (curve, dth)
            pre = curve[3:10].mean()
            r1 = recovery_floors(curve, 10)
            r2 = recovery_floors(curve, 20)
            rows.append(
                [
                    f"{s0:.2f} -> {s0 - 0.3:.2f} -> {s0:.2f}",
                    name,
                    f"{pre:.3f}",
                    f"{curve[10]:.3f}",
                    r1 if r1 is not None else "never",
                    f"{curve[20]:.3f}",
                    r2 if r2 is not None else "never",
                    f"{dth[10]:.2f}",
                ]
            )
        curves[s0] = cur
    md.append(
        table(["skill path", "policy", "mean err floors 3-9", "err on drop floor", "floors to recover after drop", "err on recovery floor", "floors to re-settle after recovery", "deaths on drop floor"], rows)
        + "\n"
    )  # fmt: skip
    scen = curves

    # ---- sim checks
    if not skip_checks:
        sc_mod = _load("sim_checks", "sim_checks.py")
        t, ok = sc_mod.monotonicity_table()
        md.append(
            "## Simulator check 1: every action dimension makes the floor harder (others at 0)\n"
        )
        md.append(t + f"\n\nAll dimensions monotone in the harder direction: **{ok}**\n")
        d, dom, _ = sc_mod.dominance_check()
        md.append("## Simulator check 2: no parameter is dominated\n")
        md.append(
            "For each dim, 16 random contexts (other dims ~ U(-0.7, 0.7)) x 6 skills: the grid value "
            "(9 points) that maximises the immediate per-floor reward (pacing + deaths + flow terms; "
            "smoothness excluded).  A dim is dominated if one bound is optimal in >95 % of contexts.\n"
        )
        md.append(d + f"\n\nAny dominated dimension: **{dom}**\n")

    # ---- criteria summary
    t_all = {p: R[p]["trained (exported)"] for p in PROFILES}
    dact_mean = float(np.mean([t_all[p]["dact"].mean() for p in PROFILES]))
    dact_max = float(np.max([t_all[p]["dact"].mean() for p in PROFILES]))
    sigma_best = sig.get(best, list(sig.values())[0])
    md.append("## Acceptance criteria (exported policy)\n")
    crit = [
        ("(a) no dim within 5% of a bound on all six profiles", not any(pinned), f"pinned dims: {[tpd.ACTION_NAMES[j] for j in range(8) if pinned[j]] or 'none'}; closest dim extremes in table above"),
        ("(b) learned sigma < 0.7 on all 8 dims", bool(sigma_best.max() < 0.7), f"max sigma = {sigma_best.max():.3f} (seed {best})"),
        ("(c) Spearman(skill, challenge) > 0.8", bool(rho_s > 0.8 and rho_c > 0.8), f"rho(score) = {rho_s:.3f}, rho(load) = {rho_c:.3f}"),
        ("(d) beats random-init, heuristic, static on reward AND pacing on >= 5/6 profiles", all(wins[b]["both"] >= 5 for b in base_names), ", ".join(f"{b}: {wins[b]['both']}/6" for b in base_names)),
        ("(e) mean per-floor |delta action| <= 0.35", dact_mean <= 0.35, f"mean over profiles = {dact_mean:.3f}, worst profile = {dact_max:.3f}"),
    ]  # fmt: skip
    md.append(
        table(
            ["criterion", "result", "number"],
            [[c, "PASS" if ok else "FAIL", n] for c, ok, n in crit],
        )
        + "\n"
    )
    md.append(
        "(f) pytest and ruff results, and the weights file size, are reported in the commit / PR description.\n"
    )

    with open(out_md, "w") as f:
        f.write("\n".join(md))
    print("wrote", out_md)

    # raw dump for the figure script
    dump = {
        "profiles": list(PROFILES),
        "metrics": {
            p: {n: {k: np.asarray(v).tolist() for k, v in s.items()} for n, s in R[p].items()}
            for p in PROFILES
        },
        "scenario": {
            str(s0): {n: {"pace": c[0].tolist(), "deaths": c[1].tolist()} for n, c in cur.items()}
            for s0, cur in scen.items()
        },
        "sigma": {str(k): v.tolist() for k, v in sig.items()},
    }
    json.dump(dump, open(os.path.join(HERE, "eval_results_sim_v2.json"), "w"))


if __name__ == "__main__":
    main()
