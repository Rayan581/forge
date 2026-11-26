# Simulator v3 — evaluation of the personalised PPO policy

Protocol: 100 paired episodes x 30 levels per profile (episode i uses seed 10000+i for every policy, so all policies face the same player trajectory: skill drift + random abrupt shifts of the default population, and the same noise stream family).  `trained (exported)` is `godot_prototype/ai/policy_weights.json` run through the NumPy mirror of PPOPolicy.gd (seed 2); `seed k` rows are the SB3 checkpoints of the three training runs; `sim-v2 policy` is the previously shipped `policy_weights_v2.json` run on the v3 simulator (reference only).  Pacing error = |t_room - 7.5 s| / 7.5 s.

## Diagnosis: why sim-v2 left enemy_damage and resource_scarcity flat

Measured on the shipped sim-v2 policy: for skills 0.1 / 0.5 / 0.9 the per-floor reward was re-evaluated with 150 common-random-number floors while one action dimension at a time was moved by +-0.3 around the policy's mean action (the numbers below are the reward change; dT = change in seconds per room; dGross = change in damage ratio).

| skill | dim | dReward (-0.3 / +0.3) | dT (s/room) | dGross |
|---|---|---|---|---|
| 0.1 | enemy_health | +0.074 / -0.218 | -1.08 / +1.54 | -0.080 / +0.116 |
| 0.1 | enemy_damage | +0.023 / -0.041 | -0.22 / +0.22 | -0.059 / +0.059 |
| 0.1 | resource_scarcity | +0.012 / -0.015 | -0.13 / +0.13 | 0.000 / 0.000 |
| 0.5 | enemy_damage | +0.002 / -0.018 | -0.19 / +0.19 | -0.046 / +0.046 |
| 0.5 | resource_scarcity | +0.001 / -0.006 | -0.11 / +0.11 | 0.000 / 0.000 |
| 0.9 | enemy_damage | -0.026 / +0.013 | -0.17 / +0.17 | -0.033 / +0.033 |
| 0.9 | resource_scarcity | -0.009 / +0.004 | -0.10 / +0.10 | 0.000 / 0.000 |

Findings:

1. **The reward only "sees" three scalars** (time per room, damage ratio, deaths) while the policy has eight levers, and deaths are essentially always 0. Damage ratio and pace are already pinned by the flow/pacing terms to skill-independent targets (0.35, 7.5 s/room).  Enemy HP changes both scalars much more strongly (about 4-5 times the effect of damage on reward) and hazard/aggro/speed also trade pace against damage, so *any* damage level can be compensated by HP/hazard.  The optimum is therefore a flat ridge in the damage direction and the balance prior 0.15 * mean(a^2) simply parks the unneeded lever near 0 (position 0.5).  A constant-action optimiser on the sim-v2 reward (differential evolution, 8 dims, 60 CRN floors) confirms this: best damage position 0.59 at skill 0.10 and 0.53 at 0.90.
2. **Scarcity has almost no physical effect** in sim-v2: it does not change the damage ratio at all (dGross = 0.000), it moves time by only +-0.1 s/room through the caution term, and its main effect (healing, via net damage) only matters for `deaths`, which are ~0. Its reward gradient is 0.004-0.015 per 0.3 step, 5-20 times weaker than damage, so noise and the balance prior decide (positions 0.47-0.48 for every profile; constant-action optimum 0.41 at skill 0.10 vs 0.56 at 0.90 is a weak, noisy signal that PPO does not resolve).  Two mirrored properties of the game make this physical, not an artefact: DungeonGenerator.gd gives 2 treasure rooms for scarcity <= 0.2 and 1 otherwise (a step, so most of the range changes supply by well under one pickup), and the high hazard density the policy prefers turns most rooms into hazard rooms that carry no pickups.
3. **Neither lever had a skill-dependent effect.** Damage and scarcity entered the physics identically for every player (only the *size* of the effect scaled with the hit probability), so the *relative* cost of moving them never changed with skill and there was no reason for the optimum to move.
4. Hazard sat at 0.70-0.78 for the same reason (cheap, always available lever to trade pace against damage).

