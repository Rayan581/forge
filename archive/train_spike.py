"""
FORGE FYP - Reinforcement Learning Technical Spike
Trains a baseline PPO agent on a tile-grid level generation environment (gym-pcgrl Zelda paradigm).
Calculates solvability rates and generates the convergence curve for Proposal Section 5.7.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

# Tile representations
EMPTY = 0
WALL = 1
PLAYER = 2
KEY = 3
DOOR = 4
ENEMY = 5

class SimpleDungeonPCGEnv(gym.Env):
    """
    Minimal tile-grid PCG environment modeling the gym-pcgrl narrow/wide Zelda representation.
    Grid size: 11 x 7
    Goal: Learn to generate a map with 1 Player, 1 Key, 1 Door, and solvable connectivity.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, width=11, height=7, max_steps=120):
        super().__init__()
        self.width = width
        self.height = height
        self.max_steps = max_steps
        self.current_step = 0
        
        # Observation space: 2D grid
        self.observation_space = spaces.Box(low=0, high=5, shape=(height, width), dtype=np.int32)
        
        # Action space: (x, y, tile_type) -> discrete multi-category
        self.action_space = spaces.Discrete(width * height * 6)
        self.grid = np.zeros((height, width), dtype=np.int32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        # Initialize with border walls and random empty/wall interior
        self.grid = np.zeros((self.height, self.width), dtype=np.int32)
        self.grid[0, :] = WALL
        self.grid[-1, :] = WALL
        self.grid[:, 0] = WALL
        self.grid[:, -1] = WALL
        
        return self.grid.copy(), {}

    def step(self, action):
        self.current_step += 1
        
        # Decode action
        tile_type = action % 6
        idx = action // 6
        x = idx % self.width
        y = idx // self.width
        
        # Only allow edits inside borders
        if 0 < x < self.width - 1 and 0 < y < self.height - 1:
            self.grid[y, x] = tile_type
            
        reward, is_solvable = self._compute_reward()
        done = self.current_step >= self.max_steps or is_solvable
        truncated = False
        
        return self.grid.copy(), reward, done, truncated, {"is_solvable": is_solvable}

    def _compute_reward(self):
        player_count = np.count_nonzero(self.grid == PLAYER)
        key_count = np.count_nonzero(self.grid == KEY)
        door_count = np.count_nonzero(self.grid == DOOR)
        
        # Reward component counts (Target: exactly 1 player, 1 key, 1 door)
        reward = 0.0
        reward -= abs(player_count - 1) * 2.0
        reward -= abs(key_count - 1) * 2.0
        reward -= abs(door_count - 1) * 2.0
        
        is_solvable = False
        if player_count == 1 and key_count == 1 and door_count == 1:
            # Check path connectivity using BFS
            is_solvable = self._check_reachability()
            if is_solvable:
                reward += 20.0
            else:
                reward += 5.0
                
        return reward, is_solvable

    def _check_reachability(self):
        p_pos = tuple(np.argwhere(self.grid == PLAYER)[0])
        k_pos = tuple(np.argwhere(self.grid == KEY)[0])
        d_pos = tuple(np.argwhere(self.grid == DOOR)[0])
        
        # BFS from Player to Key, then Key to Door
        def bfs(start, target):
            queue = [start]
            visited = set([start])
            while queue:
                cy, cx = queue.pop(0)
                if (cy, cx) == target:
                    return True
                for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < self.height and 0 <= nx < self.width:
                        if (ny, nx) not in visited and self.grid[ny, nx] != WALL:
                            visited.add((ny, nx))
                            queue.append((ny, nx))
            return False
            
        return bfs(p_pos, k_pos) and bfs(k_pos, d_pos)

class TrainingMetricLogger(BaseCallback):
    def __init__(self, check_freq=1000):
        super().__init__()
        self.check_freq = check_freq
        self.timesteps = []
        self.solvability_rates = []

    def _on_step(self) -> bool:
        if self.n_calls % self.check_freq == 0:
            # Evaluate solvability over 20 test episodes
            env = SimpleDungeonPCGEnv()
            solvable_count = 0
            for _ in range(20):
                obs, _ = env.reset()
                done = False
                while not done:
                    action, _ = self.model.predict(obs, deterministic=True)
                    obs, reward, done, _, info = env.step(action)
                if info.get("is_solvable", False):
                    solvable_count += 1
            rate = (solvable_count / 20.0) * 100.0
            self.timesteps.append(self.num_timesteps)
            self.solvability_rates.append(rate)
            print(f"Timestep: {self.num_timesteps:6d} | Solvability Rate: {rate:5.1f}%")
        return True

def main():
    print("=========================================================")
    print("  FORGE FYP: Reinforcement Learning Spike (POC Training)  ")
    print("=========================================================")
    
    env = SimpleDungeonPCGEnv()
    logger = TrainingMetricLogger(check_freq=1000)
    
    # Train PPO for 10,000 timesteps (fast technical spike)
    total_timesteps = 10000
    print(f"Starting PPO training for {total_timesteps} timesteps...")
    model = PPO("MlpPolicy", env, verbose=0, learning_rate=3e-4, gamma=0.95)
    model.learn(total_timesteps=total_timesteps, callback=logger)
    
    # Save Model
    os.makedirs("models", exist_ok=True)
    model.save("models/forge_baseline_ppo.zip")
    print("Model saved to models/forge_baseline_ppo.zip")
    
    # Generate Plot
    if len(logger.timesteps) > 0:
        plt.figure(figsize=(8, 4.5))
        plt.plot(logger.timesteps, logger.solvability_rates, marker='o', color='#0d7d8f', linewidth=2.2)
        plt.title("FORGE RL Spike: PPO Level Solvability vs Timesteps", fontsize=13, fontweight='bold')
        plt.xlabel("Training Timesteps", fontsize=11)
        plt.ylabel("Solvable Layout Percentage (%)", fontsize=11)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.ylim(0, 105)
        plt.tight_layout()
        plot_path = "forge_poc_convergence.png"
        plt.savefig(plot_path, dpi=150)
        print(f"Convergence plot saved to {plot_path}")
        
    print("\nSpike run completed successfully!")

if __name__ == "__main__":
    main()
