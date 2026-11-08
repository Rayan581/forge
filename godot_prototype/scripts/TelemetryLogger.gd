class_name TelemetryLogger
extends RefCounted

var session_id: String = ""
var start_timestamp: int = 0
var elapsed_seconds: float = 0.0
var rooms_cleared: int = 0
var total_deaths: int = 0
var damage_dealt: float = 0.0
var damage_taken: float = 0.0
var enemies_defeated: int = 0
var pickups_collected: int = 0
var hazard_hits: int = 0

# Per-Floor Cold-Start Calibration Records (Floors 1 to 5)
var calibration_records: Array = []

const TELEMETRY_FILE_PATH = "user://session_telemetry.json"

# ---------------------------------------------------------------------------------------------
# Storage backends: SQLite (godot-sqlite addon, class "SQLite") when installed, else JSON fallback.
# All SQL lives in res://telemetry/schema.sql + queries.sql (shared with the Python tests/export).
# ---------------------------------------------------------------------------------------------
const TelemetrySQL = preload("res://telemetry/TelemetrySQL.gd")
const SqliteBackend = preload("res://telemetry/SqliteBackend.gd")
const JsonBackend = preload("res://telemetry/JsonBackend.gd")
const BuildInfoScript = preload("res://scripts/BuildInfo.gd")

const DB_FILE_PATH := "user://forge_telemetry.db"
const INSTALL_ID_PATH := "user://forge_install_id.txt"
const POLICY_PATH := "res://ai/policy_weights.json"
const FRAME_SAMPLE_CAP := 72000 # ~20 min at 60 FPS per floor; later samples are dropped

## "auto" (SQLite if the addon exists, else JSON), "sqlite" or "json" (force; used by tests).
var backend_preference: String = "auto"
var db_path: String = DB_FILE_PATH
var json_path: String = TELEMETRY_FILE_PATH
var install_id_path: String = INSTALL_ID_PATH
## Playtester consent to contribute data to the Judge corpus. Defaults to false (zero PII either way).
var consent_given: bool = false
var game_version: String = ""
var mode: String = "adaptive"       # "adaptive" | "static"
var policy_version: String = ""

var started_at: int = 0
var install_id: String = ""
var _backend: RefCounted = null
var _backend_tried: bool = false

# Per-floor accumulators (reset by begin_floor / after record_floor)
var floor_num: int = 1
var floor_rooms_total: int = 0
var floor_time: float = 0.0
var floor_deaths: int = 0
var floor_damage_taken: float = 0.0
var floor_damage_dealt: float = 0.0
var floor_enemies_defeated: int = 0
var floor_hazard_hits: int = 0
var floor_pickups: int = 0
var floor_rooms_cleared: int = 0
var floor_kills: Dictionary = {}          # archetype_idx -> count
## Set when developer tools touched this floor (see mark_manual_override); stored as floors.manual_override.
var floor_manual_override: bool = false
var floor_override_reasons: PackedStringArray = PackedStringArray()
var _floor_rooms_visited: Dictionary = {} # room key -> true
var _frame_ms: PackedFloat32Array = PackedFloat32Array()
var _pending_obs: PackedFloat32Array = PackedFloat32Array()
var _pending_action: PackedFloat32Array = PackedFloat32Array()
var floor_history: Array = []

func _init() -> void:
	start_new_session()

func start_new_session() -> void:
	started_at = int(Time.get_unix_time_from_system())
	session_id = "sess_%d_%04x" % [started_at, randi() & 0xFFFF]
	start_timestamp = int(Time.get_unix_time_from_system())
	elapsed_seconds = 0.0
	rooms_cleared = 0
	total_deaths = 0
	damage_dealt = 0.0
	damage_taken = 0.0
	enemies_defeated = 0
	pickups_collected = 0
	hazard_hits = 0
	floor_history = []
	_reset_floor_state(1, 0)

func update_time(delta: float) -> void:
	elapsed_seconds += delta
	floor_time += delta

func record_death() -> void:
	total_deaths += 1
	floor_deaths += 1

