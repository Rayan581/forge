# Simulator v2 — evaluation of the retrained PPO policy

Protocol: 100 paired episodes x 30 levels per profile (episode i uses seed 10000+i for every policy, so all policies face the same player trajectory: skill drift + random abrupt shifts of the default population, and the same noise stream family).  `trained (exported)` is `godot_prototype/ai/policy_weights.json` run through the NumPy mirror of PPOPolicy.gd (seed 0); `seed k` rows are the SB3 checkpoints of the three training runs.  Pacing error = |t_room - 7.5 s| / 7.5 s.

## Reward / level (higher is better)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.732 | 0.732 | 0.731 | 0.724 | 0.038 | 0.462 | -1.127 |
| novice (0.20) | 0.750 | 0.750 | 0.749 | 0.749 | 0.270 | 0.503 | -0.787 |
| mid (0.45) | 0.791 | 0.791 | 0.788 | 0.786 | 0.689 | 0.553 | -0.109 |
| skilled (0.70) | 0.786 | 0.786 | 0.787 | 0.785 | 0.614 | 0.498 | 0.215 |
| expert (0.80) | 0.762 | 0.762 | 0.763 | 0.762 | 0.520 | 0.462 | 0.242 |
| expert (0.90) | 0.744 | 0.744 | 0.752 | 0.751 | 0.432 | 0.417 | 0.230 |

## Pacing error |t_room - target| / target (lower is better)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.128 | 0.128 | 0.127 | 0.133 | 0.659 | 0.317 | 1.347 |
| novice (0.20) | 0.127 | 0.127 | 0.125 | 0.125 | 0.500 | 0.273 | 1.150 |
| mid (0.45) | 0.115 | 0.115 | 0.116 | 0.118 | 0.210 | 0.181 | 0.688 |
| skilled (0.70) | 0.112 | 0.112 | 0.109 | 0.114 | 0.181 | 0.135 | 0.384 |
| expert (0.80) | 0.116 | 0.116 | 0.113 | 0.118 | 0.225 | 0.132 | 0.335 |
| expert (0.90) | 0.120 | 0.120 | 0.115 | 0.121 | 0.268 | 0.141 | 0.316 |

## Deaths / level (lower is better)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.000 | 0.000 | 0.000 | 0.000 | 0.008 | 0.000 | 0.647 |
| novice (0.20) | 0.000 | 0.000 | 0.000 | 0.000 | 0.003 | 0.000 | 0.480 |
| mid (0.45) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.162 |
| skilled (0.70) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.035 |
| expert (0.80) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.019 |
| expert (0.90) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.010 |

## Mean per-floor |delta action| (mean over the 8 dims, floors 2-30)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.047 | 0.047 | 0.043 | 0.041 | 0.000 | 0.046 | 0.021 |
| novice (0.20) | 0.049 | 0.049 | 0.045 | 0.042 | 0.000 | 0.045 | 0.021 |
| mid (0.45) | 0.052 | 0.052 | 0.049 | 0.047 | 0.000 | 0.038 | 0.021 |
| skilled (0.70) | 0.054 | 0.054 | 0.051 | 0.048 | 0.000 | 0.031 | 0.021 |
| expert (0.80) | 0.052 | 0.052 | 0.050 | 0.045 | 0.000 | 0.028 | 0.021 |
| expert (0.90) | 0.053 | 0.053 | 0.050 | 0.044 | 0.000 | 0.027 | 0.021 |

## Trained (exported) vs baselines — paired comparison

