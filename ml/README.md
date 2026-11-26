# ml/ — FORGE ML pipeline (MLP1 → Judge → new simulator → PPO → SHAP → baselines → report)

Every module is built and connected. When the real data is ready you run the stages **one by one, in
order**; each stage writes its outputs into the run folder and records them in `manifest.json`, and the
next stage picks them up from there. Nothing has to be copied by hand between stages.

The Godot client is **not** touched. The retrained policy is written into the run folder; putting it
into the game is a separate, manual step (see "After the run").

## Run order

Run from the repository root (`X:\FAST Tasks\FYP`). Same command on Windows, macOS and Linux:

```bash
python -m ml.pipeline <stage> --config ml/configs/default.json
```

| # | Stage | What it does | Main outputs (in `ml/runs/<run_name>/`) |
|---|---|---|---|
| 1 | `player` | Trains **MLP1** (player model) on the telemetry | `1_player_model/player_model.pt`, `player_model_report.json` |
| 2 | `judge` | Trains the **Judge** (LightGBM) on the telemetry, tests it on **held-out players**, compares it with the old hand-weighted formula (`difficulty_score`), **TreeSHAP** figures + an example Design Insight Report | `2_judge/judge_model.txt`, `judge_model.json`, `figures/`, `insight_report_example.txt` |
| 3 | `sim` | Builds the **new simulator** (sim-v4): MLP1 `sample_from_action` gives the player's outcome, the Judge gives the difficulty used in the reward. Runs response checks and scores random / static / old PPO on it | `3_sim/sim_config.json`, `sim_report.json` |
| 4 | `ppo` | **Retrains PPO** on sim-v4 (same recipe as sim-v3, one run per seed), picks the best seed on a validation set, exports `policy_weights.json`, runs the **exploit check** | `4_ppo/ppo_best.zip`, `policy_weights.json`, `ppo_summary.json`, `seed*/progress.csv` |
| 5 | `policy-shap` | Exact **SHAP of the retrained policy** (which observation drives which setting), side by side with the old policy | `5_policy_shap/policy_shap.json`, heatmap + beeswarm figures |
| 6 | `baselines` | **BSP generator** baseline + static +8 % + old-simulator PPO vs the new PPO: solvable %, difficulty fit, layout variety, adaptation speed, in **both** simulators | `6_baselines/comparison.json/.csv`, `variety.csv`, figures |
| 7 | `report` | Collects every number and figure: `results.md`, CSV + LaTeX tables, figures | `7_report/` |

Other commands: `python -m ml.pipeline all` (stages 1–7 in one go), `python -m ml.pipeline status`
(which stages are done). If a stage's input is missing, it stops and tells you which stage to run first.
Re-running a stage replaces its folder; the later stages then need to be re-run too.

Shortcuts: `make -f ml/Makefile ppo` (any stage name), or on Windows `.\ml\run_pipeline.ps1 ppo`.

### Step by step when the real data is ready

```powershell
cd "X:\FAST Tasks\FYP"
# 0. one-off: Python packages (CPU torch is enough)
pip install -r ml_spike/requirements.txt
# 0b. dry run of every stage on synthetic data (about 1-2 minutes), and the tests
python -m ml.pipeline all --config ml/configs/smoke.json
python -m pytest ml/tests -v
# 1-7. the real run. Point data.telemetry at the DB or CSV (or leave "auto" = the game's user:// DB)
python -m ml.pipeline player      --config ml/configs/default.json --set data.telemetry="C:/path/forge_telemetry.db"
python -m ml.pipeline judge       --config ml/configs/default.json --set data.telemetry="C:/path/forge_telemetry.db"
python -m ml.pipeline sim         --config ml/configs/default.json
python -m ml.pipeline ppo         --config ml/configs/default.json     # the long one, see timing below
python -m ml.pipeline policy-shap --config ml/configs/default.json
python -m ml.pipeline baselines   --config ml/configs/default.json
python -m ml.pipeline report      --config ml/configs/default.json
```

Easier: put the telemetry path into `ml/configs/default.json` once (`"data": {"telemetry": "..."}`)
so you don't need `--set` on every line.

## Input data