## What changed in sim-v3

Principle: give damage and scarcity (a) a distinct, skill-dependent physical effect on a *different* skill axis than the other levers and (b) a skill-conditioned experience measure with its own reward term, using the same device sim-v2 already uses for room count (ROOM_W) and archetype complexity (COMPLEX_W).  **(b) is a design prior, not a physical law**; it is stated as such, and its weight and band are exposed as constants.  The weights are small enough that pacing (the dominant term) is unchanged: see criterion 3.

| constant | sim-v2 | sim-v3 | role |
|---|---|---|---|
| `CAUTION_SCAR` | 0.18 | 0.30 | pace slowdown at max scarcity (before the skill factor) |
| `CAUTION_REFLEX_SLOPE` | - | 1.2 | damage caution factor 1 + 1.2 (0.5 - reflex): low-reflex players slow down more under hard hits (1.48 at reflex 0.1, 0.52 at 0.9) |
| `CAUTION_TACTICS_SLOPE` | - | 1.6 | scarcity caution factor 1 + 1.6 (0.5 - tactics): poor resource managers slow down more when healing is rare |
| `HEAL_USE` | 0.85 const | 0.60 + 0.40 tactics (`HEAL_USE_BASE/GAIN`) | usable fraction of the healing supply |
| `PLAYER_HP` | - | 100 | Player.max_health; severity of one hit = damage * mix_dmg_mult / 100 |
| `SEV_LO`, `SEV_HI`, `SEV_W` | - | 0.10, 0.35, 0.40 | **design prior (damage, reflex):** reward -= 0.40 * abs(sev - sev*(reflex)) / 0.30 with sev* = 0.10 + 0.25 reflex.  Low-reflex players cannot avoid hits, so each hit should be small; high-reflex players are rarely hit, so hits must carry weight to register as a threat |
| `COVER_LO`, `COVER_HI`, `COVER_W` | - | 1.4, 3.6, 0.80 | **design prior (scarcity, tactics):** cover = usable healing supply / expected damage (`expected_pickups` mirrors DungeonGenerator.gd); reward -= 0.80 * abs(ln(cover / cover*)) with cover* = 1.4 + 2.2 (1 - tactics).  Good resource managers are fine on a lean supply, poor ones need a generous one |

The hit-severity prior is conditioned on the *reflex* axis and the recoverability prior on the *tactics* axis; both axes are the simulated player's hidden state (reflex = skill + b, tactics = skill - b), exactly like the other two priors, and are never given to the policy (the 8-dim observation and the action contract are unchanged).  The learned damage/scarcity/hazard positions are *not* "set = skill": the priors compete with the flow, pacing and balance terms, which is why the learned spread is smaller than the priors' targets.


## Iteration history (what was tried before the shipped configuration)

1. First full run (3 seeds x 1M steps) with `COVER_HI = 2.6`: damage spread (0.90 minus 0.10) +0.24 to +0.26 on all seeds, hazard about +0.45, but scarcity spread only **+0.14 (seed 0), +0.25 (seed 1), +0.18 (seed 2)**.  Validation reward picked seed 0 (0.5701 vs 0.5699 vs 0.5665, a statistical tie), which would have failed the 0.15 criterion by 0.01.  Cause: for a novice the cover prior is already satisfied at scarcity ~0.3-0.5 (cover 2.2-2.4 vs target 2.48), so there was no reason to move to the generous side of the generator's supply step at scarcity 0.2.  Rather than pick a seed by the criterion, the novice-side target was raised (`COVER_HI` 2.6 -> 3.6, i.e. a poor resource manager wants about 3.6 floors' worth of healing) and all three seeds were retrained; the shipped numbers are from that second full run (selection rule unchanged: best validation reward).
2. Pilots (500-600k steps, 2 seeds) were used only to choose `COVER_W` (0.30 -> 0.60 -> 0.80) and `CAUTION_SCAR` / `CAUTION_TACTICS_SLOPE` (0.18 / 1.2 -> 0.30 / 1.6); the first pilot with the original weights had scarcity spreads of only +0.15 to +0.17.

