# FORGE — RL Technical Spike (Track B)

This directory contains the reinforcement learning technical spike script for the FORGE Final Year Project.

## Prerequisites
Ensure Python 3.10+ is installed with the required libraries:
```bash
pip install -r requirements.txt
```

## Running the Spike
Execute the training script:
```bash
python train_spike.py
```

## Outputs Produced
1. **`models/forge_baseline_ppo.zip`**: The trained Stable-Baselines3 PPO baseline model.
2. **`forge_poc_convergence.png`**: The solvability convergence curve plot showing solvable layout % vs training timesteps.
3. **Console Telemetry**: Final solvability percentages to insert into Section 5.7 of `FORGE_Proposal.md`.