| profile | baseline | reward diff (trained - base) | pacing-error diff | trained better on both |
|---|---|---|---|---|
| novice (0.10) | random-init (10) | +0.694 (p=3.3e-42) | -0.531 (p=2.6e-43) | yes |
| novice (0.10) | heuristic | +0.270 (p=4.8e-68) | -0.189 (p=6.1e-57) | yes |
| novice (0.10) | static +8% | +1.859 (p=6.1e-59) | -1.219 (p=2.5e-68) | yes |
| novice (0.20) | random-init (10) | +0.479 (p=4.2e-35) | -0.373 (p=5.1e-37) | yes |
| novice (0.20) | heuristic | +0.247 (p=3.1e-70) | -0.146 (p=3.2e-49) | yes |
| novice (0.20) | static +8% | +1.536 (p=1.2e-55) | -1.024 (p=1.3e-62) | yes |
| mid (0.45) | random-init (10) | +0.102 (p=6.5e-11) | -0.095 (p=2.7e-14) | yes |
| mid (0.45) | heuristic | +0.238 (p=2.4e-75) | -0.066 (p=1.1e-27) | yes |
| mid (0.45) | static +8% | +0.900 (p=6.1e-48) | -0.573 (p=7.5e-45) | yes |
| skilled (0.70) | random-init (10) | +0.172 (p=9.8e-37) | -0.069 (p=4.1e-26) | yes |
| skilled (0.70) | heuristic | +0.288 (p=4.7e-80) | -0.023 (p=1.6e-13) | yes |
| skilled (0.70) | static +8% | +0.571 (p=1.9e-57) | -0.272 (p=4.9e-36) | yes |
| expert (0.80) | random-init (10) | +0.243 (p=7.9e-47) | -0.109 (p=3.4e-40) | yes |
| expert (0.80) | heuristic | +0.300 (p=1.4e-86) | -0.016 (p=1.6e-10) | yes |
| expert (0.80) | static +8% | +0.520 (p=2.4e-61) | -0.218 (p=3.8e-35) | yes |
| expert (0.90) | random-init (10) | +0.311 (p=3.3e-53) | -0.147 (p=6.7e-48) | yes |
| expert (0.90) | heuristic | +0.326 (p=5.0e-87) | -0.020 (p=4.4e-19) | yes |
| expert (0.90) | static +8% | +0.514 (p=2.0e-72) | -0.195 (p=5.8e-39) | yes |

Profiles (of 6) on which the trained policy has the better mean on BOTH reward and pacing error: vs random-init (10): **6/6**, vs heuristic: **6/6**, vs static +8%: **6/6**

## Mean parameter value chosen per profile (trained, exported)

| profile | HP | Dmg | Speed | Aggro | Hazard | Scarcity | Rooms | a7 (c) |
|---|---|---|---|---|---|---|---|---|
| *range* | *20-120* | *5-50* | *60-220* | *100-450* | *0.05-0.8* | *0.1-0.9* | *5-9* | *-1..1* |
| novice (0.10) | 27.8 | 26.1 | 110 | 319 | 0.58 | 0.47 | 6.2 | -0.43 (0.29) |
| novice (0.20) | 31.9 | 26.3 | 114 | 315 | 0.59 | 0.48 | 6.3 | -0.34 (0.33) |
| mid (0.45) | 48.7 | 27.1 | 130 | 300 | 0.61 | 0.48 | 7.1 | -0.01 (0.50) |
| skilled (0.70) | 68.8 | 27.9 | 148 | 283 | 0.63 | 0.48 | 7.9 | +0.37 (0.69) |
| expert (0.80) | 75.0 | 28.2 | 153 | 279 | 0.63 | 0.48 | 8.1 | +0.49 (0.74) |
| expert (0.90) | 80.9 | 28.5 | 158 | 273 | 0.63 | 0.48 | 8.3 | +0.59 (0.80) |

Mean archetype mix produced by that a7 (crawler, pyromancer, brute, skirmisher, swarmer):

| profile | Melee Crawler | Ranged Pyromancer | Heavy Brute | Agile Skirmisher | Swarmer |
|---|---|---|---|---|---|
| novice (0.10) | 0.19 | 0.23 | 0.07 | 0.12 | 0.39 |
| novice (0.20) | 0.16 | 0.26 | 0.08 | 0.14 | 0.36 |
| mid (0.45) | 0.10 | 0.35 | 0.12 | 0.23 | 0.21 |
| skilled (0.70) | 0.06 | 0.24 | 0.23 | 0.35 | 0.11 |
| expert (0.80) | 0.05 | 0.21 | 0.29 | 0.35 | 0.10 |
| expert (0.90) | 0.05 | 0.18 | 0.36 | 0.33 | 0.09 |