## Reward / level (higher is better)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | sim-v2 policy | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.473 | 0.454 | 0.466 | 0.473 | 0.061 | -1.434 | -0.158 | -3.258 |
| novice (0.20) | 0.522 | 0.510 | 0.521 | 0.522 | 0.217 | -0.917 | -0.029 | -2.651 |
| mid (0.45) | 0.562 | 0.563 | 0.560 | 0.562 | 0.429 | 0.187 | 0.231 | -1.177 |
| skilled (0.70) | 0.550 | 0.544 | 0.539 | 0.550 | 0.520 | 0.093 | 0.152 | -0.391 |
| expert (0.80) | 0.546 | 0.534 | 0.534 | 0.546 | 0.419 | -0.115 | 0.074 | -0.371 |
| expert (0.90) | 0.531 | 0.532 | 0.530 | 0.531 | 0.340 | -0.309 | -0.031 | -0.452 |

## Pacing error |t_room - target| / target (lower is better)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | sim-v2 policy | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.130 | 0.134 | 0.130 | 0.130 | 0.159 | 0.871 | 0.378 | 1.499 |
| novice (0.20) | 0.134 | 0.134 | 0.128 | 0.134 | 0.141 | 0.658 | 0.327 | 1.287 |
| mid (0.45) | 0.132 | 0.127 | 0.126 | 0.132 | 0.124 | 0.259 | 0.206 | 0.722 |
| skilled (0.70) | 0.122 | 0.121 | 0.122 | 0.122 | 0.122 | 0.204 | 0.148 | 0.348 |
| expert (0.80) | 0.124 | 0.121 | 0.124 | 0.124 | 0.129 | 0.257 | 0.150 | 0.297 |
| expert (0.90) | 0.125 | 0.120 | 0.124 | 0.125 | 0.136 | 0.305 | 0.171 | 0.284 |

## Deaths / level (lower is better)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | sim-v2 policy | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.017 | 0.000 | 0.717 |
| novice (0.20) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.007 | 0.000 | 0.532 |
| mid (0.45) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 0.000 | 0.175 |
| skilled (0.70) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.037 |
| expert (0.80) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.019 |
| expert (0.90) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.010 |

## Mean per-floor |delta action| (mean over the 8 dims, floors 2-30)

| profile | trained (exported) | seed 0 | seed 1 | seed 2 | sim-v2 policy | random-init (10) | heuristic | static +8% |
|---|---|---|---|---|---|---|---|---|
| novice (0.10) | 0.048 | 0.050 | 0.048 | 0.048 | 0.047 | 0.000 | 0.047 | 0.021 |
| novice (0.20) | 0.050 | 0.053 | 0.051 | 0.050 | 0.049 | 0.000 | 0.047 | 0.021 |
| mid (0.45) | 0.059 | 0.061 | 0.063 | 0.059 | 0.053 | 0.000 | 0.039 | 0.021 |
| skilled (0.70) | 0.065 | 0.066 | 0.071 | 0.065 | 0.056 | 0.000 | 0.031 | 0.021 |
| expert (0.80) | 0.063 | 0.064 | 0.069 | 0.063 | 0.053 | 0.000 | 0.028 | 0.021 |
| expert (0.90) | 0.060 | 0.060 | 0.065 | 0.060 | 0.053 | 0.000 | 0.027 | 0.021 |

## Trained (exported) vs baselines — paired comparison

