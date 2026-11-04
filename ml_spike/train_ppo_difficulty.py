"""
FORGE — Adaptive Difficulty PPO Trainer (simulator v2, "sim-v2")
-----------------------------------------------------------------
Trains a PPO agent whose job is: given how the player just performed
(completion time, deaths, damage taken) and the current difficulty
parameters, output the NEXT dungeon's parameters — escalating when the
player is clearing levels quickly and cleanly, easing off when they are
slow or dying a lot.

We cannot have a real human play thousands of floors, so we train against a
*simulated player*. Simulator v2 (this file) fixes the artefacts of v1
(damage pinned at its minimum, speed at its maximum, aggro / scarcity having
no effect, no enemy-count or archetype model, a narrow player population and
no abrupt performance changes). Everything below the "SIMULATOR CONSTANTS"
banner is documented where it is defined; the evaluation report
(ml_spike/analysis/results_sim_v2.md) lists the constants in one table.

Interface (shared contract, unchanged by this file's internals):
    observation (8) : [norm_time, norm_deaths, norm_dmg_ratio, norm_enemy_hp,
                       norm_enemy_dmg, norm_hazard, norm_rooms, norm_level]
    action      (8) : [enemy_health, enemy_damage, enemy_speed, enemy_aggro,
                       hazard_density, resource_scarcity, room_count,
                       archetype_complexity]   each in [-1, 1]

Install once:
    pip install stable-baselines3 gymnasium torch

Run (single seed, writes the SB3 zip and the Godot JSON):
    python train_ppo_difficulty.py --seed 0 --timesteps 600000
"""

import argparse
import json

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from stable_baselines3 import PPO

# ---------------------------------------------------------------------------
# Must match DifficultyManager.gd's PARAM_RANGES / build_observation exactly.
# ---------------------------------------------------------------------------
PARAM_RANGES = {
    "enemy_health": (20.0, 120.0),
    "enemy_damage": (5.0, 50.0),
    "enemy_speed": (60.0, 220.0),
    "enemy_aggro": (100.0, 450.0),
    "hazard_density": (0.05, 0.80),
    "resource_scarcity": (0.10, 0.90),
    "room_count": (5.0, 9.0),
}
PARAM_ORDER = [
    "enemy_health",
    "enemy_damage",
    "enemy_speed",
    "enemy_aggro",
    "hazard_density",
    "resource_scarcity",
    "room_count",
]
ACTION_NAMES = PARAM_ORDER + ["archetype_complexity"]
ACT_DIM = 8
OBS_DIM = 8

TARGET_TIME = 45.0  # seconds — the pace we want a "well-matched" 6-room level to take
TARGET_TPR = TARGET_TIME / 6.0  # 7.5 s per room
MAX_LEVELS = 30  # simulated levels per training episode


def denorm(value, key):
    lo, hi = PARAM_RANGES[key]
    t = (np.clip(value, -1.0, 1.0) + 1.0) / 2.0
    return lo + t * (hi - lo)


def norm(value, key):
    lo, hi = PARAM_RANGES[key]
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


def norm_raw(value, key):
    """Normalisation WITHOUT clipping (used by the physics so that the static
    baseline, whose health/damage grow past the PPO range, is simulated honestly)."""
    lo, hi = PARAM_RANGES[key]
    return (value - lo) / (hi - lo)


def to_action(params):
    """Inverse of denorm for a params dict (unclipped); used for |delta action|."""
    out = []
    for key in PARAM_ORDER:
        out.append(2.0 * norm_raw(params[key], key) - 1.0)
    return np.array(out, dtype=np.float64)


# ---------------------------------------------------------------------------
# Archetype mix (contract section 3) — MUST be identical to the GDScript version.
# ---------------------------------------------------------------------------
ARCH_NAMES = ["MELEE_CRAWLER", "RANGED_PYROMANCER", "HEAVY_BRUTE", "AGILE_SKIRMISHER", "SWARMER"]
ARCH_LEVELS = np.array([0.00, 0.50, 0.90, 0.70, 0.25])


def archetype_mix(a7):
    """p = 0.85 * softmax(-|LEVELS - c| / 0.25) + 0.15 / 5, c = (clamp(a7) + 1) / 2."""
    c = (float(np.clip(a7, -1.0, 1.0)) + 1.0) / 2.0
    logit = -np.abs(ARCH_LEVELS - c) / 0.25
    e = np.exp(logit - logit.max())
    return 0.85 * e / e.sum() + 0.15 / 5.0