## Criterion (a): per-profile mean position inside each range (0 = min bound, 1 = max bound)

| dim | novice (0.10) | novice (0.20) | mid (0.45) | skilled (0.70) | expert (0.80) | expert (0.90) | within 5% of a bound on all 6? |
|---|---|---|---|---|---|---|---|
| enemy_health | 0.08 | 0.12 | 0.29 | 0.49 | 0.55 | 0.61 | ok |
| enemy_damage | 0.47 | 0.47 | 0.49 | 0.51 | 0.51 | 0.52 | ok |
| enemy_speed | 0.31 | 0.34 | 0.44 | 0.55 | 0.58 | 0.61 | ok |
| enemy_aggro | 0.62 | 0.61 | 0.57 | 0.52 | 0.51 | 0.49 | ok |
| hazard_density | 0.71 | 0.72 | 0.75 | 0.77 | 0.77 | 0.77 | ok |
| resource_scarcity | 0.47 | 0.47 | 0.47 | 0.47 | 0.48 | 0.48 | ok |
| room_count | 0.30 | 0.35 | 0.52 | 0.72 | 0.78 | 0.83 | ok |
| archetype_complexity | 0.29 | 0.33 | 0.50 | 0.69 | 0.74 | 0.80 | ok |

## Criterion (b): learned action standard deviation (exp(log_std))

| run | enemy_health | enemy_damage | enemy_speed | enemy_aggro | hazard_density | resource_scarcity | room_count | archetype_complexity | max |
|---|---|---|---|---|---|---|---|---|---|
| seed 0 | 0.14 | 0.25 | 0.25 | 0.28 | 0.24 | 0.25 | 0.17 | 0.19 | 0.28 |
| seed 1 | 0.14 | 0.25 | 0.24 | 0.30 | 0.22 | 0.27 | 0.18 | 0.20 | 0.30 |
| seed 2 | 0.14 | 0.25 | 0.25 | 0.27 | 0.24 | 0.27 | 0.17 | 0.20 | 0.27 |

## Criterion (c): challenge chosen vs initial skill (trained, exported)

| profile | game difficulty score (0-100) | simulator load index |
|---|---|---|
| novice (0.10) | 40.1 | 0.631 |
| novice (0.20) | 41.5 | 0.686 |
| mid (0.45) | 47.1 | 0.956 |
| skilled (0.70) | 53.7 | 1.396 |
| expert (0.80) | 55.6 | 1.549 |
| expert (0.90) | 57.5 | 1.743 |

Spearman rho (initial skill vs mean difficulty score) = **1.000**; vs simulator load index = **1.000**.

## Abrupt-shift scenario

Skill drops by 0.30 at level 10 (0-based; the first affected floor is floor 10) and recovers (+0.30) at level 20; no random shifts; 100 paired episodes.  The table gives the number of floors from the shift (the shifted floor counts as 1) until the cross-episode mean pacing error is <= 0.15 on two consecutive floors (`never` = not within 10 floors).

| skill path | policy | mean err floors 3-9 | err on drop floor | floors to recover after drop | err on recovery floor | floors to re-settle after recovery | deaths on drop floor |
|---|---|---|---|---|---|---|---|
| 0.45 -> 0.15 -> 0.45 | trained (exported) | 0.101 | 0.343 | 3 | 0.286 | 3 | 0.00 |
| 0.45 -> 0.15 -> 0.45 | heuristic | 0.194 | 0.516 | never | 0.175 | 2 | 0.00 |
| 0.45 -> 0.15 -> 0.45 | static +8% | 0.276 | 1.062 | never | 0.864 | never | 0.04 |
| 0.45 -> 0.15 -> 0.45 | random-init (seed 1000) | 0.175 | 0.626 | never | 0.138 | 1 | 0.00 |
| 0.70 -> 0.40 -> 0.70 | trained (exported) | 0.106 | 0.339 | 2 | 0.297 | 3 | 0.00 |
| 0.70 -> 0.40 -> 0.70 | heuristic | 0.113 | 0.302 | never | 0.219 | never | 0.00 |
| 0.70 -> 0.40 -> 0.70 | static +8% | 0.121 | 0.488 | never | 0.414 | never | 0.00 |
| 0.70 -> 0.40 -> 0.70 | random-init (seed 1000) | 0.141 | 0.226 | never | 0.177 | never | 0.00 |
| 0.80 -> 0.50 -> 0.80 | trained (exported) | 0.107 | 0.325 | 2 | 0.325 | 3 | 0.00 |
| 0.80 -> 0.50 -> 0.80 | heuristic | 0.119 | 0.246 | 7 | 0.237 | never | 0.00 |
| 0.80 -> 0.50 -> 0.80 | static +8% | 0.164 | 0.330 | never | 0.275 | never | 0.00 |
| 0.80 -> 0.50 -> 0.80 | random-init (seed 1000) | 0.220 | 0.130 | 1 | 0.261 | never | 0.00 |