| profile | baseline | reward diff (trained - base) | pacing-error diff | trained better on both |
|---|---|---|---|---|
| novice (0.10) | random-init (10) | +1.907 (p=2.6e-54) | -0.741 (p=4.3e-46) | yes |
| novice (0.10) | heuristic | +0.631 (p=2.0e-67) | -0.249 (p=6.8e-59) | yes |
| novice (0.10) | static +8% | +3.731 (p=2.7e-69) | -1.369 (p=1.6e-73) | yes |
| novice (0.20) | random-init (10) | +1.439 (p=1.7e-46) | -0.523 (p=2.4e-39) | yes |
| novice (0.20) | heuristic | +0.551 (p=5.4e-65) | -0.192 (p=3.9e-50) | yes |
| novice (0.20) | static +8% | +3.173 (p=8.9e-64) | -1.152 (p=9.4e-65) | yes |
| mid (0.45) | random-init (10) | +0.375 (p=7.3e-17) | -0.127 (p=3.3e-14) | yes |
| mid (0.45) | heuristic | +0.331 (p=1.5e-49) | -0.073 (p=2.0e-24) | yes |
| mid (0.45) | static +8% | +1.739 (p=6.2e-45) | -0.589 (p=1.6e-40) | yes |
| skilled (0.70) | random-init (10) | +0.457 (p=5.0e-36) | -0.082 (p=1.6e-25) | yes |
| skilled (0.70) | heuristic | +0.398 (p=2.4e-49) | -0.025 (p=1.2e-12) | yes |
| skilled (0.70) | static +8% | +0.940 (p=2.9e-45) | -0.226 (p=8.5e-25) | yes |
| expert (0.80) | random-init (10) | +0.661 (p=8.6e-46) | -0.133 (p=1.6e-40) | yes |
| expert (0.80) | heuristic | +0.473 (p=1.1e-54) | -0.026 (p=3.3e-18) | yes |
| expert (0.80) | static +8% | +0.917 (p=3.0e-55) | -0.172 (p=7.9e-25) | yes |
| expert (0.90) | random-init (10) | +0.840 (p=2.8e-52) | -0.180 (p=2.4e-49) | yes |
| expert (0.90) | heuristic | +0.562 (p=1.7e-57) | -0.045 (p=1.5e-32) | yes |
| expert (0.90) | static +8% | +0.983 (p=1.0e-70) | -0.159 (p=2.5e-30) | yes |

Profiles (of 6) on which the trained policy has the better mean on BOTH reward and pacing error: vs random-init (10): **6/6**, vs heuristic: **6/6**, vs static +8%: **6/6**

## Mean parameter value chosen per profile (trained, exported)

| profile | HP | Dmg | Speed | Aggro | Hazard | Scarcity | Rooms | a7 (c) |
|---|---|---|---|---|---|---|---|---|
| *range* | *20-120* | *5-50* | *60-220* | *100-450* | *0.05-0.8* | *0.1-0.9* | *5-9* | *-1..1* |
| novice (0.10) | 22.7 | 20.6 | 133 | 242 | 0.36 | 0.31 | 6.1 | -0.36 (0.32) |
| novice (0.20) | 24.9 | 21.4 | 135 | 242 | 0.39 | 0.34 | 6.3 | -0.29 (0.35) |
| mid (0.45) | 39.7 | 24.7 | 144 | 245 | 0.52 | 0.46 | 7.0 | +0.00 (0.50) |
| skilled (0.70) | 64.4 | 28.8 | 156 | 251 | 0.67 | 0.61 | 8.0 | +0.37 (0.69) |
| expert (0.80) | 72.6 | 30.0 | 159 | 254 | 0.71 | 0.65 | 8.2 | +0.49 (0.74) |
| expert (0.90) | 79.9 | 31.0 | 162 | 256 | 0.74 | 0.69 | 8.5 | +0.58 (0.79) |

Mean archetype mix produced by that a7 (crawler, pyromancer, brute, skirmisher, swarmer):

