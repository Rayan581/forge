# Installing the SQLite telemetry addon (Windows)

FORGE logs gameplay telemetry (one row per floor, the training corpus for the difficulty "Judge" model)
to an embedded SQLite database, `user://forge_telemetry.db`, through the **Godot SQLite** plugin by
**2shady4u** (GDExtension class `SQLite`).

The game runs without the addon: if the `SQLite` class is missing, `TelemetryLogger` prints one warning
and falls back to the old JSON file (`user://session_telemetry.json`, now with per-floor data too).
Install the addon so the real database is used, and so exported builds contain it.

The compiled plugin binaries are **not** committed by Claude's branch; you add them once, as below.

## 1. Install via the Godot editor

1. Open the project in **Godot 4.7.x** (`godot_prototype/project.godot`).
2. Click the **AssetLib** tab at the top of the editor (next to 2D / 3D / Script).
3. Search for **Godot SQLite** and open the entry by **2shady4u**.
4. Click **Download**, wait for it to finish, then **Install**.
5. In the install dialog make sure the target is **`res://addons/godot-sqlite/`** and every file is ticked
   (including the `bin/` folder with the `.dll` files), then click **Install**.
6. Restart the editor when asked. You do **not** need to enable anything under Project > Project Settings > Plugins:
   this is a GDExtension and loads automatically through `addons/godot-sqlite/gdsqlite.gdextension`.

Note: release **v4.9** (built for Godot 4.7.x) was published only on the new Godot Asset Store, not on the old
AssetLib, so the AssetLib entry may offer an older build that does not match Godot 4.7. If AssetLib does not
list a version that says it supports Godot 4.7, use one of these instead:

- Godot Asset Store page: <https://store.godotengine.org/asset/tooshady4u/godot-sqlite/>
- Manual: download `addons.zip` from
  <https://github.com/2shady4u/godot-sqlite/releases/download/v4.9/addons.zip> and extract it so that
  the folder `godot_prototype/addons/godot-sqlite/` exists and contains `gdsqlite.gdextension` and `bin/`.
  (This is exactly what CI does.)

## 2. Check that it works

After the restart, the file `godot_prototype/addons/godot-sqlite/gdsqlite.gdextension` must exist and the
Output panel must show no "GDExtension" errors. From a terminal in the repo root:

    godot --headless --path godot_prototype --script tests/test_telemetry_sqlite.gd

Expected last line: `[FORGE TEST] telemetry SQLite: PASS (...)`. If it prints `SKIP (godot-sqlite not installed)`,
the extension did not load (wrong folder, or the editor was not restarted so `.godot/extension_list.cfg`
was not refreshed; run `godot --headless --import --path godot_prototype` once).

## 3. Commit the addon so builds include it

The `.dll` binaries must be in git, otherwise CI and exported builds silently fall back to JSON:

    git add godot_prototype/addons/godot-sqlite
    git commit -m "Add godot-sqlite addon (v4.9)"

(`.gitignore` does not exclude `addons/` or `*.dll`.) Keep `export_presets.cfg` on
`include_filter="telemetry/*.sql"`: the SQL files are loaded at runtime and are not Godot resources, so they
would otherwise be left out of the exported `.pck`. CI's PCK smoke test uses the same preset.

## Where the data lives and how to get it out

- Database: Windows `%APPDATA%\Godot\app_userdata\FORGE - Adaptive Dungeon Prototype\forge_telemetry.db`
  (Godot: Project > Open User Data Folder).
- The first SQLite run imports the old `session_telemetry.json` once (recorded in the `meta` table).
- CSV corpus (one row per floor), from the game: `telemetry_logger.export_corpus_csv("user://corpus.csv")`;
  from any `.db` copy, with plain Python:

      python ml_spike/analysis/export_telemetry.py forge_telemetry.db corpus.csv

- Schema and every SQL statement: `godot_prototype/telemetry/schema.sql` (migrations) and `queries.sql`.
  They are validated by `pytest ml_spike/tests/test_telemetry_schema.py`.
- No personal data is stored. `install_id` is a random 128-bit hex string created on first run
  (`user://forge_install_id.txt`); `consent` defaults to 0 until a consent UI sets `telemetry_logger.consent_given`.
