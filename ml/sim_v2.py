"""Stage 3: the NEW simulator ("sim-v4"): MLP1 player model + empirical Judge.

``DungeonDifficultyEnvV2`` keeps the frozen game contract of ``DungeonDifficultyEnv`` (sim-v3):

    observation (8): [norm_time, norm_deaths, norm_dmg, norm_enemy_hp, norm_enemy_dmg,
                      norm_hazard, norm_rooms, norm_level]
    action (8, [-1, 1]): [health, damage, speed, aggro, hazard, scarcity, room_count, complexity]

What changes is where the numbers come from:

* **Player outcome** of a floor = ``PlayerModel.sample_from_action(action, skill, history, rng)``
  (MLP1, stage 1) instead of the hand-written physics. Calibration / static / BSP floors whose
  settings fall outside the PPO action box go through the same model with explicit settings
  (``sample_settings``); ``sample_from_action`` is exactly ``sample_settings`` on the denormalised
  action (a test checks this).
* **Difficulty signal** = the Judge's prediction D_judge for these settings and this player (previous
  floor as context; stage 2). It replaces the hand-weighted ``difficulty_score`` as the difficulty
  estimate inside the loop. The old score is still computed and logged for comparison.
* **Latent player** (skill, reflex/tactics bias, drift, abrupt shifts, scripted shifts, the paired
  per-seed player stream) is reused unchanged from ``DungeonDifficultyEnv``.

Reward (weights in ``config["sim"]``; 0 switches a term off)::

    pace_w  * (1 - min(2, |t_room - 7.5| / 7.5))            # realised pace (MLP1 outcome)
    - death_w * deaths  - 0.3 [0 deaths and too fast]  - 0.4 [deaths >= 2]
    - flow_dmg_w * |dmg - 0.35|
    - judge_w * max(0, |D_judge - D_target(skill)| - judge_tol)   # NEW: empirical Judge
    - ood_w * (share of settings outside the Judge's training range)  # NEW: anti-exploit
    - room_w, complex_w, sev_w, cover_w   (sim-v3 hidden-skill priors, unchanged definitions)
    - balance_w * mean(a^2) - smooth_w * mean|a_t - a_{t-1}|

D_target = judge_target + judge_target_skill_slope * (skill - 0.5). The default 0.27 is the
measured difficulty of an "ideal" floor under the Judge's own target definition: on pace
(0.25 * 0.5), no deaths, 35 % damage (0.40 * 0.35).

The realised measured difficulty D_real (same formula, computed from the MLP1 outcome) is logged next
to D_judge; the PPO stage uses the gap |D_judge - D_real| to detect a policy that exploits the Judge.
"""

from __future__ import annotations

import functools
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from . import player_data as D
from .config import DEFAULTS
from .judge_bridge import JudgeScorer, measured_difficulty
from .player_data import sim
from .player_model import PlayerModel, _finish_sample, _pad_history, analytic_base, build_features

SIM_VERSION = "sim-v4-mlp1-judge"


@functools.lru_cache(maxsize=8)
def _load_player_model(path: str) -> PlayerModel:
    return PlayerModel.load(path)


@functools.lru_cache(maxsize=8)
def _load_judge(path: str) -> JudgeScorer:
    return JudgeScorer(path)


def sample_outcome(pm: PlayerModel, y, mix, count_scale: float, skill: float, history, rng):
    """ONE MLP1 outcome x = (norm_time, norm_deaths, norm_dmg) for explicit settings y (8,).

    Shared by the simulator and the MLP1 Judge corpus (ml/judge_corpus.py): pick a random ensemble
    member, draw from its Gaussian, clip to the observation range, snap deaths to k/3."""
    y = np.asarray(y, dtype=np.float64)
    base = analytic_base(y, skill, np.asarray(mix, dtype=np.float64), count_scale)[None]
    hist = _pad_history(history)[None]
    mm, ss = pm._member_outputs(build_features(y[None], [skill], base, hist), base)
    m = int(rng.integers(0, len(pm.members)))
    x = mm[m, 0] + ss[m, 0] * rng.standard_normal(D.X_DIM)
    return _finish_sample(x[None], True)[0]


# Enemy-count rule of PPO floors (DifficultyManager.adaptive_count_scale; keep the two identical).
COUNT_SCALE_START, COUNT_SCALE_FULL, COUNT_SCALE_MAX = 40.0, 70.0, 1.3


