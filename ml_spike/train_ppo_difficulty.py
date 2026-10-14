"""
FORGE — Adaptive Difficulty PPO Trainer
----------------------------------------
Trains a PPO agent whose job is: given how the player just performed
(completion time, deaths, damage taken) and the current difficulty
parameters, output the NEXT dungeon's parameters — escalating when the
player is clearing levels quickly and cleanly, easing off when they're
slow or dying a lot.

We can't have a real human play thousands of rounds to train against, so we
train against a *simulated* player whose skill drifts slowly over time and
whose performance is a stochastic function of how hard the current room is
relative to that skill. This is standard practice for bootstrapping DDA
(dynamic difficulty adjustment) agents before fine-tuning on real telemetry.

Install once:
    pip install stable-baselines3 gymnasium torch

Run:
    python train_ppo_difficulty.py

Output:
    policy_weights.json
    -> copy this file into your Godot project at res://ai/policy_weights.json
       (i.e. create an "ai" folder next to "scripts" and "scenes")

Later, once you're collecting real session_telemetry.json data from actual
playtesters, you can swap the simulated _simulate_level() function below for
replay/fine-tuning against real logs — the env/action/observation contract
stays identical, so Main.gd and PPOPolicy.gd don't need to change.
"""

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

TARGET_TIME = 45.0  # seconds — the pace we want a "well-matched" level to take
MAX_LEVELS = 30  # simulated levels per training episode


def denorm(value, key):
    lo, hi = PARAM_RANGES[key]
    t = (np.clip(value, -1.0, 1.0) + 1.0) / 2.0
    return lo + t * (hi - lo)


def norm(value, key):
    lo, hi = PARAM_RANGES[key]
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