| profile | Melee Crawler | Ranged Pyromancer | Heavy Brute | Agile Skirmisher | Swarmer |
|---|---|---|---|---|---|
| novice (0.10) | 0.16 | 0.25 | 0.08 | 0.13 | 0.38 |
| novice (0.20) | 0.15 | 0.28 | 0.08 | 0.15 | 0.34 |
| mid (0.45) | 0.09 | 0.36 | 0.12 | 0.23 | 0.20 |
| skilled (0.70) | 0.06 | 0.24 | 0.23 | 0.36 | 0.11 |
| expert (0.80) | 0.05 | 0.21 | 0.29 | 0.36 | 0.10 |
| expert (0.90) | 0.05 | 0.18 | 0.35 | 0.34 | 0.09 |

## Criterion (a): per-profile mean position inside each range (0 = min bound, 1 = max bound)

| dim | novice (0.10) | novice (0.20) | mid (0.45) | skilled (0.70) | expert (0.80) | expert (0.90) | within 5% of a bound on all 6? |
|---|---|---|---|---|---|---|---|
| enemy_health | 0.03 | 0.05 | 0.20 | 0.44 | 0.53 | 0.60 | ok |
| enemy_damage | 0.35 | 0.36 | 0.44 | 0.53 | 0.56 | 0.58 | ok |
| enemy_speed | 0.46 | 0.47 | 0.53 | 0.60 | 0.62 | 0.64 | ok |
| enemy_aggro | 0.41 | 0.41 | 0.42 | 0.43 | 0.44 | 0.45 | ok |
| hazard_density | 0.41 | 0.46 | 0.63 | 0.83 | 0.89 | 0.93 | ok |
| resource_scarcity | 0.26 | 0.30 | 0.46 | 0.63 | 0.69 | 0.74 | ok |
| room_count | 0.31 | 0.35 | 0.51 | 0.73 | 0.80 | 0.86 | ok |
| archetype_complexity | 0.32 | 0.35 | 0.50 | 0.69 | 0.74 | 0.79 | ok |

## Criterion (b): learned action standard deviation (exp(log_std))

| run | enemy_health | enemy_damage | enemy_speed | enemy_aggro | hazard_density | resource_scarcity | room_count | archetype_complexity | max |
|---|---|---|---|---|---|---|---|---|---|
| seed 0 | 0.11 | 0.12 | 0.21 | 0.23 | 0.14 | 0.18 | 0.14 | 0.16 | 0.23 |
| seed 1 | 0.11 | 0.12 | 0.21 | 0.24 | 0.13 | 0.18 | 0.15 | 0.16 | 0.24 |
| seed 2 | 0.11 | 0.12 | 0.21 | 0.23 | 0.13 | 0.18 | 0.15 | 0.16 | 0.23 |

## Criterion (c): challenge chosen vs initial skill (trained, exported)

| profile | game difficulty score (0-100) | simulator load index |
|---|---|---|
| novice (0.10) | 30.4 | 0.470 |
| novice (0.20) | 32.4 | 0.522 |
| mid (0.45) | 41.8 | 0.826 |
| skilled (0.70) | 54.8 | 1.450 |
| expert (0.80) | 58.8 | 1.706 |
| expert (0.90) | 62.2 | 1.978 |

Spearman rho (initial skill vs mean difficulty score) = **1.000**; vs simulator load index = **1.000**.

## Abrupt-shift scenario

Skill drops by 0.30 at level 10 (0-based; the first affected floor is floor 10) and recovers (+0.30) at level 20; no random shifts; 100 paired episodes.  The table gives the number of floors from the shift (the shifted floor counts as 1) until the cross-episode mean pacing error is <= 0.15 on two consecutive floors (`never` = not within 10 floors).

