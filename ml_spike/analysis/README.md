# Policy training curves and evaluation (simulator v3, "sim-v3")

Run from the repository root (needs the packages in `ml_spike/requirements.txt`).

```bash
# 1. train three seeds with CSV logging (1M timesteps each, 8 vectorised envs, ~10 min per seed)
for s in 0 1 2; do python ml_spike/analysis/train_with_logging.py $s ml_spike/analysis/runs_v3 1000000; done
# 2. export the best seed (chosen on 200 held-out validation episodes) to the game and refresh
#    the SB3 checkpoint used by the parity tests
python ml_spike/analysis/export_best.py ml_spike/analysis/runs_v3 auto
# 3. evaluate against random-init / heuristic / static baselines + the previous sim-v2 policy,
#    abrupt-shift scenario and simulator checks (~25 min); <best_seed> is printed by step 2
python ml_spike/analysis/evaluate_policies.py ml_spike/analysis/runs_v3 <best_seed>
# 4. figures -> ml_spike/analysis/figures/*_v3.png
python ml_spike/analysis/make_figures.py ml_spike/analysis/runs_v3
```

Outputs: `results_sim_v3.md` (diagnosis, change table, all result tables and the acceptance
criteria; the diagnosis/changes section is `sim_v3_notes.md`, included verbatim),
`eval_results_sim_v3.json` (raw per-episode data), `figures/*_v3.png`.

What sim-v3 adds on top of sim-v2: `enemy_damage` and `resource_scarcity` now have distinct,
skill-dependent effects (reflex-scaled damage caution, tactics-scaled scarcity caution and healing
usage) and two stated experience priors (hit-severity band conditioned on reflex, healing
recoverability conditioned on tactics); see `results_sim_v3.md` and the "SIMULATOR CONSTANTS"
section of `ml_spike/train_ppo_difficulty.py`.  The observation and action contracts are unchanged.

Shipped files: `godot_prototype/ai/policy_weights.json` is the sim-v3 policy
(`meta.version = "sim-v3"`); `godot_prototype/ai/policy_weights_v2.json` is the previous sim-v2
policy (kept for comparison; it is also evaluated as a reference row in `results_sim_v3.md`);
`policy_weights_v1_7dim.json` is the legacy 7-dim policy.

Older material kept for reference: `results_sim_v2.md`, `eval_results_sim_v2.json`, `runs/` (the
sim-v2 SB3 checkpoints and logs) and the un-suffixed / `_v2` figures belong to sim-v2;
`eval_results.json` and `training_logs/` are the v1 (7-dim) results that the mid-term report was
written from.  Note that `results_sim_v2.md` can no longer be regenerated with the current
simulator (the v2 simulator is in git history, commit 23b38d6).