def adaptive_count_scale(score: float) -> float:
    t = (score - COUNT_SCALE_START) / (COUNT_SCALE_FULL - COUNT_SCALE_START)
    t = float(np.clip(t, 0.0, 1.0))
    return 1.0 + (COUNT_SCALE_MAX - 1.0) * t


def params_from_action(action) -> tuple[dict, float]:
    a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
    p = {k: float(sim.denorm(a[i], k)) for i, k in enumerate(sim.PARAM_ORDER)}
    p["room_count"] = float(round(p["room_count"]))
    return p, float(a[7])


class DungeonDifficultyEnvV2(gym.Env):
    """sim-v4: same 8-D/8-D contract as sim-v3; MLP1 outcomes; Judge difficulty in the reward."""

    metadata = {"render_modes": []}

    def __init__(self, player_model, judge, sim_cfg: dict | None = None):
        super().__init__()
        self.pm = (
            _load_player_model(str(player_model))
            if isinstance(player_model, (str, Path))
            else player_model
        )
        self.judge = _load_judge(str(judge)) if isinstance(judge, (str, Path)) else judge
        self.cfg = {**DEFAULTS["sim"], **(sim_cfg or {})}
        self.max_levels = int(self.cfg["max_levels"])
        self.observation_space = spaces.Box(0.0, 1.0, shape=(sim.OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(sim.ACT_DIM,), dtype=np.float32)
        # the latent player (skill / bias / drift / shifts) lives in an sim-v3 env we never step
        self.player = sim.DungeonDifficultyEnv()
        self.rng = np.random.default_rng()
        self.reset()

    # ---------------------------------------------------------------- reset / cold start
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.player.reset(seed=seed, options=options)
        self.rng = np.random.default_rng(None if seed is None else [int(seed), 4243])
        self.level = 0
        self.hist: list[np.ndarray] = []
        self.prev_action = None
        self.prev_floor = None
        c5 = sim.CAL_LEVELS[-1]
        self.params = self._cal_params(c5)
        self.last_time, self.last_deaths, self.last_dmg = self._calibrate()
        return self._get_obs(), {}

    @staticmethod
    def _cal_params(cal: dict) -> dict:
        return dict(
            enemy_health=float(cal["hp"]), enemy_damage=float(cal["dmg"]),
            enemy_speed=float(cal["spd"]), enemy_aggro=float(cal["agr"]),
            hazard_density=float(cal["haz"]), resource_scarcity=float(cal["scar"]),
            room_count=float(cal["rooms"]),
        )  # fmt: skip

    def _calibrate(self):
        """5 calibration floors through MLP1 (same summary as sim-v3: mean time / deaths / dmg)."""
        ts, ds, rs = [], [], []
        skill = self.player.skill
        for cal in sim.CAL_LEVELS:
            p = self._cal_params(cal)
            mix = np.asarray(cal["mix"], dtype=np.float64)
            x = self.sample_settings(p, mix, float(cal["cs"]), skill)
            t, d, r = self._unpack(x)
            ts.append(t)
            ds.append(d)
            rs.append(r)
            self._remember(x, p, t, d, r)
        return float(np.mean(ts)), int(round(np.mean(ds))), float(np.mean(rs))

    # ---------------------------------------------------------------- player model
    def sample_settings(self, params: dict, mix, count_scale: float, skill: float, complexity=None):
        """MLP1 outcome for explicit settings (used for floors outside the PPO action box).

        complexity c defaults to the mix-weighted archetype level (what calibration floors log)."""
        c = float(np.asarray(mix) @ sim.ARCH_LEVELS) if complexity is None else float(complexity)
        y = D.params_to_y([params[k] for k in sim.PARAM_ORDER], c)
        return self._sample_y(y, np.asarray(mix, dtype=np.float64), count_scale, skill)

    def _sample_y(self, y, mix, count_scale, skill):
        return sample_outcome(self.pm, y, mix, count_scale, skill, self._hist_arr(), self.rng)

    def _hist_arr(self):
        return None if not self.hist else np.stack(self.hist[-D.HISTORY_LEN :])

    @staticmethod
    def _unpack(x):
        """MLP1 observation -> (time s, deaths, damage fraction)."""
        return (
            float(x[0]) * D.TIME_NORM_S,
            int(round(float(x[1]) * D.DEATH_NORM)),
            float(x[2]),
        )

    def _remember(self, x, params, t, d, r):
        self.hist.append(np.asarray(x, dtype=np.float32))
        self.prev_floor = dict(
            time=t, deaths=d, dmg_frac=r, rooms=params["room_count"], params=dict(params)
        )

    # ---------------------------------------------------------------- observation
    def _get_obs(self):
        p = self.params
        return np.array(
            [
                np.clip(self.last_time / D.TIME_NORM_S, 0, 1),
                np.clip(self.last_deaths / D.DEATH_NORM, 0, 1),
                np.clip(self.last_dmg, 0, 1),
                sim.norm(p["enemy_health"], "enemy_health"),
                sim.norm(p["enemy_damage"], "enemy_damage"),
                sim.norm(p["hazard_density"], "hazard_density"),
                sim.norm(p["room_count"], "room_count"),
                np.clip((5 + max(self.level, 1)) / 10.0, 0, 1),
            ],
            dtype=np.float32,
        )

    # ---------------------------------------------------------------- reward
    def target_difficulty(self, skill: float) -> float:
        c = self.cfg
        return float(
            np.clip(c["judge_target"] + c["judge_target_skill_slope"] * (skill - 0.5), 0, 1)
        )

    def judge_compare(self, d_judge: float) -> float:
        """The Judge value the reward compares with the target (measured scale, or rating scale)."""
        c = self.cfg
        if c.get("judge_scale", "measured") == "rating":
            return float(np.clip(c["judge_rating_a"] * d_judge + c["judge_rating_b"], 0.0, 1.0))
        return float(d_judge)

    def reward(self, out: dict, action_vec, prev_action) -> tuple[float, dict]:
        c = self.cfg
        rooms = max(1.0, out["rooms"])
        deaths = out["deaths"]
        tpr = out["time"] / rooms
        time_err = min(sim.TIME_ERR_CAP, abs(tpr - sim.TARGET_TPR) / sim.TARGET_TPR)
        parts = {}
        parts["pace"] = c["pace_w"] * (1.0 - time_err)
        parts["deaths"] = -c["death_w"] * deaths
        parts["deaths"] -= 0.3 if (deaths == 0 and tpr < sim.TARGET_TPR * 0.5) else 0.0
        parts["deaths"] -= 0.4 if deaths >= 2 else 0.0
        parts["flow"] = -c["flow_dmg_w"] * abs(out["dmg_ratio"] - sim.FLOW_DMG_TARGET)
        # judge_scale "rating": the Judge's output mapped onto the players' own 1-5 ratings
        # (scaled to 0..1) by a linear fit on the recorded rated floors; the target is then a rating.
        judge_err = abs(self.judge_compare(out["judge"]) - out["target"])
        parts["judge"] = -c["judge_w"] * max(0.0, judge_err - c["judge_tol"])
        parts["ood"] = -c["ood_w"] * out["ood"]
        parts["rooms"] = -c["room_w"] * abs(rooms - (5.0 + 4.0 * out["skill"])) / 4.0
        parts["complexity"] = -c["complex_w"] * abs(out["c"] - out["skill"])
        sev_t = sim.SEV_LO + (sim.SEV_HI - sim.SEV_LO) * out["reflex"]
        parts["sev"] = -c["sev_w"] * abs(out["sev"] - sev_t) / 0.30
        cov_t = sim.COVER_LO + (sim.COVER_HI - sim.COVER_LO) * (1.0 - out["tactics"])
        parts["cover"] = -c["cover_w"] * abs(np.log(max(out["cover"], 1e-3) / cov_t))
        parts["balance"] = -c["balance_w"] * float(np.mean(np.square(action_vec)))
        smooth = 0.0 if prev_action is None else float(np.mean(np.abs(action_vec - prev_action)))
        parts["smooth"] = -c["smooth_w"] * smooth
        total = float(sum(parts.values()))
        return total, dict(parts=parts, pace_err=time_err, smooth=smooth, judge_err=judge_err)

    # ---------------------------------------------------------------- step
    def step(self, action):
        a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        params, a7 = params_from_action(a)
        skill = self.player.skill
        if self.cfg.get("adaptive_count_scale", False):
            # the game scales the enemy count of PPO floors with their score (DifficultyManager)
            cs = adaptive_count_scale(sim.difficulty_score(params))
            mix = sim.archetype_mix(a7)
            x = self.sample_settings(params, mix, cs, skill, (a7 + 1.0) / 2.0)
            return self._play(params, mix, (a7 + 1.0) / 2.0, cs, x, a)
        x = self.pm.sample_from_action(a, skill, self._hist_arr(), self.rng)
        return self._play(params, sim.archetype_mix(a7), (a7 + 1.0) / 2.0, 1.0, x, a)

    def step_params(self, params: dict, a7: float, count_scale: float = 1.0):
        """Play a floor with explicit settings (static +8 %, BSP baseline). Not clipped to the box."""
        params = dict(params)
        params["room_count"] = float(round(params["room_count"]))
        mix = sim.archetype_mix(a7)
        x = self.sample_settings(params, mix, count_scale, self.player.skill, (a7 + 1.0) / 2.0)
        vec = np.append(sim.to_action(params), a7)
        return self._play(params, mix, (a7 + 1.0) / 2.0, count_scale, x, vec)

    def _play(self, params, mix, c, count_scale, x, action_vec):
        rho, tau = self.player._axes()
        skill = self.player.skill
        t, d, r = self._unpack(x)
        feats = self.judge.features(params, mix, count_scale, self.prev_floor, complexity=c)
        d_judge = float(self.judge.predict(feats)[0])
        heal_use = sim.HEAL_USE_BASE + sim.HEAL_USE_GAIN * tau
        supply = sim.DungeonDifficultyEnv.expected_pickups(params) * sim.HEAL_PER_PICKUP * heal_use
        out = dict(
            time=t, deaths=d, dmg_ratio=r, rooms=params["room_count"], c=c, skill=skill,
            reflex=rho, tactics=tau, judge=d_judge, target=self.target_difficulty(skill),
            judge_cmp=self.judge_compare(d_judge),
            measured=measured_difficulty(t, d, r, params["room_count"]),
            ood=self.judge.ood_fraction(feats),
            sev=float(params["enemy_damage"] * (np.asarray(mix) @ sim.DMG_MULT) / sim.PLAYER_HP),
            cover=float(supply / max(r, 0.20)),
            proxy=sim.difficulty_score(params) / 100.0,
        )  # fmt: skip
        reward, extra = self.reward(out, np.asarray(action_vec, dtype=np.float64), self.prev_action)
        # advance state
        self.params = dict(params)
        self.last_time, self.last_deaths, self.last_dmg = t, d, r
        self._remember(x, params, t, d, r)
        self.prev_action = np.asarray(action_vec, dtype=np.float64)
        self.level += 1
        self.player.level = self.level
        self.player._advance_skill()
        terminated = self.level >= self.max_levels
        info = dict(out, mix=mix, params=dict(params), **extra)
        return self._get_obs(), float(reward), terminated, False, info


class TrainWrapperV2(sim.TrainWrapper):
    """Same wide-box trick as sim-v3's TrainWrapper (works on any env with the 8-D action)."""


def _make_env(pm: str, jd: str, sim_cfg: dict):
    import torch

    torch.set_num_threads(1)  # one simulator per process: avoid oversubscribing the CPU
    return DungeonDifficultyEnvV2(pm, jd, sim_cfg)


def make_env_factory(player_model_path, judge_path, sim_cfg):
    """Picklable env factory (works with SubprocVecEnv on Windows' spawn start method too)."""
    return functools.partial(_make_env, str(player_model_path), str(judge_path), dict(sim_cfg))


# ------------------------------------------------------------------------------------------------
# Policies used by the sanity checks / baselines (all map obs -> 8-D action)
# ------------------------------------------------------------------------------------------------
def json_policy_fn(path):
    """NumPy mirror of PPOPolicy.gd (tanh hidden layers, linear output clipped to [-1, 1])."""
    import json

    layers = json.loads(Path(path).read_text(encoding="utf-8"))["layers"]
    W = [np.array(layer["w"], dtype=np.float64) for layer in layers]
    B = [np.array(layer["b"], dtype=np.float64) for layer in layers]

    def f(obs):
        x = np.asarray(obs, dtype=np.float64).T
        for i, (w, b) in enumerate(zip(W, B)):
            x = w @ x + (b[:, None] if x.ndim == 2 else b)
            if i < len(W) - 1:
                x = np.tanh(x)
        return np.clip(x.T, -1.0, 1.0)

    return f


def run_episode(env, policy, seed, options=None, record=True):
    """policy: callable obs -> action, or ('static',) / ('params', fn(floor)->(params, a7))."""
    obs, _ = env.reset(seed=seed, options=options)
    rows = []
    done = False
    floor = 0
    while not done:
        floor += 1
        if callable(policy):
            obs, r, done, _, info = env.step(policy(obs))
        else:
            params, a7 = policy[1](floor)
            obs, r, done, _, info = env.step_params(params, a7)
        if record:
            rows.append(
                dict(reward=r, obs=obs.copy(), **{k: v for k, v in info.items() if k != "parts"})
            )
    return rows


def static_schedule(floor):
    f = 1.0 + sim.STATIC_STEP * max(floor - 1, 0)
    p = dict(sim.INTERMEDIATE)
    p["enemy_health"] *= f
    p["enemy_damage"] *= f
    return p, sim.STATIC_A7


def summarize(rows_list) -> dict:
    keys = [
        "reward",
        "pace_err",
        "deaths",
        "dmg_ratio",
        "judge",
        "measured",
        "target",
        "ood",
        "proxy",
    ]
    out = {}
    for k in keys:
        vals = np.array([np.mean([r[k] for r in rows]) for rows in rows_list], dtype=float)
        out[k] = float(vals.mean())
    out["judge_gap"] = float(
        np.mean([np.mean([abs(r["judge"] - r["measured"]) for r in rows]) for rows in rows_list])
    )
    out["fit_err"] = float(
        np.mean([np.mean([abs(r["measured"] - r["target"]) for r in rows]) for rows in rows_list])
    )
    out["n_episodes"] = len(rows_list)
    return out


def sanity_report(env: DungeonDifficultyEnvV2, policies: dict, episodes: int, seed0: int = 20_000):
    """Checks that the new simulator responds sensibly, and scores a few reference policies."""
    rep: dict = {"sim_version": SIM_VERSION}
    # 1) response sweeps: harder settings -> more damage / higher Judge difficulty; skill -> less
    sweeps = {}
    mid = np.zeros(sim.ACT_DIM)
    for dim, name in [(1, "enemy_damage"), (0, "enemy_health"), (4, "hazard_density")]:
        grid = np.linspace(-1, 1, 5)
        dmg, jd = [], []
        for v in grid:
            a = mid.copy()
            a[dim] = v
            mean, _ = env.pm.predict_from_action(a, 0.5, None)
            p, a7 = params_from_action(a)
            feats = env.judge.features(p, sim.archetype_mix(a7), 1.0, None, complexity=(a7 + 1) / 2)
            dmg.append(float(mean[2]))
            jd.append(float(env.judge.predict(feats)[0]))
        sweeps[name] = dict(
            grid=grid.tolist(), mlp1_dmg=dmg, judge=jd,
            dmg_increasing=bool(dmg[-1] > dmg[0]), judge_increasing=bool(jd[-1] > jd[0]),
        )  # fmt: skip
    skills = [0.1, 0.5, 0.9]
    by_skill = [float(env.pm.predict_from_action(mid, s, None)[0][2]) for s in skills]
    sweeps["skill"] = dict(
        grid=skills, mlp1_dmg=by_skill, dmg_decreasing=bool(by_skill[-1] < by_skill[0])
    )
    rep["sweeps"] = sweeps
    # 2) reference policies
    rep["policies"] = {}
    for name, pol in policies.items():
        eps = [run_episode(env, pol, seed0 + i) for i in range(episodes)]
        rep["policies"][name] = summarize(eps)
    rep["checks"] = {
        "damage_rises_with_enemy_damage": sweeps["enemy_damage"]["dmg_increasing"],
        "judge_rises_with_enemy_damage": sweeps["enemy_damage"]["judge_increasing"],
        "damage_falls_with_skill": sweeps["skill"]["dmg_decreasing"],
        "finite_rewards": all(np.isfinite(v["reward"]) for v in rep["policies"].values()),
    }
    return rep