| skill path | policy | mean err floors 3-9 | err on drop floor | floors to recover after drop | err on recovery floor | floors to re-settle after recovery | deaths on drop floor |
|---|---|---|---|---|---|---|---|
| 0.45 -> 0.15 -> 0.45 | trained (exported) | 0.121 | 0.362 | 2 | 0.340 | 4 | 0.00 |
| 0.45 -> 0.15 -> 0.45 | heuristic | 0.222 | 0.665 | never | 0.187 | 2 | 0.00 |
| 0.45 -> 0.15 -> 0.45 | static +8% | 0.316 | 1.294 | never | 0.898 | never | 0.10 |
| 0.45 -> 0.15 -> 0.45 | random-init (seed 1000) | 0.216 | 0.827 | never | 0.157 | 3 | 0.00 |
| 0.70 -> 0.40 -> 0.70 | trained (exported) | 0.107 | 0.440 | 2 | 0.377 | 4 | 0.00 |
| 0.70 -> 0.40 -> 0.70 | heuristic | 0.114 | 0.374 | never | 0.249 | never | 0.00 |
| 0.70 -> 0.40 -> 0.70 | static +8% | 0.125 | 0.555 | never | 0.322 | never | 0.00 |
| 0.70 -> 0.40 -> 0.70 | random-init (seed 1000) | 0.154 | 0.285 | never | 0.201 | never | 0.00 |
| 0.80 -> 0.50 -> 0.80 | trained (exported) | 0.110 | 0.395 | 2 | 0.387 | 4 | 0.00 |
| 0.80 -> 0.50 -> 0.80 | heuristic | 0.132 | 0.306 | 9 | 0.262 | never | 0.00 |
| 0.80 -> 0.50 -> 0.80 | static +8% | 0.193 | 0.352 | never | 0.173 | never | 0.00 |
| 0.80 -> 0.50 -> 0.80 | random-init (seed 1000) | 0.252 | 0.148 | 1 | 0.300 | never | 0.00 |

## Simulator check 1: every action dimension makes the floor harder (others at 0)

| action dim | skill | t/room @-1 | t/room @+1 | gross dmg @-1 | gross dmg @+1 | deaths @-1 | deaths @+1 | direction ok |
|---|---|---|---|---|---|---|---|---|
| enemy_health | 0.2 | 8.19 | 18.28 | 0.254 | 0.991 | 0.00 | 0.04 | yes |
| enemy_health | 0.5 | 5.77 | 11.77 | 0.147 | 0.578 | 0.00 | 0.00 | yes |
| enemy_health | 0.8 | 3.85 | 7.87 | 0.081 | 0.259 | 0.00 | 0.00 | yes |
| enemy_damage | 0.2 | 11.67 | 14.86 | 0.203 | 1.042 | 0.00 | 0.07 | yes |
| enemy_damage | 0.5 | 8.03 | 9.56 | 0.133 | 0.545 | 0.00 | 0.00 | yes |
| enemy_damage | 0.8 | 5.52 | 6.15 | 0.079 | 0.216 | 0.00 | 0.00 | yes |
| enemy_speed | 0.2 | 12.25 | 14.15 | 0.609 | 0.624 | 0.00 | 0.00 | yes |
| enemy_speed | 0.5 | 7.73 | 9.67 | 0.275 | 0.375 | 0.00 | 0.00 | yes |
| enemy_speed | 0.8 | 5.14 | 6.50 | 0.112 | 0.180 | 0.00 | 0.00 | yes |
| enemy_aggro | 0.2 | 13.20 | 13.24 | 0.552 | 0.672 | 0.00 | 0.00 | yes |
| enemy_aggro | 0.5 | 8.49 | 8.99 | 0.267 | 0.393 | 0.00 | 0.00 | yes |
| enemy_aggro | 0.8 | 5.61 | 6.04 | 0.113 | 0.181 | 0.00 | 0.00 | yes |
| hazard_density | 0.2 | 12.87 | 13.61 | 0.553 | 0.762 | 0.00 | 0.01 | yes |
| hazard_density | 0.5 | 8.19 | 9.46 | 0.240 | 0.491 | 0.00 | 0.00 | yes |
| hazard_density | 0.8 | 5.37 | 6.49 | 0.079 | 0.277 | 0.00 | 0.00 | yes |
| resource_scarcity | 0.2 | 10.24 | 14.93 | 0.526 | 0.623 | 0.00 | 0.00 | yes |
| resource_scarcity | 0.5 | 7.16 | 9.56 | 0.284 | 0.339 | 0.00 | 0.00 | yes |
| resource_scarcity | 0.8 | 5.04 | 6.10 | 0.125 | 0.147 | 0.00 | 0.00 | yes |
| room_count | 0.2 | 12.37 | 14.19 | 0.408 | 0.885 | 0.00 | 0.03 | yes |
| room_count | 0.5 | 8.20 | 9.43 | 0.214 | 0.490 | 0.00 | 0.00 | yes |
| room_count | 0.8 | 5.49 | 6.19 | 0.092 | 0.206 | 0.00 | 0.00 | yes |
| archetype_complexity | 0.2 | 12.48 | 15.35 | 0.502 | 0.885 | 0.00 | 0.01 | yes |
| archetype_complexity | 0.5 | 8.02 | 10.03 | 0.239 | 0.492 | 0.00 | 0.00 | yes |
| archetype_complexity | 0.8 | 5.42 | 6.58 | 0.109 | 0.193 | 0.00 | 0.00 | yes |