`data.telemetry` accepts:
* the game's **SQLite DB** (`forge_telemetry.db`, read through the `v_corpus` view), or
* the **CSV** from `python ml_spike/analysis/export_telemetry.py <db> out.csv`, or
* `"auto"` = the game's `user://forge_telemetry.db` if it exists on this machine, or
* `"synthetic"` = stage 0 (`smoke-data`) writes a synthetic CSV in the same `v_corpus` format and every
  stage uses it. This is how the smoke run tests the real-data code path.

`data.consented_only` (default `true`) keeps only sessions with consent. Floors with
`manual_override = 1` are always dropped.

**What happens with too little data.** The Judge needs at least `judge.min_real_players` (7) players
for a grouped 5-fold CV + held-out test. With `judge.train_on = "auto"` (default) it trains on real data
when there are enough players, and otherwise trains on the synthetic sim-v3 corpus and uses every real
floor as the held-out check (all real players are then unseen). MLP1 falls back to holding out sessions
when there is one player (it prints a warning). Today's real data (29 floors, one player) therefore gives
a **synthetic-trained Judge validated on 29 real floors**; that is labelled in every output.

## Configuration

`ml/config.py` holds every knob with its default and a comment. A config file only needs the keys it
changes (`ml/configs/default.json`, `smoke.json`, `synthetic_check.json`). Any value can be overridden:
`--set ppo.seeds=[0]`, `--set sim.judge_w=0.5`, `--set run_name=try2` (a new run folder).

Main knobs:
* `judge.train_on`: `auto` / `real` / `synthetic` / `mixed`; `judge.target`: `auto` (rating if the
  player rated the floor, else measured) / `measured` / `rating`.
* `sim.judge_target` (0.27), `sim.judge_w`, `sim.judge_tol`, `sim.ood_w`, and the kept sim-v3 reward
  weights. Reward formula: top of `ml/sim_v2.py`.
* `ppo.seeds`, `ppo.total_timesteps` (1M per seed, like sim-v3), `ppo.vec_env` (`subproc` = parallel
  simulators), `ppo.init_from` (warm start from an SB3 zip), exploit-check thresholds.
* `baselines.old_policy` (default `godot_prototype/ai/policy_weights.json`, the shipped sim-v3 policy).

**Timing (measured in the cloud container, 4 CPU cores):** sim-v4 trains at about 940 steps/s with
`vec_env = subproc` (440 steps/s single-process), so 1M steps ≈ 18 min per seed and the default 3 seeds
≈ 1 hour. Every other stage takes seconds to a few minutes.

## How the pieces connect

* **sim-v4** (`ml/sim_v2.py`, `DungeonDifficultyEnvV2`) keeps the game's 8-D observation / 8-D action
  contract. The player's outcome comes from `PlayerModel.sample_from_action(action, skill, history, rng)`;
  the latent player (skill, reflex/tactics bias, drift, abrupt shifts) is reused unchanged from sim-v3.
  Floors outside the PPO action box (calibration, static +8 %, BSP) go through the same MLP1 with
  explicit settings; a test checks both paths give the same draw.
* **Judge in the loop** (`ml/judge_bridge.py`): the Judge's prediction D_judge for these settings and
  this player (previous floor as context) replaces the hand-weighted `difficulty_score` as the
  difficulty signal: `reward -= judge_w * max(0, |D_judge - D_target| - judge_tol)`. The old score is
  still logged as `proxy` for comparison. Settings outside the Judge's training range are penalised
  (`ood_w`).
