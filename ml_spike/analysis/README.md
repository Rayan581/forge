# Policy training curves and evaluation (simulator v2, "sim-v2")

Run from the repository root (needs the packages in `ml_spike/requirements.txt`).

```bash
# 1. train three seeds with CSV logging (1M timesteps each, 8 vectorised envs, ~9 min per seed)
for s in 0 1 2; do python ml_spike/analysis/train_with_logging.py $s ml_spike/analysis/runs 1000000; done
# 2. export the best seed to the game and refresh the SB3 checkpoint used by the parity tests
python ml_spike/analysis/export_best.py ml_spike/analysis/runs <best_seed>
# 3. evaluate against random-init / heuristic / static baselines + abrupt-shift scenario + simulator checks
python ml_spike/analysis/evaluate_policies.py ml_spike/analysis/runs <best_seed>
# 4. figures -> ml_spike/analysis/figures/
python ml_spike/analysis/make_figures.py ml_spike/analysis/runs
```

Outputs: `results_sim_v2.md` (all tables), `eval_results_sim_v2.json` (raw per-episode data),
`figures/*.png`.  `eval_results.json` and `training_logs/` are the v1 (7-dim) results that the
mid-term report was written from; they are kept for reference.