func record_room_cleared() -> void:
	rooms_cleared += 1
	floor_rooms_cleared += 1

func record_damage_dealt(amount: float) -> void:
	damage_dealt += amount
	floor_damage_dealt += amount

func record_damage_taken(amount: float) -> void:
	damage_taken += amount
	floor_damage_taken += amount

func record_enemy_defeated() -> void:
	enemies_defeated += 1
	floor_enemies_defeated += 1

func record_pickup_collected() -> void:
	pickups_collected += 1
	floor_pickups += 1

func record_hazard_hit() -> void:
	hazard_hits += 1
	floor_hazard_hits += 1

## Records a completed calibration floor's performance slice along with its difficulty challenge rating
func record_calibration_floor(floor_num: int, completion_time_sec: float, deaths: int, damage_taken: float, expected_rooms: int, diff_score: int) -> void:
	calibration_records.append({
		"floor": floor_num,
		"time": completion_time_sec,
		"deaths": deaths,
		"damage": damage_taken,
		"rooms": expected_rooms,
		"diff_score": diff_score,
		# Pace per room: normal is ~7.5s/room
		"sec_per_room": completion_time_sec / maxf(1.0, float(expected_rooms))
	})
	print("[TelemetryLogger] Recorded Calibration Floor %d: %.1fs (%d rooms, %d deaths, %.0f dmg, diff=%d)" % [
		floor_num, completion_time_sec, expected_rooms, deaths, damage_taken, diff_score
	])

## Computes the composite Cold-Start Initial Combat Rating (CR₀) across all 5 calibration levels.
## Higher difficulty levels are weighted significantly more heavily than introductory floors:
## Floor 1 weight = 1.0 (Novice Pacing)
## Floor 2 weight = 1.5 (Melee Reflex)
## Floor 3 weight = 2.0 (Hazard & Agile Evasion)
## Floor 4 weight = 2.5 (Tactical Attrition)
## Floor 5 weight = 3.0 (Apex Gauntlet Stress Test)
## Total Weight = 10.0
func compute_cr0_baseline(player_max_health: float = 100.0) -> Dictionary:
	if calibration_records.is_empty():
		return {
			"cr0_score": 50.0,
			"obs_time": 0.5,
			"obs_deaths": 0.0,
			"obs_dmg_ratio": 0.3,
			"weighted_time_ratio": 0.5,
			"weighted_death_ratio": 0.0,
			"weighted_damage_ratio": 0.3,
			"tier_name": "Intermediate"
		}
		
	var weights = [1.0, 1.5, 2.0, 2.5, 3.0]
	var total_weight: float = 0.0
	var weighted_pace_score: float = 0.0
	var weighted_death_score: float = 0.0
	var weighted_dmg_score: float = 0.0
	# Weighted averages of the three player signals on the SAME scales the PPO policy
	# was trained on (train_ppo_difficulty.py::_get_obs): floor time / 90 s for a
	# 6-room floor, deaths / 3, damage taken / player max health.
	var weighted_obs_time: float = 0.0
	var weighted_obs_deaths: float = 0.0
	var weighted_obs_dmg: float = 0.0
	
	for i in range(calibration_records.size()):
		var rec = calibration_records[i]
		var w = weights[clampi(i, 0, weights.size() - 1)]
		total_weight += w
		
		# Ideal pace per room is ~7.5 seconds
		# Fast clear (< 5s/room) scores high (0.8-1.0), Slow (> 15s/room) scores low (0.0-0.3)
		var pace_ratio = clampf(1.0 - (rec.sec_per_room - 5.0) / 12.0, 0.0, 1.0)
		weighted_pace_score += pace_ratio * w
		
		# Death penalty: 0 deaths = 1.0, 1 death = 0.5, >= 2 deaths = 0.0
		var survival_ratio = clampf(1.0 - float(rec.deaths) * 0.5, 0.0, 1.0)
		weighted_death_score += survival_ratio * w
		
		# Damage intake ratio per 100 HP
		var dmg_ratio = clampf(1.0 - (rec.damage / 120.0), 0.0, 1.0)
		weighted_dmg_score += dmg_ratio * w

		weighted_obs_time += clampf(rec.sec_per_room * 6.0 / 90.0, 0.0, 1.0) * w
		weighted_obs_deaths += clampf(float(rec.deaths) / 3.0, 0.0, 1.0) * w
		weighted_obs_dmg += clampf(rec.damage / maxf(1.0, player_max_health), 0.0, 1.0) * w
		
	var avg_pace = weighted_pace_score / total_weight
	var avg_survival = weighted_death_score / total_weight
	var avg_dmg_defense = weighted_dmg_score / total_weight
	
	# Initial Combat Rating CR0 (0 to 100 scale):
	# 40% Survival Execution + 35% Combat Efficiency & Defense + 25% Pace
	var cr0 = (avg_survival * 40.0) + (avg_dmg_defense * 35.0) + (avg_pace * 25.0)
	cr0 = clampf(cr0, 10.0, 95.0)
	
	var tier = "Intermediate"
	if cr0 < 40.0:
		tier = "Novice (Adaptive Scaling Down)"
	elif cr0 < 70.0:
		tier = "Intermediate (Balanced Adaptive)"
	else:
		tier = "Expert (High-Intensity Adaptive)"
		
	return {
		"cr0_score": cr0,
		"obs_time": weighted_obs_time / total_weight,
		"obs_deaths": weighted_obs_deaths / total_weight,
		"obs_dmg_ratio": weighted_obs_dmg / total_weight,
		"weighted_time_ratio": clampf(1.0 - avg_pace, 0.0, 1.0),
		"weighted_death_ratio": clampf(1.0 - avg_survival, 0.0, 1.0),
		"weighted_damage_ratio": clampf(1.0 - avg_dmg_defense, 0.0, 1.0),
		"tier_name": tier
	}