def legacy_a7_from_score(score):
    """Legacy 7-dim action rule: c = difficulty_score / 100  ->  a7 = 2*score/100 - 1."""
    return 2.0 * float(score) / 100.0 - 1.0


def difficulty_score(params):
    """Port of DifficultyManager.calculate_difficulty_score() (integer 0-100)."""

    def cl(x):
        return min(max(x, 0.0), 1.0)

    n_hp = cl((params["enemy_health"] - 20.0) / 100.0)
    n_dmg = cl((params["enemy_damage"] - 5.0) / 45.0)
    n_spd = cl((params["enemy_speed"] - 60.0) / 160.0)
    n_agr = cl((params["enemy_aggro"] - 100.0) / 350.0)
    n_haz = cl((params["hazard_density"] - 0.05) / 0.75)
    n_scar = cl((params["resource_scarcity"] - 0.10) / 0.80)
    raw = n_dmg * 0.28 + n_hp * 0.22 + n_spd * 0.18 + n_agr * 0.14 + n_haz * 0.10 + n_scar * 0.08
    return int(np.floor(raw * 100.0 + 0.5))


# ===========================================================================
# SIMULATOR CONSTANTS (sim-v2).  All "per-archetype" arrays follow the
# Enemy.Archetype enum order: crawler, pyromancer, brute, skirmisher, swarmer.
# ===========================================================================
# -- physical stat multipliers (contract section 1) --------------------------
HP_MULT = np.array([1.00, 0.75, 2.00, 0.80, 0.35])
DMG_MULT = np.array([1.00, 0.90, 1.40, 0.80, 0.45])
SPD_MULT = np.array([1.00, 0.92, 0.55, 1.30, 1.15])
AGR_MULT = np.array([1.00, 1.00, 0.80, 1.20, 1.00])
AGR_FLOOR = np.array([0.0, 420.0, 0.0, 0.0, 0.0])  # pyromancer: max(aggro, 420)
BODIES = np.array([1.0, 1.0, 1.0, 1.0, 3.0])  # a SWARMER slot spawns 3 bodies
# Reach factor: ranged / evasive archetypes take longer to pin down and hit back meanwhile.
REACH = np.array([1.00, 1.35, 1.00, 1.25, 1.10])
SLOT_HP = HP_MULT * BODIES * REACH  # effective time-to-kill weight of one spawn slot (x PPO hp)
# Damage exposure of one slot = (kill time) x (damage rate) = hp_slot x dmg_slot, x0.6
# for the swarmer because its 3 bodies die one after another (rate decays while killing).
EXPOSURE = np.array([1.0, 0.675, 2.80, 0.64, 0.85]) * REACH
# -- threat weights: how hard each archetype is to AVOID, per skill axis ------
#    reflex axis = dodging / positioning;  tactics axis = target priority / crowd control
THREAT_REFLEX = np.array([0.85, 1.15, 0.95, 1.45, 0.90])
THREAT_TACTICS = np.array([0.80, 1.00, 1.55, 1.20, 1.00])
THREAT_REFLEX_REF = 1.05  # normalisation so that the c=0.45 (static) mix is ~1
THREAT_TACTICS_REF = 1.10
# -- skill sensitivity: how much more a LOW-skill player suffers (0.4 + 1.1*level) --
SENSITIVITY = 0.40 + 1.10 * ARCH_LEVELS
SENS_REF = 0.95
SENS_PEN = 0.75  # extra gap = SENS_PEN * (K_mix - SENS_REF) * (1 - skill)^2
# -- diminishing-returns exponents on the normalised loads -------------------
EXP_SPEED, EXP_AGGRO, EXP_HAZARD, EXP_DMG = 0.70, 0.70, 0.80, 1.0
# -- load weights per skill axis ---------------------------------------------
W_R = (0.45, 0.30, 0.25)  # reflex load  : speed, hazard, aggro
W_T = (0.38, 0.27, 0.35)  # tactics load : health, enemy count, aggro
GAP_SLOPE = 5.2  # hit-probability sigmoid steepness
GAP_R_W, GAP_T_W = 0.55, 0.45  # weight of each axis in the hit probability
LOAD_OFFSET = 0.00  # centring of load vs skill (calibration constant)
SKILL_GAIN_R = 1.00  # load a skill point cancels on each axis
SKILL_GAIN_T = 1.00
MU_MIN, MU_MAX = 0.03, 0.97
FATIGUE = 0.035  # hit probability grows 3.5 % per room already fought on the floor
SIM_AGGRO = 0.90  # simultaneous-engagement multiplier at max aggro and a full room
# -- time model (seconds) ----------------------------------------------------
T_TRAVERSE = 1.5  # per room, walking / doors
T_KILL = 0.92  # seconds to kill one 60-hp crawler slot at tactics 0.5
T_EVADE = 0.50  # seconds of dodging per slot at reference speed 130
T_STAGGER = 0.70  # seconds lost per slot x hit-probability (knock-back, re-engaging)
T_HAZARD = 0.45  # seconds per hazard tile in a room
CAUTION_DMG, CAUTION_SCAR = 0.30, 0.18  # players slow down when hits hurt / healing is rare
RESPAWN_S = 6.0  # seconds added per death (counted in completion_time)
TIME_NOISE_ROOM = 0.14  # lognormal sigma per room
TIME_NOISE_LEVEL = 0.05  # lognormal sigma per level
# -- damage model (fractions of player max health) ---------------------------
DMG_K = 0.0105  # enemy damage per slot-exposure at reference damage 27.5 / hp 60
HAZ_DMG = 0.009  # per hazard tile at reflex 0
HEAL_PER_PICKUP = 0.18
HEAL_USE = 0.85  # fraction of available healing that is actually usable
DMG_NOISE_LEVEL = 0.22  # lognormal sigma of the whole level's damage
# -- player population -------------------------------------------------------
SKILL_INIT = (0.05, 0.95)
REFLEX_BIAS = 0.12  # reflex = skill + b, tactics = skill - b with b ~ U(-0.12, 0.12)
DRIFT_MEAN, DRIFT_STD = 0.004, 0.007  # gradual per-level learning drift
SHIFT_PROB = 0.05  # per level probability of an abrupt shift
SHIFT_MAG = (0.15, 0.30)
SHIFT_TRANSIENT_P = 0.5  # half of the shifts are a "tilt/break" that reverts after 3-6 floors
# -- reward ------------------------------------------------------------------
SMOOTH_LAMBDA = 0.25  # weight of mean |a_t - a_{t-1}| (over the 8 dims)
FLOW_DMG_TARGET = 0.35  # desirable damage-taken ratio (player is engaged but not crushed)
FLOW_DMG_W = 0.45
BALANCE_W = 0.15  # "balanced difficulty": penalty on mean(a^2) so that challenge is spread over
# several levers instead of one cheap extreme (sponge enemies / paper-thin enemies, spike
# hazards); keeps every dimension inside its range unless pushing it clearly pays off.
COMPLEX_W = 0.20  # archetype complexity should track proficiency: target c = skill
ROOM_W = 0.30  # floors should be longer for stronger players: target rooms = 5 + 4 * skill
OOB_LAMBDA = (
    1.5  # training only: quadratic penalty on sampled actions outside [-1, 1] (TrainWrapper)
)
TIME_ERR_CAP = 2.0