* **Exploit check** (`ml/ppo_train.py`): Judge prediction vs the difficulty the MLP1 player actually
  realised (must stay near the Judge's held-out MAE), out-of-range settings, actions stuck at the box
  edge, MLP1 ensemble disagreement, and the new policy played in the **old physics simulator** (an
  independent player model). Result: `4_ppo/ppo_summary.json` → `exploit_check.passed` and `checks`.
* **BSP generator** (`ml/layouts.py`): recursive split (ratio 0.35–0.65, min leaf, depth limit), one room
  per leaf, sibling subtrees joined by one door, start = a dead end, exit = deepest room. It outputs the
  same grid/door room model as `DungeonGenerator.gd`, so it can be ported to GDScript later. The file
  also has a Python port of the current random-walk generator for the variety comparison.
* **BSP in the game** (`godot_prototype/scripts/BSPGenerator.gd`, same algorithm): pick the condition
  with `DifficultyManager.set_generator_mode("forge" | "static" | "bsp")`, the Defense Panel toggle
  "BSP Baseline (fixed Intermediate)" (dev build), or `godot --path godot_prototype -- --mode=bsp`.
  BSP floors use the fixed Intermediate preset, no calibration, no PPO. Telemetry schema v3 adds
  `floors.generator` (`forge` / `bsp`); BSP floors are stored with phase `static`.

## After the run

* `ml/runs/<run>/7_report/results.md` has every table (CSV and LaTeX copies in `tables/`) and figure.
* If `exploit_check.passed` is true and the results beat the old policy, copy
  `ml/runs/<run>/4_ppo/policy_weights.json` to `godot_prototype/ai/policy_weights.json` (keep the old
  file as `policy_weights_v3.json`). Its `meta.version` is `sim-v4-mlp1-judge`. Run the Godot tests
  after copying (CI checks size < 120 KB and inference parity).
* `ml/runs/` holds large generated files; keep it out of git (see below).

## Honest limits

* Smoke / synthetic runs only prove the code path works; every output says SYNTHETIC when it is.
* sim-v4 is only as good as MLP1 and the Judge. With one real player both are close to their synthetic
  priors (MLP1's physics base term; the synthetic-trained Judge), so a sim-v4 policy trained today
  mostly re-learns sim-v3. The pipeline becomes meaningful with the FYP-2 player corpus.
* norm_time is clipped at 90 s (the game's observation contract), so very slow floors all look alike.
* The hidden-skill priors of sim-v3 (rooms, complexity, hit severity, healing cover) are kept in the
  reward (weights in the config); set them to 0 to train on the data-driven terms only.
* BSP is evaluated in the simulators through its room count and the fixed Intermediate settings.

## Godot tests for the BSP port (run on your PC; they were not run in the cloud)

```powershell
godot --headless --path godot_prototype --import
godot --headless --path godot_prototype --script res://tests/test_bsp_generator.gd
godot --headless --path godot_prototype --script res://tests/ci_solvability_runner.gd   # now also 500 BSP layouts
godot --headless --path godot_prototype --script res://tests/test_static_baseline.gd
godot --headless --path godot_prototype --script res://tests/test_telemetry_logger.gd
godot --headless --path godot_prototype --script res://tests/test_playtest_flow.gd
godot --path godot_prototype -- --mode=bsp      # play a BSP run and look at the floors
```

Add `test_bsp_generator` to the list of GDScript tests in `.github/workflows/ci.yml` (next to
`test_static_baseline`). Godot creates `BSPGenerator.gd.uid` and `test_bsp_generator.gd.uid` on import:
commit them too.

## Git (run these yourself; nothing was committed)

```powershell
cd "X:\FAST Tasks\FYP"
git checkout -b ml-pipeline
Add-Content .gitignore "`nml/runs/"
git add .gitignore ml/config.py ml/configs ml/judge_bridge.py ml/sim_v2.py ml/ppo_train.py ml/policy_shap.py ml/layouts.py ml/compare.py ml/report.py ml/pipeline.py ml/Makefile ml/run_pipeline.ps1 ml/README.md ml/tests/test_pipeline.py ml_spike/judge/explain.py ml_spike/judge/make_synthetic_corpus.py ml_spike/telemetry_data/telemetry_db.py ml_spike/tests/test_sqlite_telemetry.py ml_spike/tests/test_telemetry_schema.py
git add godot_prototype/scripts/BSPGenerator.gd godot_prototype/scripts/BSPGenerator.gd.uid godot_prototype/scripts/DungeonGenerator.gd godot_prototype/scripts/DifficultyManager.gd godot_prototype/scripts/Main.gd godot_prototype/scripts/DefenseOverlay.gd godot_prototype/scripts/TelemetryLogger.gd godot_prototype/telemetry/schema.sql godot_prototype/telemetry/queries.sql godot_prototype/tests/test_bsp_generator.gd godot_prototype/tests/test_bsp_generator.gd.uid godot_prototype/tests/ci_solvability_runner.gd .github/workflows/ci.yml
git commit -m "ML pipeline (Judge stage, sim-v4, PPO retrain + exploit check, policy SHAP, report) and BSP baseline generator in Godot (generator mode, telemetry schema v3)"
git push -u origin ml-pipeline
```

If MLP1 itself (`ml/player_*.py`, `ml/train_player_model.py`, `ml/tests/test_player_model.py`,
`ml/artifacts/`) is not committed yet, add those files to the same `git add` line.

---

# MLP1 — the player model (stage 1) in detail

Grey-box model of how a player responds to a floor: **(difficulty config y, skill, last 2 observations) → distribution over x = (norm_time, norm_deaths, norm_dmg)**.
It will replace `_simulate_level` / `_simulate` in the future `DungeonDifficultyEnvV2`. The observation (8-D) and action (8-D) contracts are untouched; the Godot client and `ml_spike/train_ppo_difficulty.py` are not modified (the model only *imports* from the latter).

| File | What it is |
|---|---|
| `player_data.py` | `FloorDataset`, telemetry loader (`.db` / `.csv`), synthetic generator from the old simulator, train/val split |
| `player_model.py` | analytic base term, residual MLP, ensemble, `fit`, `sample_from_action`, `save` / `load` |
| `player_eval.py` | per-output MAE, calibration (PIT, interval coverage, distribution distance), monotonicity check |
| `train_player_model.py` | command line: load → split → train → evaluate → save model + JSON report |
| `tests/test_player_model.py` | 14 tests |
| `artifacts/player_model_synthetic.pt` | model trained on **SYNTHETIC** data only (pipeline demo, not a real-player model) |

## How it works (short)
`mean(x) = base(y, skill) + 0.25 · tanh(MLP(features))`, `sigma(x) = 0.01 + softplus(MLP(features))`.
* **base** = the old physics (`DungeonDifficultyEnv._room_layout` + `_physics`), averaged over 3 layouts and 5 damage-noise points. It already makes time, deaths and damage rise with `difficulty − skill`.
* **residual** is small and bounded, so with little data the model stays close to the physics.
* **monotone penalty** (training loss): the residual must not decrease when a parameter or the gap goes up, nor increase when skill goes up. Soft, not a hard guarantee; `monotonicity_check` measures violations.
* **ensemble** of 5 bootstrap-trained nets; a sample picks one member then draws a Gaussian, so member disagreement widens the noise.

## Run
Run everything from the repository root, with `torch`, `numpy`, `pandas`, `gymnasium` installed (`ml_spike/requirements.txt` has them plus `stable-baselines3`, which the old simulator imports).

```bash
python -m pytest ml/tests -v                                   # tests (about 10 s)
python -m ml.train_player_model --source synthetic --players 150 --out ml/artifacts/player_model_synthetic.pt   # about 1 min
python -m ml.train_player_model --source real --telemetry path/to/forge_telemetry.db --out ml/artifacts/player_model_real.pt
```

Use from the future simulator:
```python
from ml.player_model import PlayerModel
model = PlayerModel.load("ml/artifacts/player_model_synthetic.pt")
x = model.sample_from_action(action8, skill, history, rng)   # float32 (3,): norm_time, norm_deaths, norm_dmg
# history = last 1-2 observations (k x 3 or k x 8), most recent last; skill = latent skill in 0..1
```
`model.data_source` says whether the weights were fitted on `'synthetic'` or `'real'` data.

## What the numbers mean (read before quoting any)
* **Synthetic runs** only show the pipeline works. The data comes from the same physics as the base term, so the residual has nothing to learn and ≈ matches the base. Any "good" MAE there is **not** evidence about real players.
* **Real data today = one player, 3 sessions, 29 floors.** There is no player split possible. The script falls back to holding out whole sessions (or the last floors) and prints a warning; those metrics only measure fit **within one person**. Calibration on ~8 rows is anecdotal.
* The real skill is latent. For real telemetry the loader uses a crude proxy (EMA of a competence score from *previous* floors, alpha 0.3, prior 0.5). The simulator will pass its true latent skill instead; that mismatch is a known gap.
* Deaths are whole numbers and mostly 0, so the Gaussian is an approximation; samples are clipped to [0, 1] and deaths are rounded to k/3.
* Not modelled: per-room pacing, enemy-count scale on adaptive floors (always 1), reflex-vs-tactics bias (reflex = tactics = skill in the base term), the apex champion, and the known sim↔game gaps (healing 0.18 vs 35 HP, hazard tick damage).
* Outside the training range the model falls back to the physics base (the residual is bounded), but PPO can still exploit it. Constrain `y` or add an OOD penalty in V2 (handoff step 4).
