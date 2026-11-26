# FORGE: hand-off brief for FYP-1 Final work (Judge model, then BSP baseline)

Paste this whole file into a new Claude chat that has access to the repo (`X:\FAST Tasks\FYP`, GitHub `Rayan581/forge`).
Do **Task A (Judge)** first. **Task B (BSP)** is independent and can run in a second chat in parallel.

---

## Ground rules (apply to both tasks)

- **Never push to GitHub.** Make the changes in the working tree, then give Ryn the exact `git add` / `git commit` / `git push` commands to run.
- Small change → say what to change; many files → deliver the changed files.
- Read before you write: `README.md`, `FORGE_Final1_Session_Summary.md` (in `docs/mid_evaluation/`), `ml_spike/analysis/results_sim_v3.md`, `ml_spike/analysis/sim_v3_notes.md`, `godot_prototype/PLAYTEST.md`.
- Godot **4.7.2**, GDScript. Python 3.12. CI = GitHub Actions: ruff **0.4.10** (`ruff.toml`, line length 100; run `python -m ruff check` and `python -m ruff format --check`), pytest in `ml_spike/tests`, and headless Godot tests listed in `.github/workflows/ci.yml`. **Every new test file must be added to that list.**
- Headless Godot test: `godot --headless --path godot_prototype --script res://tests/<name>.gd`, prints `[FORGE TEST] <name>: PASS` and exits 0/1. Follow `tests/test_static_baseline.gd` or `tests/test_playtest_flow.gd`.
- On Windows a godot-sqlite process can hang after it has finished. That is a known local issue, not a test failure.
- Be honest in all numbers. Never invent data; label synthetic vs real data everywhere.

---

## Task A: Empirical Judge model + TreeSHAP (do first)

### Why
FYP committee: "define and validate the judge model using empirical player data rather than primarily manually assigned difficulty weights" and "clear, measurable way of evaluating". The plan was moved from FYP-2 Mid into **FYP-1 Final**. Today the game's Judge is a hand-weighted linear proxy (`DifficultyManager.calculate_difficulty_score()` in Godot, `difficulty_score()` in `ml_spike/train_ppo_difficulty.py`).

### Data situation (important)
- Real data is tiny: a few sessions, ~10 floor rows, almost no consented sessions and no 1–5 ratings yet. **It cannot train a model.**
- Plan: **train on a synthetic corpus from the sim-v3 simulator, validate on the real rows**, and state plainly in the report that the 25+ player real corpus is FYP-2 work. The pipeline must already accept the real corpus with no code change (just a different input file).

### What exists
- `ml_spike/telemetry_data/telemetry_db.py`
  - `TelemetryDatabase.get_judge_training_data(consented_only=False)` → `features`, `targets`, `feature_names`, `target_names`. Skips NULL rows and `manual_override = 1` rows.
  - `JUDGE_FEATURES` (14): enemy_health, enemy_damage, enemy_speed, enemy_aggro, hazard_density, resource_scarcity, room_count, archetype_complexity, archetype_mix_0..4, enemy_count_scale.
  - `JUDGE_TARGETS`: completion_time, deaths, damage_taken, damage_exchange_ratio.
  - `sync_from_game_db(path)` merges a game `.db`; `ml_spike/analysis/export_telemetry.py db out.csv --consented-only` exports the corpus.
- `godot_prototype/telemetry/schema.sql`: `floors` table + `v_corpus` view. `floors.perceived_difficulty` = player's 1–5 rating (NULL if skipped).
- `ml_spike/train_ppo_difficulty.py`: `DungeonDifficultyEnv` (sim-v3). `_simulate(p, mix, count_scale)` returns time, deaths, dmg_ratio, challenge, skill, reflex, tactics, ... for a settings dict `p` and a simulated player. `difficulty_score(params)` is the old linear proxy.