func get_summary() -> Dictionary:
	return {
		"session_id": session_id,
		"timestamp": start_timestamp,
		"elapsed_seconds": snappedf(elapsed_seconds, 0.1),
		"rooms_cleared": rooms_cleared,
		"total_deaths": total_deaths,
		"damage_dealt": snappedf(damage_dealt, 0.1),
		"damage_taken": snappedf(damage_taken, 0.1),
		"enemies_defeated": enemies_defeated,
		"pickups_collected": pickups_collected,
		"hazard_hits": hazard_hits,
		"exploration_efficiency": snappedf(float(rooms_cleared) / maxf(1.0, elapsed_seconds / 60.0), 0.01)
	}

## Persists the session summary. SQLite: upserts the `sessions` row. JSON fallback: replaces this
## session's entry in the history file (legacy behaviour appended a duplicate snapshot per call).
func save_to_file() -> void:
	var b := _ensure_backend()
	if b == null:
		return
	if b.save_session(_session_row()):
		print("[TelemetryLogger] Logged session via %s backend" % b.backend_name())
	else:
		print("[TelemetryLogger] WARNING: failed to log session (%s)" % b.last_error)

# ---------------------------------------------------------------------------------------------
# Per-floor recording (Judge-model corpus)
# ---------------------------------------------------------------------------------------------

func _reset_floor_state(p_floor_num: int, p_rooms_total: int) -> void:
	floor_num = p_floor_num
	floor_rooms_total = p_rooms_total
	floor_time = 0.0
	floor_deaths = 0
	floor_damage_taken = 0.0
	floor_damage_dealt = 0.0
	floor_enemies_defeated = 0
	floor_hazard_hits = 0
	floor_pickups = 0
	floor_rooms_cleared = 0
	floor_kills = {}
	floor_manual_override = false
	floor_override_reasons = PackedStringArray()
	_floor_rooms_visited = {}
	_frame_ms = PackedFloat32Array()

## Call when a new floor is built: resets the per-floor accumulators.
func begin_floor(p_floor_num: int, p_rooms_total: int) -> void:
	_reset_floor_state(p_floor_num, p_rooms_total)

