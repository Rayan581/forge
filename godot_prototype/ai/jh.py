"""
Sensitivity check for a trained policy_weights.json.

For each observation dimension, this holds every other dimension at a
neutral 0.5 and sweeps that one dimension from 0 -> 1, then measures how
much each output (especially room_count, index 6) moves. A dimension that
barely matters will show near-zero swing; a dimension the network leans on
heavily will show a large swing.

Run:
    python inspect_policy.py policy_weights.json
"""

import json
import sys
import numpy as np

OBS_NAMES = ["time", "deaths", "dmg_ratio", "enemy_hp", "enemy_dmg", "hazard", "room_count", "level"]
ACTION_NAMES = ["enemy_health", "enemy_damage", "enemy_speed", "enemy_aggro",
                "hazard_density", "resource_scarcity", "room_count"]


def forward(layers, obs):
    x = np.array(obs, dtype=np.float64)
    for i, layer in enumerate(layers):
        w = np.array(layer["w"], dtype=np.float64)  # [out, in]
        b = np.array(layer["b"], dtype=np.float64)
        x = w @ x + b
        if i < len(layers) - 1:
            x = np.tanh(x)
    return np.tanh(x)  # final squash, matches PPOPolicy.gd


def main(path):
    with open(path) as f:
        data = json.load(f)
    layers = data["layers"]

    print(f"Loaded {len(layers)} layers.\n")
    print(f"{'obs dim swept':<14}" + "".join(f"{n:>16}" for n in ACTION_NAMES))

    for dim_idx, dim_name in enumerate(OBS_NAMES):
        base = np.full(8, 0.5)
        low_obs = base.copy(); low_obs[dim_idx] = 0.0
        high_obs = base.copy(); high_obs[dim_idx] = 1.0

        out_low = forward(layers, low_obs)
        out_high = forward(layers, high_obs)
        swing = out_high - out_low

        row = f"{dim_name:<14}" + "".join(f"{v:>16.3f}" for v in swing)
        print(row)

    print("\nLarger absolute numbers = that observation dimension moves that output more.")
    print("Look at the 'room_count' column: whichever obs row has the biggest number")
    print("there is what the trained policy is actually reacting to when it sets room count.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "policy_weights.json"
    main(path)