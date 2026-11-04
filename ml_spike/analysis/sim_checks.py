"""Sanity checks of the sim-v2 simulator: monotonicity of every action dimension and an
explicit "is any parameter dominated?" test.  Imported by evaluate_policies.py."""

import importlib.util
import os

import numpy as np

spec = importlib.util.spec_from_file_location(
    "tpd",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../train_ppo_difficulty.py"),
)
tpd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpd)

GRID = np.linspace(-1.0, 1.0, 9)


def level_outcome(action, skill, seed, bias=0.0):
    """One simulated floor for a fixed action; common random numbers via `seed`."""
    env = tpd.DungeonDifficultyEnv()
    env.reset(seed=seed, options={"skill": skill, "random_shifts": False})
    env.bias = bias
    env.rng = np.random.default_rng(seed + 1_000_003)
    a = np.clip(np.asarray(action, dtype=np.float64), -1, 1)
    params = {k: float(tpd.denorm(a[i], k)) for i, k in enumerate(tpd.PARAM_ORDER)}
    params["room_count"] = float(round(params["room_count"]))
    res = env._simulate(params, tpd.archetype_mix(a[7]))
    res["c"] = (a[7] + 1.0) / 2.0
    reward, _ = env.reward_fn(res, a, None)
    return res, reward


def sweep(dim, skill, base=None, n=60):
    """Mean outcome of each grid value of one action dim (others at `base`, default 0)."""
    base = np.zeros(8) if base is None else np.asarray(base, dtype=np.float64)
    rows = []
    for v in GRID:
        a = base.copy()
        a[dim] = v
        outs = [level_outcome(a, skill, s) for s in range(n)]
        rows.append(
            (
                float(np.mean([o[0]["time"] / o[0]["rooms"] for o in outs])),
                float(np.mean([o[0]["gross"] for o in outs])),
                float(np.mean([o[0]["deaths"] for o in outs])),
                float(np.mean([o[1] for o in outs])),
            )
        )
    return np.array(rows)  # [grid, (t_room, gross, deaths, reward)]


def monotonicity_table(skills=(0.2, 0.5, 0.8), n=80):
    """Effect of moving each dim from -1 to +1 (others 0): delta time/room, gross damage, deaths."""
    lines = ["| action dim | skill | t/room @-1 | t/room @+1 | gross dmg @-1 | gross dmg @+1 | deaths @-1 | deaths @+1 | direction ok |",
             "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    ok_all = True
    for i, name in enumerate(tpd.ACTION_NAMES):
        for s in skills:
            r = sweep(i, s, n=n)
            lo, hi = r[0], r[-1]
            harder = (
                (hi[0] >= lo[0] - 0.05) and (hi[1] >= lo[1] - 0.005) and (hi[2] >= lo[2] - 0.01)
            )
            strictly = (hi[0] > lo[0] + 0.05) or (hi[1] > lo[1] + 0.01)
            ok = bool(harder and strictly)
            ok_all &= ok
            lines.append(
                f"| {name} | {s} | {lo[0]:.2f} | {hi[0]:.2f} | {lo[1]:.3f} | {hi[1]:.3f} "
                f"| {lo[2]:.2f} | {hi[2]:.2f} | {'yes' if ok else 'NO'} |"
            )
    return "\n".join(lines), ok_all


def dominance_check(skills=(0.10, 0.20, 0.45, 0.70, 0.80, 0.90), n_ctx=16, n=24, seed=0):
    """For every dim: in many random contexts (other dims ~ U(-0.7, 0.7)) find the
    reward-maximising grid value.  A dim is DOMINATED if the same bound is optimal in
    (nearly) every context of every profile.  Also reports how the optimum moves with skill."""
    rng = np.random.default_rng(seed)
    ctx = rng.uniform(-0.7, 0.7, size=(n_ctx, 8))
    res = {}
    for i, name in enumerate(tpd.ACTION_NAMES):
        best = np.zeros((len(skills), n_ctx))
        for si, s in enumerate(skills):
            for ci in range(n_ctx):
                rew = []
                for v in GRID:
                    a = ctx[ci].copy()
                    a[i] = v
                    rew.append(np.mean([level_outcome(a, s, k)[1] for k in range(n)]))
                best[si, ci] = GRID[int(np.argmax(rew))]
        res[name] = best
    lines = [
        "| action dim | % contexts optimum at -1 | % at +1 | % interior | mean optimum @skill 0.10 | @0.45 | @0.90 | dominated? |",
        "|---|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    any_dom = False
    for name, best in res.items():
        lo = float(np.mean(best <= -0.99)) * 100
        hi = float(np.mean(best >= 0.99)) * 100
        mid = 100 - lo - hi
        dom = lo > 95 or hi > 95
        any_dom |= dom
        m = best.mean(axis=1)
        lines.append(
            f"| {name} | {lo:.0f} | {hi:.0f} | {mid:.0f} | {m[0]:+.2f} | {m[2]:+.2f} | {m[5]:+.2f} | {'YES' if dom else 'no'} |"
        )
    return "\n".join(lines), any_dom, res


if __name__ == "__main__":
    t, ok = monotonicity_table()
    print(t, ok)
    d, dom, _ = dominance_check()
    print(d, dom)
