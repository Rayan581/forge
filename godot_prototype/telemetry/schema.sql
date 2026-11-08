-- FORGE telemetry schema (SQLite). Single source of truth for Godot (godot-sqlite) and Python.
-- Parsed by telemetry/TelemetrySQL.gd and ml_spike/analysis/export_telemetry.py:
--   * "-- bootstrap" runs on every open (idempotent).
--   * "-- migration vN" sections run in order once, when N > MAX(schema_version.version).
-- Rules: one statement per ";", no ";" inside strings/comments, comment lines start with "--".
-- Privacy: zero PII. install_id is a random UUID-like hex string generated on first run.

-- bootstrap
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- migration v1
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE sessions (
    id               TEXT PRIMARY KEY,
    install_id       TEXT NOT NULL,
    started_at       INTEGER NOT NULL,
    ended_at         INTEGER,
    game_version     TEXT NOT NULL DEFAULT '',
    mode             TEXT NOT NULL DEFAULT 'adaptive' CHECK (mode IN ('adaptive', 'static', 'unknown')),
    policy_version   TEXT NOT NULL DEFAULT '',
    consent          INTEGER NOT NULL DEFAULT 0 CHECK (consent IN (0, 1)),
    elapsed_seconds  REAL NOT NULL DEFAULT 0,
    rooms_cleared    INTEGER NOT NULL DEFAULT 0,
    total_deaths     INTEGER NOT NULL DEFAULT 0,
    damage_dealt     REAL NOT NULL DEFAULT 0,
    damage_taken     REAL NOT NULL DEFAULT 0,
    enemies_defeated INTEGER NOT NULL DEFAULT 0,
    pickups_collected INTEGER NOT NULL DEFAULT 0,
    hazard_hits      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_sessions_install ON sessions(install_id);

CREATE TABLE floors (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id            TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    floor_num             INTEGER NOT NULL,
    phase                 TEXT NOT NULL CHECK (phase IN ('calibration', 'adaptive', 'static')),
    completion_time       REAL NOT NULL,
    deaths                INTEGER NOT NULL DEFAULT 0,
    damage_taken          REAL NOT NULL DEFAULT 0,
    damage_dealt          REAL NOT NULL DEFAULT 0,
    player_max_hp         REAL,
    rooms_total           INTEGER NOT NULL DEFAULT 0,
    rooms_visited         INTEGER NOT NULL DEFAULT 0,
    exploration_pct       REAL NOT NULL DEFAULT 0,
    rooms_cleared         INTEGER NOT NULL DEFAULT 0,
    enemies_defeated      INTEGER NOT NULL DEFAULT 0,
    hazards_hit           INTEGER NOT NULL DEFAULT 0,
    pickups_collected     INTEGER NOT NULL DEFAULT 0,
    enemy_health          REAL,
    enemy_damage          REAL,
    enemy_speed           REAL,
    enemy_aggro           REAL,
    hazard_density        REAL,
    resource_scarcity     REAL,
    room_count            INTEGER,
    archetype_complexity  REAL,
    archetype_mix_0       REAL,
    archetype_mix_1       REAL,
    archetype_mix_2       REAL,
    archetype_mix_3       REAL,
    archetype_mix_4       REAL,
    enemy_count_scale     REAL,
    difficulty_score      REAL,
    action_0 REAL, action_1 REAL, action_2 REAL, action_3 REAL,
    action_4 REAL, action_5 REAL, action_6 REAL, action_7 REAL,
    obs_0 REAL, obs_1 REAL, obs_2 REAL, obs_3 REAL,
    obs_4 REAL, obs_5 REAL, obs_6 REAL, obs_7 REAL,
    frame_avg_ms          REAL,
    frame_p95_ms          REAL,
    frame_max_ms          REAL,
    perceived_difficulty  REAL,
    created_at            INTEGER NOT NULL,
    UNIQUE (session_id, floor_num)
);

CREATE INDEX idx_floors_session ON floors(session_id);

CREATE TABLE kills_by_archetype (
    floor_id      INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
    archetype_idx INTEGER NOT NULL,
    count         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (floor_id, archetype_idx)
);

CREATE INDEX idx_kills_floor ON kills_by_archetype(floor_id);

-- One row per floor, flattened for the Judge-model corpus / CSV export.
-- Column order: session fields, floor columns (floors order, id/session_id excluded), kills_0..kills_4.
CREATE VIEW v_corpus AS
SELECT
    s.id AS session_id,
    s.install_id AS install_id,
    s.mode AS mode,
    s.policy_version AS policy_version,
    s.game_version AS game_version,
    s.consent AS consent,
    f.floor_num, f.phase, f.completion_time, f.deaths, f.damage_taken, f.damage_dealt,
    f.player_max_hp, f.rooms_total, f.rooms_visited, f.exploration_pct, f.rooms_cleared,
    f.enemies_defeated, f.hazards_hit, f.pickups_collected,
    f.enemy_health, f.enemy_damage, f.enemy_speed, f.enemy_aggro, f.hazard_density,
    f.resource_scarcity, f.room_count, f.archetype_complexity,
    f.archetype_mix_0, f.archetype_mix_1, f.archetype_mix_2, f.archetype_mix_3, f.archetype_mix_4,
    f.enemy_count_scale, f.difficulty_score,
    f.action_0, f.action_1, f.action_2, f.action_3, f.action_4, f.action_5, f.action_6, f.action_7,
    f.obs_0, f.obs_1, f.obs_2, f.obs_3, f.obs_4, f.obs_5, f.obs_6, f.obs_7,
    f.frame_avg_ms, f.frame_p95_ms, f.frame_max_ms, f.perceived_difficulty, f.created_at,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 0), 0) AS kills_0,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 1), 0) AS kills_1,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 2), 0) AS kills_2,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 3), 0) AS kills_3,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 4), 0) AS kills_4