## Call when the CURRENT floor is rebuilt with a new layout (Defense Panel "regenerate", preset, static
## toggle). The attempt continues: deaths, damage, kills, time and frames carry over, so the floor row
## and the session totals stay consistent. Only the room set changes (rooms_total / visited restart on
## the new layout). The floor is flagged as manually overridden.
func restart_floor_layout(p_rooms_total: int) -> void:
	floor_rooms_total = p_rooms_total
	_floor_rooms_visited = {}
	mark_manual_override("regenerated layout")

## Flags the current floor: a developer tool changed its settings or outcome while it was played, so
## the row must not be used as policy/Judge training data (floors.manual_override = 1).
func mark_manual_override(reason: String) -> void:
	floor_manual_override = true
	if not floor_override_reasons.has(reason):
		floor_override_reasons.append(reason)

## Marks a room as visited on the current floor (key can be a Vector2i grid position, an id, ...).
func record_room_visited(room_key: Variant) -> void:
	_floor_rooms_visited[room_key] = true

## Adds one defeated enemy body of the given archetype (Enemy.Archetype index) to the current floor.
## Does NOT touch `enemies_defeated`; keep calling record_enemy_defeated() for the total.
func record_enemy_defeated_by_archetype(archetype_idx: int) -> void:
	floor_kills[archetype_idx] = int(floor_kills.get(archetype_idx, 0)) + 1

## Samples one frame (call from _process with the frame delta in seconds). Feeds avg/p95/max ms.
## NOTE: this only records frame-time statistics; the 60 FPS non-functional requirement (NFR-05)
## is not asserted or measured against a target anywhere yet.
func record_frame(delta: float) -> void:
	if delta > 0.0 and _frame_ms.size() < FRAME_SAMPLE_CAP:
		_frame_ms.append(delta * 1000.0)

## Remembers the PPO observation/action that produced the NEXT floor's parameters; attached to that
## floor's row by record_floor(). Floors without a policy step (calibration, static) store NULLs.
func note_policy_step(obs: PackedFloat32Array, action: PackedFloat32Array) -> void:
	_pending_obs = obs.duplicate()
	_pending_action = action.duplicate()

func get_frame_stats() -> Dictionary:
	var n := _frame_ms.size()
	if n == 0:
		return {"avg_ms": null, "p95_ms": null, "max_ms": null}
	var sorted := _frame_ms.duplicate()
	sorted.sort()
	var total := 0.0
	for v in sorted:
		total += v
	var idx := clampi(int(ceil(0.95 * n)) - 1, 0, n - 1)
	return {"avg_ms": total / n, "p95_ms": sorted[idx], "max_ms": sorted[n - 1]}

static func _obj_get(obj: Object, prop: String) -> Variant:
	if obj == null:
		return null
	return obj.get(prop) # null when the property does not exist (older / newer DifficultyManager)

