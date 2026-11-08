# FORGE playtest build: how to ship it and collect the data

## 1. Build
Project → Export (or the command line). Two Windows presets:

| Preset | Output | Use |
|---|---|---|
| **Windows Desktop** | `dist/FORGE.exe` | The build you give to testers. Has the `playtest` feature. |
| **Windows Desktop (Dev)** | `dist_dev/FORGE_dev.exe` | Your own build with the developer tools. |

```
.\godot --headless --path godot_prototype --export-release "Windows Desktop" dist/FORGE.exe
```
Send the whole `dist` folder (zip it): `FORGE.exe`, `FORGE.pck` and `libgdsqlite.windows.template_release.x86_64.dll`.
Without the DLL the game falls back to JSON telemetry. Bump `application/config/version` in
`project.godot` for each build you hand out; it is stored in every session row.

To try the playtest flavour without exporting: `.\godot --path godot_prototype -- --playtest`.

## 2. What testers see (playtest build)
- **First launch:** a consent screen ("Share my gameplay data" / "Don't share"; equal weight, no nudge).
  Stored in `user://forge_settings.cfg`; changeable in Main Menu → Data & Privacy.
- **After every floor** (consenting players only): "How hard did that floor feel?" 1–5
  (Very easy … Very hard), keys 1–5, Esc to skip. The game is paused while it is open.
- **No developer tools:** the Defense Panel, its Tab shortcut, the difficulty badge, the archetype-mix
  HUD text and the difficulty score on the floor banner are hidden, so testers play exactly what the
  policy generated and their ratings are not anchored by an on-screen "Hard (64/100)".

## 3. Collect the data
Each tester: Main Menu → Data & Privacy → **Open data folder**, and send `forge_telemetry.db`.
(Windows path: `%APPDATA%\Godot\app_userdata\FORGE - Adaptive Dungeon Prototype\`.)

Then, per file:
```
python -c "from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase as T; print(T().sync_from_game_db(r'path\to\forge_telemetry.db'))"
python ml_spike/analysis/export_telemetry.py ml_spike/telemetry_data/forge_telemetry.db corpus.csv --consented-only
```
Syncing is idempotent and sessions are keyed by random IDs, so files from different testers merge
safely into one database.

## 4. Data rules
- `sessions.consent = 1` only for testers who agreed. Use `--consented-only` for the study corpus.
- `floors.manual_override = 1`: the floor was changed with developer tools while it was played.
  It cannot happen in the playtest build. The Judge loader excludes such rows.
- `floors.perceived_difficulty`: the 1–5 rating, NULL when skipped or not consenting.
- If a developer regenerates the current floor, the attempt continues: time, deaths, damage and kills
  carry over (floor rows add up to the session totals). Session totals still include an unfinished
  last floor, which has no floor row.