## Simulator check 1: every action dimension makes the floor harder (others at 0)

| action dim | skill | t/room @-1 | t/room @+1 | gross dmg @-1 | gross dmg @+1 | deaths @-1 | deaths @+1 | direction ok |
|---|---|---|---|---|---|---|---|---|
| enemy_health | 0.2 | 7.42 | 16.18 | 0.254 | 0.991 | 0.00 | 0.01 | yes |
| enemy_health | 0.5 | 5.60 | 11.33 | 0.147 | 0.578 | 0.00 | 0.00 | yes |
| enemy_health | 0.8 | 3.95 | 8.20 | 0.081 | 0.259 | 0.00 | 0.00 | yes |
| enemy_damage | 0.2 | 10.65 | 12.99 | 0.203 | 1.042 | 0.00 | 0.04 | yes |
| enemy_damage | 0.5 | 7.72 | 9.26 | 0.133 | 0.545 | 0.00 | 0.00 | yes |
| enemy_damage | 0.8 | 5.56 | 6.55 | 0.079 | 0.216 | 0.00 | 0.00 | yes |
| enemy_speed | 0.2 | 10.95 | 12.60 | 0.609 | 0.624 | 0.00 | 0.00 | yes |
| enemy_speed | 0.5 | 7.47 | 9.33 | 0.275 | 0.375 | 0.00 | 0.00 | yes |
| enemy_speed | 0.8 | 5.32 | 6.76 | 0.112 | 0.180 | 0.00 | 0.00 | yes |
| enemy_aggro | 0.2 | 11.77 | 11.81 | 0.552 | 0.672 | 0.00 | 0.00 | yes |
| enemy_aggro | 0.5 | 8.20 | 8.67 | 0.267 | 0.393 | 0.00 | 0.00 | yes |
| enemy_aggro | 0.8 | 5.81 | 6.27 | 0.113 | 0.181 | 0.00 | 0.00 | yes |
| hazard_density | 0.2 | 11.42 | 12.35 | 0.553 | 0.762 | 0.00 | 0.01 | yes |
| hazard_density | 0.5 | 7.89 | 9.18 | 0.240 | 0.491 | 0.00 | 0.00 | yes |
| hazard_density | 0.8 | 5.58 | 6.69 | 0.079 | 0.277 | 0.00 | 0.00 | yes |
| resource_scarcity | 0.2 | 9.88 | 12.49 | 0.526 | 0.623 | 0.00 | 0.00 | yes |
| resource_scarcity | 0.5 | 7.16 | 8.95 | 0.284 | 0.339 | 0.00 | 0.00 | yes |
| resource_scarcity | 0.8 | 5.19 | 6.35 | 0.125 | 0.147 | 0.00 | 0.00 | yes |
| room_count | 0.2 | 11.04 | 12.62 | 0.408 | 0.885 | 0.00 | 0.01 | yes |
| room_count | 0.5 | 7.91 | 9.09 | 0.214 | 0.490 | 0.00 | 0.00 | yes |
| room_count | 0.8 | 5.69 | 6.44 | 0.092 | 0.206 | 0.00 | 0.00 | yes |
| archetype_complexity | 0.2 | 11.15 | 13.64 | 0.502 | 0.885 | 0.00 | 0.00 | yes |
| archetype_complexity | 0.5 | 7.74 | 9.66 | 0.239 | 0.492 | 0.00 | 0.00 | yes |
| archetype_complexity | 0.8 | 5.61 | 6.84 | 0.109 | 0.193 | 0.00 | 0.00 | yes |

