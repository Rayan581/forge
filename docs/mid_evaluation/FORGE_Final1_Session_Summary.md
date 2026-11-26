# FORGE — Final-1 Work Session Summary

Date: 4 Nov 2026 · Repo: `Rayan581/forge` (private) · Local: `X:\FAST Tasks\FYP`
State at the end of this session: **`origin/main` = `c7a254f`** (all work below is on `main`).

---

## 1. What you asked for

1. Look at the repo, work out the planned work for **FYP-1 Final (Weeks 11–14)**, and plan it.
2. Implement the Final-1 task list, one subagent per independent step, in parallel, then verify against acceptance criteria and combine:
   - new enemy types
   - SQLite migration
   - unified room tiles (healing room, purple exit portal room no longer re-tint every tile)
   - exit room placed far from the start room
   - dynamic room sizes
   - your downloaded asset packs for characters, rooms, tiles, walls, items, with animations
   - skeleton for the player, skeleton for crawlers, priest for the pyromancer
   - pixel-art sprites for the new enemy types
   - fix the simulator and retrain PPO
3. Review the teammate's `hellsing` branch (SQLite work), merge it with the rest, fix issues, load everything locally.
4. Explain why you only saw 3 enemy types in floors 1–4.
5. Give the merge-to-main command, fix the flagged issues, say what to do next.
6. Latest: asked whether you can train the policy on your own PC, then asked me to push the latest verified work to `main`.

---

## 2. What was built

### Gameplay
- **5 enemy archetypes** (`Enemy.gd`): Melee Crawler, Ranged Pyromancer, Heavy Brute, Agile Skirmisher, Swarmer (a swarmer slot spawns 3 bodies). Each has its own states, multipliers, telegraphs and sprites.
- **PPO action is now 8-dim**: `[health, damage, speed, aggro, hazard, scarcity, room_count, archetype_complexity]`. Observation stays 8-dim.
- **Archetype mix** (`DifficultyManager.compute_archetype_mix`): `c=(a7+1)/2; logit=-|LEVELS[i]-c|/0.25; p = 0.85*softmax + 0.15/5`, LEVELS `[0, 0.5, 0.9, 0.7, 0.25]` in the order crawler, pyromancer, brute, skirmisher, swarmer.
- **Calibration floors 1–5** use fixed, gradual archetype mixes; PPO takes over from floor 6. This is why you saw only 3 enemy types on floors 1–4.
- **Map generation**: dynamic room sizes (per-room `RoomData.size`), exit room chosen by BFS depth so it is far from the start, per-door corridors, tileset floors/walls/torches, no more whole-room re-tinting.
- **Sprites/animation**: skeleton player, skeleton crawler, priest pyromancer, CC0 0x72 art for Brute/Skirmisher/Swarmer (`assets/sprites/enemies/` with `manifest.json` + `CREDITS.md`), flask pickups, spike hazards. `tools/build_sprite_frames.py` regenerates the frames.

### Telemetry (SQLite)
- Merged your teammate's `hellsing` work with the Final-1 telemetry design; the Final-1 design was kept.
- `schema.sql` / `queries.sql` are the **single source of truth** for Godot and Python. `v_corpus` view gives the Judge corpus.
- Godot side: `godot-sqlite` (2shady4u) GDExtension if installed, otherwise JSON fallback.
- Python side (`ml_spike/telemetry_data/telemetry_db.py`): idempotent `sync_from_game_db`, `get_judge_training_data` (14 settings → 4 targets; incomplete rows skipped and counted), `export_corpus_csv`. Missing values stay NULL, never invented.