class DungeonDifficultyEnv(gym.Env):
    """One episode = one simulated playthrough of ~MAX_LEVELS dungeon levels.

    Observation (8): [norm_time, norm_deaths, norm_dmg_ratio,
                       norm_enemy_hp, norm_enemy_dmg, norm_hazard,
                       norm_rooms, norm_level]
    Action (7, continuous in [-1, 1] — Godot denormalizes to real ranges):
      [enemy_health, enemy_damage, enemy_speed, enemy_aggro,
       hazard_density, resource_scarcity, room_count]
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(8,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(7,), dtype=np.float32)
        self.reset()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.rng = np.random.default_rng(seed)
        self.level = 0
        self.player_skill = self.rng.uniform(0.3, 0.6)  # 0..1, improves slowly over the run
        self.params = {
            "enemy_health": 60.0,
            "enemy_damage": 20.0,
            "enemy_speed": 125.0,
            "enemy_aggro": 240.0,
            "hazard_density": 0.35,
            "resource_scarcity": 0.40,
            "room_count": 6.0,
        }
        self.last_time, self.last_deaths, self.last_dmg_ratio = TARGET_TIME, 0, 0.3
        return self._get_obs(), {}

    def _get_obs(self):
        return np.array(
            [
                np.clip(self.last_time / (TARGET_TIME * 2.0), 0, 1),
                np.clip(self.last_deaths / 3.0, 0, 1),
                np.clip(self.last_dmg_ratio, 0, 1),
                norm(self.params["enemy_health"], "enemy_health"),
                norm(self.params["enemy_damage"], "enemy_damage"),
                norm(self.params["hazard_density"], "hazard_density"),
                norm(self.params["room_count"], "room_count"),
                np.clip(self.level / 10.0, 0, 1),
            ],
            dtype=np.float32,
        )

    def _simulate_level(self):
        """Turns current difficulty params + player skill into a
        (completion_time, deaths, damage_ratio) result, with noise."""
        hp_n = norm(self.params["enemy_health"], "enemy_health")
        dmg_n = norm(self.params["enemy_damage"], "enemy_damage")
        spd_n = (self.params["enemy_speed"] - 60.0) / 160.0
        haz_n = norm(self.params["hazard_density"], "hazard_density")
        rooms = self.params["room_count"]

        challenge = 0.35 * dmg_n + 0.25 * hp_n + 0.2 * spd_n + 0.2 * haz_n
        gap = challenge - self.player_skill  # > 0 = too hard, < 0 = too easy

        base_time_per_room = TARGET_TIME / 6.0
        time_mult = 1.0 + gap * 1.8
        completion_time = max(
            5.0, rooms * base_time_per_room * time_mult * self.rng.uniform(0.85, 1.15)
        )

        death_prob = float(np.clip(0.5 + gap * 1.2, 0.0, 0.95))
        deaths = (
            self.rng.binomial(3, death_prob)
            if gap > 0
            else self.rng.binomial(1, max(0.0, death_prob))
        )
        dmg_ratio = float(np.clip(0.3 + gap * 0.9 + self.rng.normal(0, 0.05), 0.0, 1.0))

        # Player slowly improves regardless of difficulty (learning the game).
        self.player_skill = float(
            np.clip(self.player_skill + self.rng.uniform(0.0, 0.01), 0.0, 1.0)
        )
        return completion_time, int(deaths), dmg_ratio

    def step(self, action):
        for i, key in enumerate(PARAM_ORDER):
            self.params[key] = denorm(action[i], key)
        self.params["room_count"] = round(self.params["room_count"])

        completion_time, deaths, dmg_ratio = self._simulate_level()
        self.last_time, self.last_deaths, self.last_dmg_ratio = completion_time, deaths, dmg_ratio
        self.level += 1

        # --- FIXED REWARD ---
        # The old version compared raw completion_time against a fixed
        # TARGET_TIME. Since completion_time = rooms * time_per_room, the
        # agent could satisfy that target purely by cranking room_count up
        # or down, with zero regard for actual combat difficulty (enemy
        # health/damage/speed/hazard). That's reward hacking: it optimizes
        # the metric without doing the thing the metric was meant to measure.
        #
        # Fix: judge pace PER ROOM instead of as a raw total, so scaling
        # room_count doesn't move this term at all. Room count is judged
        # separately, by how well it's tracking overall challenge.
        target_time_per_room = TARGET_TIME / 6.0
        time_per_room = completion_time / max(1, self.params["room_count"])
        time_error = abs(time_per_room - target_time_per_room) / target_time_per_room

        reward = 1.0 - time_error
        reward -= deaths * 0.5
        if deaths == 0 and time_per_room < target_time_per_room * 0.5:
            reward -= 0.3  # should have escalated combat harder
        if deaths >= 2:
            reward -= 0.4  # should have eased combat off

        # Room count should track overall challenge (more rooms = a longer,
        # more demanding run) rather than sit at an extreme regardless of
        # how the player is doing. Compute what "appropriate" room count
        # would be given current challenge/skill gap, and penalize distance
        # from it — this is what stops room_count from just pinning at 9.
        hp_n = norm(self.params["enemy_health"], "enemy_health")
        dmg_n = norm(self.params["enemy_damage"], "enemy_damage")
        challenge = 0.5 * dmg_n + 0.5 * hp_n
        appropriate_rooms = 5.0 + challenge * 4.0  # low challenge -> 5, high challenge -> 9
        room_mismatch = abs(self.params["room_count"] - appropriate_rooms) / 4.0
        reward -= room_mismatch * 0.5

        terminated = self.level >= MAX_LEVELS
        return self._get_obs(), float(reward), terminated, False, {}


def train():
    env = DungeonDifficultyEnv()
    model = PPO(
        "MlpPolicy",
        env,
        policy_kwargs=dict(net_arch=[64, 64]),
        verbose=1,
        n_steps=2048,
        batch_size=256,
        learning_rate=3e-4,
    )
    model.learn(total_timesteps=300_000)
    model.save("ppo_difficulty_model")
    return model


def export_policy_to_json(model: PPO, path="policy_weights.json"):
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

    with open(path, "w") as f:
        json.dump({"layers": layers, "activation": "tanh"}, f)
    print(f"Exported policy to {path} ({len(layers)} layers).")
    print("Copy this file to res://ai/policy_weights.json in your Godot project.")


if __name__ == "__main__":
    trained_model = train()
    export_policy_to_json(trained_model, "policy_weights.json")
