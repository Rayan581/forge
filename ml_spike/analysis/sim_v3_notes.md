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