### Simulator + policy
- **Sim-v2**: reflex/tactics skill axes, abrupt skill shifts, smoothness reward, out-of-range penalty.
- **Sim-v3** (this session's last change): fixed the problem that enemy damage and resource scarcity barely reacted to player skill. Added a hit-severity prior (damage, conditioned on reflex) and a recoverability prior (scarcity, conditioned on tactics). Retrained 3 seeds × 1M steps.
- Independently re-verified with fresh seeds (0.10 vs 0.90 skill): **damage +0.26, scarcity +0.53** of range (target ≥ 0.15). Pacing error within 0.017 of sim-v2 (limit 0.03). Previous policy kept as `policy_weights_v2.json`.

### Bug found and fixed
- `DefenseOverlay.gd` re-emitted slider signals while syncing, so only HP appeared to adapt. Fixed with `set_value_no_signal`; regression test `tests/test_overlay_sync.gd`.

---

## 3. Verification status (before the push)

| Check | Result |
|---|---|
| Godot suites (10 in CI list) | all PASS |
| Godot parse check (`--headless --quit`) | no SCRIPT ERROR / Parse Error |
| `pytest ml_spike/tests` | 145 passed |
| `ruff 0.4.10` check + format (CI scope `ml_spike/`) | clean |

Not yet verified anywhere: the SQLite code has **never run against the real godot-sqlite plugin** (only the JSON fallback and Python's `sqlite3`).

---

## 4. Branches and delivery

- `main` (remote) = `c7a254f`: Final-1 work + `hellsing` + post-merge cleanup + sim-v3.
- Local-only leftovers on my side: `wip/sim-v3-snapshot` (superseded; do not train from it), worktrees under `/home/claude/wt/`.
- Bundles written earlier to `X:\FAST Tasks\FYP`: `forge-final1.bundle`, `forge-main-combined.bundle`, `forge-fixes-wip.bundle`. All are superseded now that `main` is pushed.

---

## 5. Next steps for you

### Right now
1. **Update your local project**
   ```
   cd "X:\FAST Tasks\FYP"
   git checkout -- godot_prototype/assets/tiles/torch    # only if Godot modified those .import files again
   git checkout main
   git pull origin main
   git branch -D wip/sim-v3-snapshot                      # optional cleanup
   ```
2. **Check GitHub Actions on `main`.** Look at the godot-sqlite v4.9 install step and the real-SQLite test step in particular, since they have never run before. If it fails, send me the log.
3. **Play floors 1–8** in the game. Confirm: five archetypes appear after calibration, the exit room is far away, room sizes vary, from floor 6 damage/scarcity visibly respond to how you play.
4. **Install godot-sqlite locally** (see `godot_prototype/addons/README_SQLITE.md`), run the game once, then run `python ml_spike\telemetry_data\telemetry_db.py` to confirm the DB syncs. Commit the addon if the team wants it in the repo.

### Optional: train the policy yourself
```
python -m venv .venv ; .venv\Scripts\activate
pip install -r ml_spike\requirements.txt
python ml_spike\train_ppo_difficulty.py --seed 0 --timesteps 600000 --out policy_weights_test.json
```
- CPU is the right choice (tiny network, simulator-bound); the GPU will not help.
- Run several `--seed` values in parallel if you have cores.
- Do not overwrite `godot_prototype/ai/policy_weights.json` until the result passes the checks in `ml_spike/analysis/results_sim_v3.md` (damage and scarcity differ ≥ 0.15 between skill 0.10 and 0.90, pacing error not worse than sim-v2 by more than 0.03).

### Remaining Final-1 work (not started)
5. **Consent screen + post-floor difficulty-rating UI.** None exists yet; needed for a study corpus (`--consented-only` export depends on it).
6. **Ship a playtest build and collect 25+ sessions** of real telemetry.
7. **BSP baseline generator** (the comparison baseline for the evaluation).
8. **Judge model** (LightGBM/XGBoost, target MAE ≤ 0.15) **+ TreeSHAP** explanations, trained on the playtest corpus.
9. **Final-1 report** (results, sim-v3 findings in `results_sim_v3.md`, telemetry design).

### Decisions for you
- **Brutes earlier in calibration?** Currently Brutes only show up once PPO takes over. If you want them sooner, edit `CALIBRATION_LEVELS` `archetype_mix` in `DifficultyManager.gd` and update `tests/test_archetype_mix.gd` to match.
- **Plan gaps for FYP-2:** the Chapter 10 FYP-2 sprints are missing the profiling engine and PPO fine-tuning on real data. Worth adding before the Mid evaluation.

---

## 6. Things to remember

- Ruff is pinned to **0.4.10** in CI. Use `python -m ruff` locally (a newer ruff may report false formatting errors).
- `godot_prototype/ai/jh.py` and the extra `policy_weights_2.json` / `policy_weights_working.json` are pre-existing and untouched; `jh.py` has ruff errors but CI does not check that folder.
- Scarcity is a coarse lever: the generator gives 2 treasure rooms only at scarcity ≤ 0.2, otherwise 1, and high hazard turns many rooms into hazard rooms with no pickups. Expect that when interpreting playtest results.