All dimensions monotone in the harder direction: **True**

## Simulator check 2: no parameter is dominated

For each dim, 16 random contexts (other dims ~ U(-0.7, 0.7)) x 6 skills: the grid value (9 points) that maximises the immediate per-floor reward (pacing + deaths + flow terms; smoothness excluded).  A dim is dominated if one bound is optimal in >95 % of contexts.

| action dim | % contexts optimum at -1 | % at +1 | % interior | mean optimum @skill 0.10 | @0.45 | @0.90 | dominated? |
|---|---|---|---|---|---|---|---|
| enemy_health | 31 | 8 | 60 | -1.00 | -0.59 | +0.77 | no |
| enemy_damage | 21 | 36 | 43 | -0.94 | -0.42 | +0.97 | no |
| enemy_speed | 45 | 33 | 22 | -1.00 | -0.72 | +0.95 | no |
| enemy_aggro | 42 | 35 | 23 | -0.94 | -0.75 | +0.97 | no |
| hazard_density | 15 | 33 | 52 | -0.11 | -0.41 | +0.95 | no |
| resource_scarcity | 41 | 14 | 46 | -1.00 | -0.75 | +0.80 | no |
| room_count | 30 | 14 | 56 | -1.00 | -0.17 | +0.86 | no |
| archetype_complexity | 39 | 0 | 61 | -1.00 | -0.39 | +0.75 | no |

Any dominated dimension: **False**

## Acceptance criteria (exported policy)

| criterion | result | number |
|---|---|---|
| (a) no dim within 5% of a bound on all six profiles | PASS | pinned dims: none; closest dim extremes in table above |
| (b) learned sigma < 0.7 on all 8 dims | PASS | max sigma = 0.280 (seed 0) |
| (c) Spearman(skill, challenge) > 0.8 | PASS | rho(score) = 1.000, rho(load) = 1.000 |
| (d) beats random-init, heuristic, static on reward AND pacing on >= 5/6 profiles | PASS | random-init (10): 6/6, heuristic: 6/6, static +8%: 6/6 |
| (e) mean per-floor |delta action| <= 0.35 | PASS | mean over profiles = 0.051, worst profile = 0.054 |

(f) pytest and ruff results, and the weights file size, are reported in the commit / PR description.

## Ablation: no balance term (BALANCE_W = 0, one seed, 700k steps, 30 episodes/profile)

Mean position in range (HP, Dmg, Speed, Aggro, Hazard, Scarcity, Rooms, c) and pacing error. Nothing pins without the balance prior (earlier iterations that pinned hazard at max and damage at min did so because of the clipped-mean gradient problem fixed by TrainWrapper, not because of the balance prior).

| profile | HP | Dmg | Speed | Aggro | Hazard | Scarcity | Rooms | c | pace err |
|---|---|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.09 | 0.37 | 0.36 | 0.58 | 0.81 | 0.41 | 0.30 | 0.36 | 0.122 |
| novice (0.20) | 0.14 | 0.39 | 0.37 | 0.57 | 0.81 | 0.41 | 0.35 | 0.40 | 0.121 |
| mid (0.45) | 0.31 | 0.46 | 0.41 | 0.52 | 0.81 | 0.42 | 0.54 | 0.54 | 0.116 |
| skilled (0.70) | 0.52 | 0.53 | 0.46 | 0.46 | 0.80 | 0.44 | 0.74 | 0.70 | 0.109 |
| expert (0.80) | 0.59 | 0.56 | 0.48 | 0.44 | 0.80 | 0.44 | 0.81 | 0.75 | 0.115 |
| expert (0.90) | 0.65 | 0.58 | 0.49 | 0.42 | 0.79 | 0.45 | 0.87 | 0.80 | 0.117 |
