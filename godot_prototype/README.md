# FORGE — Godot 4.x Prototype User Guide

Welcome to the **FORGE Interactive Dungeon Crawler Prototype**! This guide walks you step-by-step through opening, playing, and demonstrating the prototype for your FYP proposal defense.

---

## 1. How to Open the Project in Godot

1. **Launch Godot:**
   - Double-click the Godot executable on your machine:
     ```
     D:\Softwares\Godot_v4.7.1-stable_win64\Godot_v4.7.1-stable_win64.exe
     ```
2. **Import the Project:**
   - On the Godot Project Manager window, click the **Import** button (top left).
   - In the popup dialog, click **Browse**, navigate to:
     ```
     D:\FAST Tasks\FYP\godot_prototype
     ```
   - Select the `project.godot` file and click **Open**.
   - Click **Import & Edit**.
3. **Run the Game:**
   - Once the Godot editor opens, press **F5** on your keyboard (or click the **▶ Play** button at the top-right corner).
   - The game window will launch in full 1280x720 resolution.

---

## 2. Gameplay Controls

| Action | Controls |
| :--- | :--- |
| **Movement** | **W, A, S, D** or **Arrow Keys** (8-directional) |
| **Attack** | **Left Mouse Button** or **Spacebar** (swings sword in mouse/facing direction) |
| **Toggle Defense Panel** | **Tab Key** or click the **⚙ Defense Panel** button at the top-right |

---

## 3. How to Demonstrate During Proposal Defense

### Demonstration Workflow (30 Seconds to Impress Your Panel):
1. **Show Gameplay:**
   - Move your character around the room, defeat the enemies, and pick up health potions.
   - When all enemies in a chamber are defeated, the top **Exit Door turns green (unlocked)**. Step through the doorway to enter the next chamber.

2. **Open the Defense Panel:**
   - Press **Tab** or click **⚙ Defense Panel**.

3. **Demonstrate Adaptive Difficulty Presets:**
   - Click **[Novice]**: Watch the parameters immediately drop to low damage, slow velocity, and light hazards. Notice the **Design Insight Report** score changes to `32/100 · Accessible`.
   - Click **[Expert]**: Watch enemy speed, damage, and hazard density spike. The Design Insight Report score jumps to `88/100 · Brutal`, with *Enemy Damage* and *Velocity* highlighted as the top attribution drivers.
   - Click **🔄 Apply Parameters & Rebuild Room**: The chamber regenerates live with the new adversary and environmental parameters!

4. **Show Live Telemetry Logging:**
   - Look at the bottom of the Defense Panel: it shows real-time tracking of **Elapsed Time**, **Deaths**, **Damage Taken**, and **Pickups**.
   - All session data is automatically written to `user://session_telemetry.json`.

---

## 4. Project Structure (What Each File Does)

- **`scenes/Main.tscn` & `scripts/Main.gd`:** The root orchestrator connecting player, rooms, telemetry, and UI.
- **`scenes/Player.tscn` & `scripts/Player.gd`:** Player movement, combat collision, health, and procedural visual drawing.
- **`scenes/Enemy.tscn` & `scripts/Enemy.gd`:** Dynamic adversary AI (Wander $\rightarrow$ Chase $\rightarrow$ Attack) whose stats scale directly with continuous vector $\vec{E}$.
- **`scenes/Room.tscn` & `scripts/Room.gd`:** Procedural room arena, walls, exit door logic, hazard traps, and pickup spawns.
- **`scenes/DefenseOverlay.tscn` & `scripts/DefenseOverlay.gd`:** The presentation overlay with sliders, preset buttons, and the explainability report.
- **`scripts/DifficultyManager.gd`:** Mathematical engine calculating the 0–100 difficulty score and feature attribution percentages.
- **`scripts/TelemetryLogger.gd`:** Handles JSON serialization of player session metrics.