## Records a finished floor: builds one `floors` row (+ kills_by_archetype) and stores it in a single
## transaction. `p_diff` is the DifficultyManager holding the params the floor was played with;
## `extras` may override/add: floor_num, completion_time, deaths, damage_taken, damage_dealt,
## player_max_hp, rooms_total, rooms_visited, phase, difficulty_score, obs, action, perceived_difficulty.
## Missing DifficultyManager fields (e.g. archetype_*) are stored as NULL. Returns true if persisted.
func record_floor(p_diff: Object, extras: Dictionary = {}) -> bool:
	var fnum: int = int(extras.get("floor_num", floor_num))
	var rooms_total: int = int(extras.get("rooms_total", floor_rooms_total))
	var rooms_visited: int = int(extras.get("rooms_visited", _floor_rooms_visited.size()))
	var phase: String = str(extras.get("phase", ""))
	if phase.is_empty():
		if _obj_get(p_diff, "static_baseline_mode") == true:
			phase = "static"
		elif p_diff != null and p_diff.has_method("is_in_calibration") and p_diff.is_in_calibration(fnum):
			phase = "calibration"
		else:
			phase = "adaptive"
	mode = "static" if phase == "static" or _obj_get(p_diff, "static_baseline_mode") == true else "adaptive"

	var score: Variant = extras.get("difficulty_score", null)
	if score == null and p_diff != null and p_diff.has_method("calculate_difficulty_score"):
		var rep: Dictionary = p_diff.calculate_difficulty_score()
		score = float(rep.get("score", 0.0))

	var row: Dictionary = {
		"session_id": session_id,
		"floor_num": fnum,
		"phase": phase,
		"completion_time": float(extras.get("completion_time", floor_time)),
		"deaths": int(extras.get("deaths", floor_deaths)),
		"damage_taken": float(extras.get("damage_taken", floor_damage_taken)),
		"damage_dealt": float(extras.get("damage_dealt", floor_damage_dealt)),
		"player_max_hp": extras.get("player_max_hp", null),
		"rooms_total": rooms_total,
		"rooms_visited": rooms_visited,
		"exploration_pct": 100.0 * float(rooms_visited) / maxf(1.0, float(rooms_total)) if rooms_total > 0 else 0.0,
		"rooms_cleared": int(extras.get("rooms_cleared", floor_rooms_cleared)),
		"enemies_defeated": int(extras.get("enemies_defeated", floor_enemies_defeated)),
		"hazards_hit": int(extras.get("hazards_hit", floor_hazard_hits)),
		"pickups_collected": int(extras.get("pickups_collected", floor_pickups)),
		"enemy_health": _obj_get(p_diff, "enemy_health"),
		"enemy_damage": _obj_get(p_diff, "enemy_damage"),
		"enemy_speed": _obj_get(p_diff, "enemy_speed"),
		"enemy_aggro": _obj_get(p_diff, "enemy_aggro"),
		"hazard_density": _obj_get(p_diff, "hazard_density"),
		"resource_scarcity": _obj_get(p_diff, "resource_scarcity"),
		"room_count": _obj_get(p_diff, "room_count_target"),
		"archetype_complexity": _obj_get(p_diff, "archetype_complexity"),
		"enemy_count_scale": _obj_get(p_diff, "enemy_count_scale"),
		"difficulty_score": score,
		"perceived_difficulty": extras.get("perceived_difficulty", null),
		"created_at": int(Time.get_unix_time_from_system()),
		"manual_override": 1 if (floor_manual_override or bool(extras.get("manual_override", false))) else 0,
	}
	var mix: Variant = _obj_get(p_diff, "archetype_mix")
	for a in range(5):
		row["archetype_mix_%d" % a] = float(mix[a]) if (mix is PackedFloat32Array or mix is Array) and mix.size() > a else null
	var obs: Variant = extras.get("obs", _pending_obs)
	var act: Variant = extras.get("action", _pending_action)
	for k in range(8):
		row["obs_%d" % k] = float(obs[k]) if obs.size() > k else null
		row["action_%d" % k] = float(act[k]) if act.size() > k else null
	var fs := get_frame_stats()
	row["frame_avg_ms"] = fs["avg_ms"]
	row["frame_p95_ms"] = fs["p95_ms"]
	row["frame_max_ms"] = fs["max_ms"]

	var kills: Dictionary = floor_kills.duplicate()
	var hist: Dictionary = row.duplicate()
	hist["kills"] = kills
	floor_history.append(hist)
	_pending_obs = PackedFloat32Array()
	_pending_action = PackedFloat32Array()

	if row["manual_override"] == 1:
		print("[TelemetryLogger] Floor %d flagged manual_override (%s): excluded from the Judge corpus" % [
			fnum, ", ".join(floor_override_reasons) if not floor_override_reasons.is_empty() else "extras"])

	var persisted := false
	var b := _ensure_backend()
	if b != null:
		persisted = b.save_session(_session_row()) and b.save_floor(row, kills)
		if not persisted:
			print("[TelemetryLogger] WARNING: failed to log floor %d (%s)" % [fnum, b.last_error])
	_reset_floor_state(fnum + 1, 0)
	return persisted

## In-memory floors recorded this session (each row has a "kills" Dictionary).
func get_floor_history() -> Array:
	return floor_history.duplicate(true)