All dimensions monotone in the harder direction: **True**

## Simulator check 2: no parameter is dominated

For each dim, 16 random contexts (other dims ~ U(-0.7, 0.7)) x 6 skills: the grid value (9 points) that maximises the immediate per-floor reward (pacing + deaths + flow terms; smoothness excluded).  A dim is dominated if one bound is optimal in >95 % of contexts.

| action dim | % contexts optimum at -1 | % at +1 | % interior | mean optimum @skill 0.10 | @0.45 | @0.90 | dominated? |
|---|---|---|---|---|---|---|---|
| enemy_health | 42 | 27 | 31 | -1.00 | -0.80 | +0.97 | no |
| enemy_damage | 39 | 6 | 55 | -1.00 | -0.59 | +0.58 | no |
| enemy_speed | 48 | 43 | 9 | -1.00 | -0.92 | +1.00 | no |
| enemy_aggro | 48 | 43 | 9 | -1.00 | -0.89 | +0.98 | no |
| hazard_density | 27 | 29 | 44 | -0.61 | -0.83 | +1.00 | no |
| resource_scarcity | 41 | 44 | 16 | -1.00 | -0.75 | +1.00 | no |
| room_count | 47 | 12 | 41 | -1.00 | -0.86 | +0.44 | no |
| archetype_complexity | 45 | 2 | 53 | -1.00 | -0.89 | +0.69 | no |

Any dominated dimension: **False**

## Acceptance criteria (exported policy)

| criterion | result | number |
|---|---|---|
| (a) no dim within 5% of a bound on all six profiles | PASS | pinned dims: none; closest dim extremes in table above |
| (b) learned sigma < 0.7 on all 8 dims | PASS | max sigma = 0.231 (seed 2) |
| (c) Spearman(skill, challenge) > 0.8 | PASS | rho(score) = 1.000, rho(load) = 1.000 |
| (d) beats random-init, heuristic, static on reward AND pacing on >= 5/6 profiles | PASS | random-init (10): 6/6, heuristic: 6/6, static +8%: 6/6 |
| (e) mean per-floor |delta action| <= 0.35 | PASS | mean over profiles = 0.058, worst profile = 0.065 |
| 1. enemy_damage and resource_scarcity: |pos(0.90) - pos(0.10)| >= 0.15 | PASS | damage +0.231, scarcity +0.476 (hazard +0.515, reported only) |
| 3. pacing error not worse than sim-v2 by more than 0.03 on every profile | PASS | diff per profile: +0.002, +0.007, +0.017, +0.010, +0.008, +0.005 (worst +0.017) |

(f) pytest and ruff results, and the weights file size, are reported in the commit / PR description.  Criteria (a)-(e) are the sim-v2 criteria; 1 and 3 are the sim-v3 additions.