# Cold-start calibration floors (DifficultyManager.CALIBRATION_LEVELS + contract mixes).
CAL_LEVELS = [
    dict(hp=35, dmg=10, spd=85, agr=160, haz=0.05, scar=0.15, rooms=3, cs=0.7, mix=[0.70, 0, 0, 0, 0.30]),
    dict(hp=45, dmg=14, spd=110, agr=200, haz=0.15, scar=0.25, rooms=4, cs=0.9, mix=[0.50, 0, 0, 0, 0.50]),
    dict(hp=55, dmg=18, spd=135, agr=240, haz=0.38, scar=0.35, rooms=4, cs=1.0, mix=[0, 0.75, 0, 0.25, 0]),
    dict(hp=70, dmg=24, spd=155, agr=290, haz=0.50, scar=0.55, rooms=5, cs=1.15, mix=[0.25, 0.25, 0, 0.30, 0.20]),
    dict(hp=90, dmg=30, spd=175, agr=350, haz=0.65, scar=0.70, rooms=5, cs=1.3, mix=[0.15, 0.25, 0.30, 0.20, 0.10]),
]  # fmt: skip
INTERMEDIATE = dict(
    enemy_health=60.0,
    enemy_damage=20.0,
    enemy_speed=130.0,
    enemy_aggro=250.0,
    hazard_density=0.35,
    resource_scarcity=0.40,
    room_count=6.0,
)
STATIC_STEP = 0.08
STATIC_A7 = -0.1


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class DungeonDifficultyEnv(gym.Env):
    """One episode = one simulated playthrough of MAX_LEVELS dungeon floors
    (the adaptive phase, Floor 6 onwards, after the 5-floor cold start).

    Observation (8): [norm_time, norm_deaths, norm_dmg_ratio,
                       norm_enemy_hp, norm_enemy_dmg, norm_hazard,
                       norm_rooms, norm_level]
    Action (8, continuous in [-1, 1] — Godot denormalizes to real ranges):
      [enemy_health, enemy_damage, enemy_speed, enemy_aggro,
       hazard_density, resource_scarcity, room_count, archetype_complexity]

    reset(options=...) accepts: skill (float, initial skill), shifts
    ({level_index: delta_skill}, scripted abrupt changes), random_shifts (bool).
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(ACT_DIM,), dtype=np.float32)
        self.rng = np.random.default_rng()
        self.reset()

    # ------------------------------------------------------------------ reset
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None or not hasattr(self, "rng"):
            self.rng = np.random.default_rng(seed)
            # The player (skill drift / abrupt shifts / reflex-vs-tactics bias) has its OWN
            # random stream, so two policies evaluated on the same seed face the SAME player
            # trajectory (paired comparison) even though their level layouts consume different
            # amounts of simulator noise.
            self.prng = np.random.default_rng(None if seed is None else [seed, 7919])
        else:
            self.prng = np.random.default_rng(int(self.rng.integers(2**31)))
        options = options or {}
        self.level = 0
        s0 = options.get("skill")
        if s0 is None:
            s0 = self.prng.uniform(*SKILL_INIT)
        self.skill = float(s0)
        self.bias = float(self.prng.uniform(-REFLEX_BIAS, REFLEX_BIAS))
        self.scripted_shifts = dict(options.get("shifts", {}))
        self.random_shifts = bool(options.get("random_shifts", not self.scripted_shifts))
        self.revert = {}  # level_index -> delta to apply (end of a transient shift)
        # State after the 5-floor cold start: DifficultyManager still holds the Floor-5 values.
        c5 = CAL_LEVELS[-1]
        self.params = dict(
            enemy_health=float(c5["hp"]),
            enemy_damage=float(c5["dmg"]),
            enemy_speed=float(c5["spd"]),
            enemy_aggro=float(c5["agr"]),
            hazard_density=float(c5["haz"]),
            resource_scarcity=float(c5["scar"]),
            room_count=float(c5["rooms"]),
        )
        self.a7 = None
        self.prev_action = None
        self.last_time, self.last_deaths, self.last_dmg_ratio = self._calibrate()
        return self._get_obs(), {}

    def _calibrate(self):
        """CR0: average observation fields over the 5 explicit calibration floors."""
        ts, ds, rs = [], [], []
        for cal in CAL_LEVELS:
            p = dict(
                enemy_health=cal["hp"],
                enemy_damage=cal["dmg"],
                enemy_speed=cal["spd"],
                enemy_aggro=cal["agr"],
                hazard_density=cal["haz"],
                resource_scarcity=cal["scar"],
                room_count=cal["rooms"],
            )
            res = self._simulate(p, np.asarray(cal["mix"], dtype=np.float64), cal["cs"])
            ts.append(res["time"])
            ds.append(res["deaths"])
            rs.append(res["dmg_ratio"])
        return float(np.mean(ts)), int(round(np.mean(ds))), float(np.mean(rs))

    # ----------------------------------------------------------------- obs
    def _get_obs(self):
        p = self.params
        return np.array(
            [
                np.clip(self.last_time / (TARGET_TIME * 2.0), 0, 1),
                np.clip(self.last_deaths / 3.0, 0, 1),
                np.clip(self.last_dmg_ratio, 0, 1),
                norm(p["enemy_health"], "enemy_health"),
                norm(p["enemy_damage"], "enemy_damage"),
                norm(p["hazard_density"], "hazard_density"),
                norm(p["room_count"], "room_count"),
                np.clip((5 + max(self.level, 1)) / 10.0, 0, 1),
            ],
            dtype=np.float32,
        )

    # -------------------------------------------------------- player model
    @property
    def player_skill(self):  # backwards-compatible alias
        return self.skill

    @player_skill.setter
    def player_skill(self, v):
        self.skill = float(v)

    def _axes(self):
        r = float(np.clip(self.skill + self.bias, 0.0, 1.0))
        t = float(np.clip(self.skill - self.bias, 0.0, 1.0))
        return r, t

    def _advance_skill(self):
        """Gradual drift + abrupt shifts (called once after every floor)."""
        prng = self.prng
        self.skill += float(prng.normal(DRIFT_MEAN, DRIFT_STD))
        k = self.level  # index of the NEXT floor
        if k in self.revert:
            self.skill += self.revert.pop(k)
        if k in self.scripted_shifts:
            self.skill += self.scripted_shifts[k]
        elif self.random_shifts and prng.random() < SHIFT_PROB:
            d = float(prng.uniform(*SHIFT_MAG)) * (1.0 if prng.random() < 0.5 else -1.0)
            self.skill += d
            if prng.random() < SHIFT_TRANSIENT_P:  # tilt / break: reverts later
                self.revert[k + int(prng.integers(3, 7))] = -d
        self.skill = float(np.clip(self.skill, 0.02, 0.98))

    # ----------------------------------------------------------- physics
    def _room_layout(self, p, count_scale):
        """Per-room enemy slots / hazard tiles / healing, mirroring DungeonGenerator.gd."""
        rng = self.rng
        R = int(round(p["room_count"]))
        haz, scar = p["hazard_density"], p["resource_scarcity"]
        avail = max(R - 2, 1)
        n_haz = int(np.clip(int(haz * avail), 1, avail))
        n_tre = int(np.clip(int((1.0 - scar) * 2.5), 1, 3))
        counts = np.zeros(R)
        hz = np.zeros(R)
        pickups = 0.0
        for i in range(1, R):
            j = i - 1  # index among key rooms
            if i == R - 1:  # exit room
                counts[i] = int(np.clip(int(3 + haz * 3.0), 3, 6))
                hz[i] = int(np.clip(int(haz * 6.0), 1, 6))
            elif j < n_haz:
                counts[i] = rng.integers(1, 4)
                hz[i] = int(np.clip(int(haz * 10.0), 3, 10))
            elif j < n_haz + n_tre:
                counts[i] = rng.integers(1, 3)
                pickups += rng.integers(2, 5)
            else:
                counts[i] = rng.integers(2, 6)
                hz[i] = int(np.clip(int(haz * 4.0), 0, 4))
                pickups += 1.0 if rng.random() > scar else 0.0
        if count_scale != 1.0:
            counts = np.where(counts > 0, np.maximum(1, np.round(counts * count_scale)), 0)
        return counts, hz, pickups * HEAL_PER_PICKUP

    def _mix_stats(self, p, mix):
        """Mix-averaged per-slot quantities (all use the contract mix `mix`)."""
        spd_abs = p["enemy_speed"] * SPD_MULT
        spd_n = np.clip((spd_abs - 60.0) / 160.0, 0.0, 1.6)
        agr_abs = np.maximum(p["enemy_aggro"] * AGR_MULT, AGR_FLOOR)
        agr_n = np.clip((agr_abs - 100.0) / 350.0, 0.0, 1.6)
        return dict(
            spd=float(mix @ (spd_n**EXP_SPEED)),
            agr=float(mix @ (agr_n**EXP_AGGRO)),
            spd_rel=float(mix @ (spd_abs / 130.0)),
            hslot=float(mix @ SLOT_HP),
            expo=float(mix @ EXPOSURE),
            bodies=float(mix @ BODIES),
            th_r=float(mix @ THREAT_REFLEX) / THREAT_REFLEX_REF,
            th_t=float(mix @ THREAT_TACTICS) / THREAT_TACTICS_REF,
            sens=float(mix @ SENSITIVITY),
        )

    def _physics(self, p, mix, counts, hz, rho, tau):
        """Noise-free per-room time and damage for a player with reflex `rho`, tactics `tau`.
        Returns (t_room[R], d_total[R], mu0)."""
        st = self._mix_stats(p, mix)
        R = len(counts)
        fight = counts > 0
        nbar = float(counts[fight].mean()) if fight.any() else 0.0

        hp_n = max(0.0, norm_raw(p["enemy_health"] * st["hslot"], "enemy_health"))
        dmg_abs = p["enemy_damage"]
        haz_n = max(0.0, norm_raw(p["hazard_density"], "hazard_density"))
        scar_n = float(np.clip(norm_raw(p["resource_scarcity"], "resource_scarcity"), 0.0, 1.0))
        cnt_n = float(np.clip((nbar * st["bodies"] - 1.5) / 4.5, 0.0, 1.3))

        # loads on the two skill axes (diminishing returns via the exponents above)
        load_r = (W_R[0] * st["spd"] + W_R[1] * haz_n**EXP_HAZARD + W_R[2] * st["agr"]) * st["th_r"]
        load_t = (W_T[0] * hp_n + W_T[1] * cnt_n + W_T[2] * st["agr"]) * st["th_t"]
        skill_mean = 0.5 * (rho + tau)
        pen = SENS_PEN * (st["sens"] - SENS_REF) * (1.0 - skill_mean) ** 2
        gap = (
            GAP_R_W * (load_r - SKILL_GAIN_R * rho)
            + GAP_T_W * (load_t - SKILL_GAIN_T * tau)
            + LOAD_OFFSET
            + pen
        )
        mu0 = float(sigmoid(GAP_SLOPE * gap))

        dps = (0.30 + 1.2 * tau) / 0.9  # tactics speeds up killing
        mu = np.clip(mu0 * (1.0 + FATIGUE * np.arange(R)), MU_MIN, MU_MAX)
        sim = 1.0 + SIM_AGGRO * st["agr"] * np.clip(counts * st["bodies"] - 1.0, 0, 6) / 6.0
        caution = 1.0 + CAUTION_DMG * norm_raw(dmg_abs, "enemy_damage") + CAUTION_SCAR * scar_n
        kill = counts * T_KILL * st["hslot"] * (p["enemy_health"] / 60.0) / dps
        evade = counts * T_EVADE * st["spd_rel"] * (1.0 - 0.7 * rho)
        stagger = counts * T_STAGGER * mu
        haz_t = T_HAZARD * hz * (1.15 - 0.7 * rho)
        t_room = T_TRAVERSE + (kill + evade + stagger) * caution + haz_t
        d_enemy = (
            DMG_K
            * (dmg_abs / 27.5) ** EXP_DMG
            * st["expo"]
            * (p["enemy_health"] / 60.0)
            * counts
            * sim
            * mu
            / dps
        )
        d_haz = HAZ_DMG * hz * (1.15 - 0.7 * rho)
        return t_room, d_enemy + d_haz, mu0

    def _simulate(self, p, mix, count_scale=1.0):
        """Turns difficulty params + archetype mix + player skill into
        (completion_time, deaths, damage_ratio) with noise."""
        rng = self.rng
        rho, tau = self._axes()
        counts, hz, heal = self._room_layout(p, count_scale)
        R = len(counts)
        t_room, d_room, _ = self._physics(p, mix, counts, hz, rho, tau)
        t_room = t_room * np.exp(rng.normal(0.0, TIME_NOISE_ROOM, R))
        gross = float(d_room.sum()) * float(np.exp(rng.normal(0.0, DMG_NOISE_LEVEL)))
        net = gross - HEAL_USE * min(heal, gross)
        deaths = int(min(6, np.floor(net)))
        total = float(t_room.sum()) * float(np.exp(rng.normal(0.0, TIME_NOISE_LEVEL)))
        total += deaths * RESPAWN_S
        # Skill-independent "challenge" of these settings: pace and damage that a REFERENCE
        # player (reflex = tactics = 0.5) would experience on this very layout.
        t_ref, d_ref, _ = self._physics(p, mix, counts, hz, 0.5, 0.5)
        challenge = (
            0.5 * float(t_ref.mean()) / TARGET_TPR + 0.5 * float(d_ref.sum()) / FLOW_DMG_TARGET
        )
        return dict(
            time=max(5.0, total),
            deaths=deaths,
            dmg_ratio=float(np.clip(gross, 0.0, 1.0)),
            gross=gross,
            rooms=R,
            challenge=challenge,
            skill=self.skill,
        )

    # ---------------------------------------------------------------- step
    def _finish_level(self, res, action_vec):
        """Shared by step() and the static baseline: update obs state, compute reward."""
        self.last_time, self.last_deaths, self.last_dmg_ratio = (
            res["time"],
            res["deaths"],
            res["dmg_ratio"],
        )
        self.level += 1
        reward, parts = self.reward_fn(res, action_vec, self.prev_action)
        self.prev_action = action_vec
        self._advance_skill()
        return reward, parts

    @staticmethod
    def reward_fn(res, action_vec, prev_action):
        """Pacing-per-room + deaths (v1 terms, kept) + flow + smoothness (new)."""
        rooms = max(1, res["rooms"])
        deaths = res["deaths"]
        tpr = res["time"] / rooms
        time_error = min(TIME_ERR_CAP, abs(tpr - TARGET_TPR) / TARGET_TPR)
        reward = 1.0 - time_error
        reward -= deaths * 0.5
        if deaths == 0 and tpr < TARGET_TPR * 0.5:
            reward -= 0.3  # should have escalated combat harder
        if deaths >= 2:
            reward -= 0.4  # should have eased combat off
        reward -= FLOW_DMG_W * abs(res["dmg_ratio"] - FLOW_DMG_TARGET)
        flow = deaths == 0 and time_error < 0.25
        # Room count is judged against the player's proficiency (v1 judged it against challenge):
        # more rooms = longer, more demanding run, which only a skilled player enjoys.
        reward -= ROOM_W * abs(rooms - (5.0 + 4.0 * res["skill"])) / 4.0
        # Archetype variety is judged against proficiency too: novices should meet mostly simple
        # enemies (crawlers, swarms), experts the brutes / skirmishers.
        reward -= COMPLEX_W * abs(res.get("c", 0.5) - res["skill"])
        reward -= BALANCE_W * float(np.mean(np.square(action_vec)))
        smooth = 0.0
        if prev_action is not None:
            smooth = float(np.mean(np.abs(action_vec - prev_action)))
            reward -= SMOOTH_LAMBDA * smooth
        return float(reward), dict(pace_err=time_error, smooth=smooth, flow=flow)

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        for i, key in enumerate(PARAM_ORDER):
            self.params[key] = float(denorm(action[i], key))
        self.params["room_count"] = float(round(self.params["room_count"]))
        self.a7 = float(action[7])
        mix = archetype_mix(self.a7)

        res = self._simulate(self.params, mix)
        res["c"] = (self.a7 + 1.0) / 2.0
        reward, parts = self._finish_level(res, action)
        terminated = self.level >= MAX_LEVELS
        info = dict(
            time=res["time"],
            deaths=res["deaths"],
            dmg_ratio=res["dmg_ratio"],
            gross=res["gross"],
            challenge=res["challenge"],
            rooms=res["rooms"],
            skill=self.skill,
            mix=mix,
            **parts,
        )
        return self._get_obs(), float(reward), terminated, False, info

    def step_static(self, floor):
        """Static +8 % baseline (Intermediate preset, health/damage x(1+0.08*(floor-1)),
        fixed a7 = -0.1).  `floor` is 1-based.  Returns (obs, reward, terminated, info)."""
        f = 1.0 + STATIC_STEP * max(floor - 1, 0)
        self.params = dict(INTERMEDIATE)
        self.params["enemy_health"] *= f
        self.params["enemy_damage"] *= f
        self.a7 = STATIC_A7
        mix = archetype_mix(self.a7)
        res = self._simulate(self.params, mix)
        res["c"] = (self.a7 + 1.0) / 2.0
        vec = np.append(to_action(self.params), self.a7)
        reward, parts = self._finish_level(res, vec)
        obs_params = self.params
        # the observation clips to PPO ranges, exactly like DifficultyManager.build_observation
        obs = self._get_obs()
        terminated = self.level >= MAX_LEVELS
        info = dict(
            time=res["time"],
            deaths=res["deaths"],
            dmg_ratio=res["dmg_ratio"],
            challenge=res["challenge"],
            rooms=res["rooms"],
            params=dict(obs_params),
            **parts,
        )
        return obs, float(reward), terminated, info


# ---------------------------------------------------------------------------
# Training / export
# ---------------------------------------------------------------------------
class TrainWrapper(gym.Wrapper):
    """Training-only wrapper that exposes a WIDE action box [-4, 4] to SB3.

    SB3 clips sampled actions to the action space before calling env.step().  With a
    [-1, 1] box, an output mean that drifts beyond +-1 gets zero gradient (every sample is
    clipped to the same bound) and the dimension is stuck at the bound for good.  Here the
    env clips to [-1, 1] itself (exactly what PPOPolicy.gd does at run time) and adds a small
    penalty OOB_LAMBDA * sum(max(0, |a| - 1)^2) so that a mean outside the legal range always
    has a gradient pulling it back.  The saved model's action space is reset to [-1, 1]
    (see train()), so predict() clips like the game does.
    """

    def __init__(self, env):
        super().__init__(env)
        self.action_space = spaces.Box(low=-4.0, high=4.0, shape=(ACT_DIM,), dtype=np.float32)

    def step(self, action):
        a = np.asarray(action, dtype=np.float64)
        excess = float(np.sum(np.maximum(0.0, np.abs(a) - 1.0) ** 2))
        obs, r, term, trunc, info = self.env.step(np.clip(a, -1.0, 1.0))
        return obs, r - OOB_LAMBDA * excess, term, trunc, info


def make_vec_env(n_envs=8, seed=0):
    from stable_baselines3.common.env_util import make_vec_env as _mk

    return _mk(DungeonDifficultyEnv, n_envs=n_envs, seed=seed, wrapper_class=TrainWrapper)


def make_model(env, seed=0, **kw):
    params = dict(
        policy_kwargs=dict(net_arch=[64, 64], activation_fn=__import__("torch").nn.Tanh),
        verbose=0,
        n_steps=512,
        batch_size=512,
        n_epochs=10,
        learning_rate=lambda f: 3e-4 * (0.1 + 0.9 * f),  # linear decay to 3e-5
        gamma=0.9,
        gae_lambda=0.9,
        ent_coef=0.0,
        seed=seed,
        device="cpu",
    )
    params.update(kw)
    return PPO("MlpPolicy", env, **params)


def train(seed=0, total_timesteps=600_000, n_envs=8, save_path="ppo_difficulty_model", verbose=0):
    env = make_vec_env(n_envs, seed)
    model = make_model(env, seed=seed, verbose=verbose)
    model.learn(total_timesteps=total_timesteps)
    finalize_model(model)
    if save_path:
        model.save(save_path)
    return model


def finalize_model(model):
    """Restore the deployment action space ([-1, 1]) on a model trained through TrainWrapper."""
    box = spaces.Box(low=-1.0, high=1.0, shape=(ACT_DIM,), dtype=np.float32)
    model.action_space = box
    model.policy.action_space = box


def export_policy_to_json(model: PPO, path="policy_weights.json", meta=True):
    """Extracts the trained actor network's weights into plain JSON matrices
    so PPOPolicy.gd can run the forward pass without any ML runtime."""
    policy_net = model.policy.mlp_extractor.policy_net
    action_net = model.policy.action_net

    layers = []
    for module in policy_net:
        if hasattr(module, "weight"):
            layers.append(
                {
                    "w": module.weight.detach().cpu().numpy().tolist(),
                    "b": module.bias.detach().cpu().numpy().tolist(),
                }
            )
    layers.append(
        {
            "w": action_net.weight.detach().cpu().numpy().tolist(),
            "b": action_net.bias.detach().cpu().numpy().tolist(),
        }
    )

    out = {"layers": layers, "activation": "tanh"}
    if meta:
        out["meta"] = {"obs_dim": OBS_DIM, "act_dim": len(layers[-1]["b"]), "version": "sim-v2"}
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"Exported policy to {path} ({len(layers)} layers).")
    print("Copy this file to res://ai/policy_weights.json in your Godot project.")


def load_training_data_from_sqlite(db_path: str | None = None) -> dict:
    """Judge-model training data (per-floor settings -> outcome) from a telemetry SQLite DB.

    Defaults to ml_spike/telemetry_data/forge_telemetry.db; run
    ``python ml_spike/telemetry_data/telemetry_db.py`` first to sync it from the game's user:// DB.
    Rows with missing parameters are skipped (see the returned "skipped" count).
    """
    try:
        from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase
    except ImportError:
        from telemetry_data.telemetry_db import TelemetryDatabase

    return TelemetryDatabase(db_path).get_judge_training_data()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timesteps", type=int, default=600_000)
    ap.add_argument("--out", default="policy_weights.json")
    args = ap.parse_args()
    trained_model = train(args.seed, args.timesteps, verbose=1)
    export_policy_to_json(trained_model, args.out)
