# Rating-trained Judge, leave-one-player-out (2026-11-27)

Data: ml/runs/tel1127_data/forge_merged_v2.db = the 5 collected players + tonight's Pilot 2 run on
this PC as its own player (`pc1127_pilot2_run`, a copy; the original DBs are unchanged).
150 rated floors, 6 players. Every method is fitted on 5 players and scored on the 6th.
Script: ml/runs/tel1127_lopo/rating_judge.py. Numbers: summary.csv, predictions.csv.

| Method | Rating error (stars) | Exact | Within 1 | Rank agreement (per player) |
|---|---|---|---|---|
| Predict the average | 0.77 | 47% | 82% | n/a |
| Old formula (difficulty_score), rescaled | **0.48** | **61%** | 98% | **0.77** |
| Current Judge (mlp1_synth), rescaled | 0.62 | 43% | 98% | 0.72 |
| Rating-trained Judge (fine-tuned on ratings) | 0.51 | 58% | 99% | 0.74 |
| Outcomes, hand weights 40/35/25 | 0.71 | 41% | 95% | 0.70 |
| Outcomes, learned weights | 0.71 | 40% | 95% | 0.65 |

Learned outcome weights (all players): damage 0.91, deaths 0.09, time per room 0.00 (hand: 0.40 /
0.35 / 0.25). Player-bootstrap 90% ranges: damage 0.45-1.00, deaths 0.00-0.49, time 0.00-0.37.

Caveat: all ratings except 29 floors (8 Nov playtest build) were given in dev builds that show the
difficulty score before rating. The settings formula IS that score, so its lead may be anchoring.
Supporting this: what happened on the floor (damage, deaths, time) predicts ratings worse than the
settings formula does. Only playtest-build (hidden score) ratings can settle Judge vs formula.
