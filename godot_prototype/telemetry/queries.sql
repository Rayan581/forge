-- FORGE telemetry queries. Named blocks: "-- name: <id>" then one SQL statement ending in ";".
-- All use "?" positional bindings (godot-sqlite query_with_bindings). For INSERT/UPSERT statements the
-- bind order is the column list of the first "(...)" group, so callers build params from that list.

-- name: get_schema_version
SELECT COALESCE(MAX(version), 0) AS v FROM schema_version;

-- name: insert_schema_version
INSERT INTO schema_version (version, applied_at) VALUES (?, ?);

-- name: get_meta
SELECT value FROM meta WHERE key = ?;

-- name: set_meta
INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value;

-- name: upsert_session
INSERT INTO sessions (id, install_id, started_at, ended_at, game_version, mode, policy_version, consent, elapsed_seconds, rooms_cleared, total_deaths, damage_dealt, damage_taken, enemies_defeated, pickups_collected, hazard_hits)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    ended_at = excluded.ended_at,
    game_version = excluded.game_version,
    mode = excluded.mode,
    policy_version = excluded.policy_version,
    consent = excluded.consent,
    elapsed_seconds = excluded.elapsed_seconds,
    rooms_cleared = excluded.rooms_cleared,
    total_deaths = excluded.total_deaths,
    damage_dealt = excluded.damage_dealt,
    damage_taken = excluded.damage_taken,
    enemies_defeated = excluded.enemies_defeated,
    pickups_collected = excluded.pickups_collected,
    hazard_hits = excluded.hazard_hits;

-- Legacy import: never overwrites a row that already exists.
-- name: insert_legacy_session
INSERT OR IGNORE INTO sessions (id, install_id, started_at, ended_at, game_version, mode, policy_version, consent, elapsed_seconds, rooms_cleared, total_deaths, damage_dealt, damage_taken, enemies_defeated, pickups_collected, hazard_hits)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: insert_floor
INSERT INTO floors (session_id, floor_num, phase, completion_time, deaths, damage_taken, damage_dealt, player_max_hp, rooms_total, rooms_visited, exploration_pct, rooms_cleared, enemies_defeated, hazards_hit, pickups_collected, enemy_health, enemy_damage, enemy_speed, enemy_aggro, hazard_density, resource_scarcity, room_count, archetype_complexity, archetype_mix_0, archetype_mix_1, archetype_mix_2, archetype_mix_3, archetype_mix_4, enemy_count_scale, difficulty_score, action_0, action_1, action_2, action_3, action_4, action_5, action_6, action_7, obs_0, obs_1, obs_2, obs_3, obs_4, obs_5, obs_6, obs_7, frame_avg_ms, frame_p95_ms, frame_max_ms, perceived_difficulty, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- name: insert_kill
INSERT INTO kills_by_archetype (floor_id, archetype_idx, count) VALUES (?, ?, ?);

-- name: set_perceived_difficulty
UPDATE floors SET perceived_difficulty = ? WHERE session_id = ? AND floor_num = ?;

-- name: select_floors
SELECT * FROM floors WHERE session_id = ? ORDER BY floor_num;

-- name: select_kills
SELECT archetype_idx, count FROM kills_by_archetype WHERE floor_id = ? ORDER BY archetype_idx;

-- name: select_session
SELECT * FROM sessions WHERE id = ?;

-- name: corpus_columns
PRAGMA table_info(v_corpus);

-- name: export_corpus
SELECT * FROM v_corpus ORDER BY session_id, floor_num;

-- name: export_corpus_consented
SELECT * FROM v_corpus WHERE consent = 1 ORDER BY session_id, floor_num;
