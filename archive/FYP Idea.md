## Summary: FYP Direction

**Game type**: Top-down 2D (not platformer) — matches your original proposal's language and metrics (exploration rate, treasure collection, enemy encounters), and aligns with existing PCGRL literature (`gym-pcgrl`'s Zelda-style representation) as a base to build from.

**Best-fit concept**: Room-based dungeon crawler with combat, closest to Option 1/3 hybrid — rooms connected by doors, cleared via combat, generated procedurally per player.

## Core Design Decision: Difficulty ≠ Enemy Count
Landed on structured, multi-attribute difficulty instead of scalar scaling:

- **Enemy attributes** (parameter vector, not fixed types): health, damage, speed, attack range/pattern, aggro radius, reaction delay, group behavior, special abilities
- **Non-combat factors**: terrain/hazards, cover/line-of-sight, resource scarcity (health/ammo), time pressure, objective type, room geometry
- Difficulty emerges from **combinations**, not any single stat — this is your strongest "no obvious solution" / CCP justification

## RL Pipeline
1. **Environment**: tile-grid PCGRL-style, but action space is structured (`position, enemy_archetype_params, terrain_modifier`) rather than flat tile placement
2. **Reward**: solvability (hard constraint) + predicted difficulty-fit (via a learned auxiliary regressor trained on session logs, not a hand-coded formula) + diversity + interaction-quality term
3. **Player profile**: embedding built from completion time, deaths, exploration rate, treasure rate, enemy encounters — updated after each session
4. **Conditioning**: profile vector fed into PPO policy so generation adapts per player
5. **Explainability**: expose the difficulty predictor's feature importance — this directly closes your own stated research gap (#5, "can't explain design choices") with minimal extra work

## FYP Guide Alignment — Still Needed Before Proposal
- Explicit CCP formulation naming Seoul Accord characteristics (conflicting requirements, no obvious solution, interdependence, ill-defined requirements are your strongest claims)
- Contribution statement in the guide's precise format
- Deployment target stated (where the playable build will run/install)
- At least one measurable non-functional requirement
- POC/technical spike — fork `gym-pcgrl`, train baseline PPO, show solvable output vs. random (mandatory for proposal defense, not optional)
- External component classification (PPO library = support; player-conditioning + difficulty predictor = your core contribution)
- SDG/thematic alignment
- Honest stakeholder statement (likely single group: players — fine to say so)

## Scope Reality Check (3 people, 2 semesters)
Commit to 3–4 enemy attributes + 2 environmental factors as core scope; document everything else (full behavior trees, more hazard types, richer objectives) as optional extensions. This keeps Final-1 realistic while still leaving a defensible, non-trivial RL problem.