### What to build
1. **Target definition** (write it down in the module docstring and in the report):
   one scalar **difficulty ∈ [0, 1]** so "MAE ≤ 0.15" has a meaning.
   - Primary: perceived difficulty when a rating exists: `(rating − 1) / 4`.
   - Fallback (all current data): a **measured difficulty** built from outcomes, e.g. a fixed, documented combination of normalised deaths, damage taken (fraction of max HP), and completion time relative to a target time per room. Fix the normalisation constants once; don't tune them on the test set.
   - Keep the 4 raw outcome targets available too (multi-output is fine as an extra).
2. **Synthetic corpus generator** `ml_spike/judge/make_synthetic_corpus.py`
   - Sample settings across the full action space (uniform + near-preset samples) and many simulated players (skill/reflex/tactics spread). Call the simulator; compute the same target as above.
   - Output the **same column names as `v_corpus`** plus a `source = "synthetic"` column, so the trainer reads synthetic and real data the same way. ~20k–50k rows; fixed seed.
3. **Features**: the 14 `JUDGE_FEATURES` + a small **player-context** block taken from the previous floor of the same session (prev completion time, prev deaths, prev damage taken). The Judge predicts "how hard will these settings be **for this player**". Document how the first floor of a session is handled.
4. **Trainer** `ml_spike/judge/train_judge.py`
   - Add `lightgbm` and `shap` to `ml_spike/requirements.txt` (check CI still installs within time; keep versions pinned to recent stable).
   - LightGBM regressor. **Split by session/player, not by row** (no leakage). 5-fold grouped CV + held-out test.
   - Report: MAE, RMSE, R² on synthetic test; compare against (a) the old linear proxy `difficulty_score()` rescaled to [0,1], and (b) a mean-predictor baseline. The point to prove: learned Judge beats the hand-weighted proxy.
   - Then score the **real rows** (sync the user's `forge_telemetry.db`) and report MAE on them with the sample size, clearly marked "n is too small to conclude".
   - Save the model as `ml_spike/judge/judge_model.txt` (LightGBM native) + a JSON with feature names, target definition, metrics, data counts, git commit.
5. **TreeSHAP** `ml_spike/judge/explain.py`
   - Global: SHAP summary (beeswarm) + mean |SHAP| bar chart → `ml_spike/judge/figures/`.
   - Local: a "Design Insight Report" for one floor: top 3 features in plain English, e.g. "Difficulty +0.12 mostly because enemy damage was high (+0.07) and resource scarcity was high (+0.04)."
   - CLI: `python -m ml_spike.judge.explain --db path/to/forge_telemetry.db --session <id>` prints the report per floor.
6. **Tests** `ml_spike/tests/test_judge.py`: corpus generator is deterministic for a seed; columns match `v_corpus`; grouped split has no session overlap; a tiny model trains and beats the mean predictor; SHAP values sum to prediction − expected value (additivity); explain CLI runs on a fixture DB with a few floors. Keep the test fast (<20 s).
7. **Results file** `ml_spike/judge/results_judge.md`: target definition, data counts (synthetic/real), metrics table, figures, limitations (synthetic training data, simulator bias, real-data MAE not meaningful yet), and what changes in FYP-2 (retrain on 25+ consented players, rating target).

### Out of scope for now (mention in the report as next steps)
- Porting the trained trees or SHAP into GDScript / live in-game explanation panel (FYP-2). Optional if time allows: export the model to JSON and show the offline Insight Report for a recorded session in the Final-1 demo.
- Replacing the Judge used inside PPO training.

### Acceptance checklist
- [ ] `python -m ml_spike.judge.make_synthetic_corpus` and `train_judge` run end to end from a clean venv.
- [ ] Synthetic test MAE ≤ 0.15 on the [0,1] target and better than the linear proxy (if not, report the real number and why).
- [ ] Real-row evaluation printed with its n.
- [ ] SHAP figures + one example Insight Report in `results_judge.md`.
- [ ] pytest + ruff pass; CI unchanged otherwise.
- [ ] Git commands for Ryn.

---

## Task B: Rule-based BSP baseline generator (Godot)

### Why
Committee: "demonstrate the benefit of the closed-loop adaptive approach over a **strong non-adaptive procedural-generation baseline**". Planned comparison:
- Baseline A: BSP generator, non-adaptive (fixed Intermediate difficulty).
- Baseline B: existing static baseline (+8 % per floor, `DifficultyManager.static_baseline_mode`).
- FORGE: existing generator + PPO.

### What exists
- `godot_prototype/scripts/DungeonGenerator.gd`: grid-of-rooms generator. `generate_dungeon(p_diff, target_room_count) -> Dictionary` (Vector2i → RoomData), `start_room_pos`, `exit_room_pos`, random/chain layouts, `_pick_exit` (far from start), `_assign_sizes` (WIDTH_STEPS/HEIGHT_STEPS), `_layout_world()`. Rooms connect through doors on grid neighbours; `Room.gd` builds the room from RoomData.
- Static baseline wiring to copy: `DifficultyManager.static_baseline_mode`, `apply_static_baseline()`, the Defense Panel toggle in `DefenseOverlay.gd`, `tests/test_static_baseline.gd`.
- Solvability check: `tests/ci_solvability_runner.gd` (used by CI).
- Telemetry: `sessions`/`floors` tables; there is a phase/mode field. Record which generator was used so evaluation can split by condition (check `schema.sql`; if a new column is needed, add a schema migration v3 the same way v2 added `manual_override`, update `queries.sql`, `telemetry_db.py`, and both schema tests).

### What to build
1. **BSP layout mode** (new file e.g. `scripts/BSPGenerator.gd` or a mode inside `DungeonGenerator`):
   - Recursively split a rectangle (min leaf size, random split ratio 0.35–0.65, depth limit), one room per leaf, connect sibling leaves bottom-up so the graph is connected.
   - **Must output the same RoomData dictionary** the game already consumes (grid positions + door connections + sizes + start/exit), so `Room.gd`, minimap, pickups, enemies all work unchanged. Map BSP leaves onto the existing grid/door model rather than inventing a new room system.
   - Start = one leaf, exit = farthest leaf by graph distance.
   - Difficulty: fixed Intermediate preset every floor (non-adaptive), no PPO, no calibration.
2. **Switch**: `DifficultyManager` (or Main) gets a `generator_mode` = `forge` / `static` / `bsp`. Selectable in the Defense Panel (dev build only) and via command line `-- --mode=bsp` for scripted runs. Playtest build stays FORGE only.
3. **Tests**
   - `tests/test_bsp_generator.gd`: 200 seeds × room counts 4–10 → every dungeon connected, exit reachable from start, no overlapping rooms, exit ≠ start, deterministic for a seed. Add it to `ci.yml` list and to the solvability runner.
4. **Layout-diversity metrics** (shared script, used for the report table): for N generated dungeons per generator compute room count, room-size variance, start→exit path length, branching factor / dead ends, and a pairwise layout distance (e.g. normalised edit distance of the occupancy grid). Output CSV + one figure comparing FORGE vs BSP vs static.

### Acceptance checklist
- [ ] Game runs a full BSP run in the dev build; floors look sane (send screenshots).
- [ ] test_bsp_generator passes; all existing tests still pass.
- [ ] Telemetry rows say which generator produced them.
- [ ] Diversity CSV + figure.
- [ ] Git commands for Ryn.

---

## After both: evaluation + report (separate step)
One script producing the Final-1 results table: solvability %, layout diversity (FORGE vs BSP vs static), PPO convergence and adaptation stability (from `results_sim_v3.md`), Judge MAE vs linear proxy, SHAP figures. Then update the LaTeX report in `docs/reports/mid_report/latex` (new iteration chapter, testing, results, limitations; timeline table: shop → FYP-2 Mid, Judge + SHAP → Final-1).