FROM floors f JOIN sessions s ON s.id = f.session_id;

-- migration v2
-- manual_override = 1 when developer tools changed the floor while it was being played (Defense Panel
-- sliders or presets, static-baseline toggle, regenerate, auto-kill). Its difficulty settings or
-- outcome then do not reflect the policy, so it is excluded from the Judge corpus. Existing rows get 0.
ALTER TABLE floors ADD COLUMN manual_override INTEGER NOT NULL DEFAULT 0 CHECK (manual_override IN (0, 1));

DROP VIEW v_corpus;

-- v_corpus as in v1 plus manual_override (same position as in insert_floor: after created_at).
CREATE VIEW v_corpus AS
SELECT
    s.id AS session_id,
    s.install_id AS install_id,
    s.mode AS mode,
    s.policy_version AS policy_version,
    s.game_version AS game_version,
    s.consent AS consent,
    f.floor_num, f.phase, f.completion_time, f.deaths, f.damage_taken, f.damage_dealt,
    f.player_max_hp, f.rooms_total, f.rooms_visited, f.exploration_pct, f.rooms_cleared,
    f.enemies_defeated, f.hazards_hit, f.pickups_collected,
    f.enemy_health, f.enemy_damage, f.enemy_speed, f.enemy_aggro, f.hazard_density,
    f.resource_scarcity, f.room_count, f.archetype_complexity,
    f.archetype_mix_0, f.archetype_mix_1, f.archetype_mix_2, f.archetype_mix_3, f.archetype_mix_4,
    f.enemy_count_scale, f.difficulty_score,
    f.action_0, f.action_1, f.action_2, f.action_3, f.action_4, f.action_5, f.action_6, f.action_7,
    f.obs_0, f.obs_1, f.obs_2, f.obs_3, f.obs_4, f.obs_5, f.obs_6, f.obs_7,
    f.frame_avg_ms, f.frame_p95_ms, f.frame_max_ms, f.perceived_difficulty, f.created_at,
    f.manual_override,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 0), 0) AS kills_0,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 1), 0) AS kills_1,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 2), 0) AS kills_2,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 3), 0) AS kills_3,
    COALESCE((SELECT k.count FROM kills_by_archetype k WHERE k.floor_id = f.id AND k.archetype_idx = 4), 0) AS kills_4
FROM floors f JOIN sessions s ON s.id = f.session_id;