## Floors of any session read back from the active backend (SQLite or JSON).
func load_floors(p_session_id: String) -> Array:
	var b := _ensure_backend()
	return b.get_floors(p_session_id) if b != null else []

## Stores the post-floor difficulty rating (1 = very easy .. 5 = very hard, from FloorRating) for an
## already recorded floor of this session. Also updates the in-memory floor history.
func set_perceived_difficulty(p_floor_num: int, value: float) -> bool:
	for h in floor_history:
		if int(h.get("floor_num", -1)) == p_floor_num:
			h["perceived_difficulty"] = value
	var b := _ensure_backend()
	return b != null and b.set_perceived_difficulty(session_id, p_floor_num, value)

## One CSV row per recorded floor across all sessions in the active backend. Returns the row count or -1.
func export_corpus_csv(path: String, consented_only: bool = false) -> int:
	var b := _ensure_backend()
	return b.export_corpus_csv(path, consented_only) if b != null else -1

func get_backend_name() -> String:
	var b := _ensure_backend()
	return b.backend_name() if b != null else "none"

## Closes the database (flushes nothing extra: every write is already committed).
func close() -> void:
	if _backend != null:
		_backend.close()
		_backend = null
	_backend_tried = false

# ---------------------------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------------------------

func _ensure_backend() -> RefCounted:
	if _backend != null:
		return _backend
	if _backend_tried:
		return null
	_backend_tried = true
	if backend_preference != "json" and SqliteBackend.is_available():
		var sb = SqliteBackend.new(db_path, json_path)
		if sb.open():
			_backend = sb
			return _backend
		print("[TelemetryLogger] WARNING: SQLite open failed (%s); using JSON fallback" % sb.last_error)
	elif backend_preference == "sqlite":
		print("[TelemetryLogger] WARNING: godot-sqlite not installed; using JSON fallback")
	elif backend_preference == "auto":
		print("[TelemetryLogger] WARNING: godot-sqlite not installed - telemetry falls back to JSON (see addons/README_SQLITE.md)")
	var jb = JsonBackend.new(json_path)
	var q := TelemetrySQL.load_queries()
	if q.has("insert_floor"):
		jb.floor_columns = TelemetrySQL.insert_columns(q["insert_floor"])
	jb.open()
	_backend = jb
	return _backend

func _load_install_id() -> String:
	if not install_id.is_empty():
		return install_id
	if FileAccess.file_exists(install_id_path):
		var f := FileAccess.open(install_id_path, FileAccess.READ)
		if f:
			install_id = f.get_as_text().strip_edges()
			f.close()
	if install_id.is_empty():
		install_id = Crypto.new().generate_random_bytes(16).hex_encode() # random, not derived from the machine
		var fw := FileAccess.open(install_id_path, FileAccess.WRITE)
		if fw:
			fw.store_string(install_id)
			fw.close()
	return install_id

## application/config/version + build flavour (e.g. "0.9.0-playtest"). The old code stored "" because
## the project had no version set and get_setting() returns the empty string, not the default.
func _game_version() -> String:
	if game_version.is_empty():
		game_version = BuildInfoScript.version()
	return game_version

func _policy_version() -> String:
	if policy_version.is_empty():
		var md5 := FileAccess.get_md5(POLICY_PATH)
		policy_version = ("md5:" + md5.substr(0, 12)) if not md5.is_empty() else "heuristic"
	return policy_version

## Session row keyed by queries.sql column names, plus the legacy summary keys for the JSON file.
func _session_row() -> Dictionary:
	var row: Dictionary = get_summary()
	row["id"] = session_id
	row["install_id"] = _load_install_id()
	row["started_at"] = started_at
	row["ended_at"] = int(Time.get_unix_time_from_system())
	row["game_version"] = _game_version()
	row["mode"] = mode
	row["policy_version"] = _policy_version()
	row["consent"] = 1 if consent_given else 0
	row["elapsed_seconds"] = elapsed_seconds
	row["damage_dealt"] = damage_dealt
	row["damage_taken"] = damage_taken
	return row
