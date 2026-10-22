# Policy training curves and unseen-profile evaluation

Run from the repository root (needs the packages in `ml_spike/requirements.txt` plus pandas and scipy).

```bash
# 1. re-train with logging, one run per seed (writes progress.csv + model per seed)
for s in 0 1 2; do python ml_spike/analysis/train_with_logging.py $s ml_spike/analysis/runs; done
# 2. evaluate shipped policy, re-trained policies and random-init policies on unseen player profiles
python ml_spike/analysis/evaluate_policies.py ml_spike/analysis/eval.json godot_prototype/ai/policy_weights.json ml_spike/analysis/runs
# 3. draw the two figures used in the report (run from ml_spike/analysis)
cd ml_spike/analysis && python make_figures.py
```
