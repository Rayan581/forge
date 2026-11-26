## SQLite backend on top of the godot-sqlite GDExtension (class "SQLite", by 2shady4u).
## Instantiated through ClassDB so this script parses even when the addon is not installed.
extends "res://telemetry/TelemetryBackend.gd"

const TelemetrySQL = preload("res://telemetry/TelemetrySQL.gd")

var db_path: String
var legacy_json_path: String
var _db: Object = null
var _q: Dictionary = {}
var _floor_cols: PackedStringArray
var _session_cols: PackedStringArray
var _legacy_cols: PackedStringArray

func _init(p_db_path: String = "user://forge_telemetry.db", p_legacy_json_path: String = "") -> void:
	db_path = p_db_path
	legacy_json_path = p_legacy_json_path

static func is_available() -> bool:
	return ClassDB.class_exists("SQLite")

func backend_name() -> String:
	return "sqlite"

func open() -> bool:
	if not is_available():
		last_error = "godot-sqlite not installed"
		return false
	_q = TelemetrySQL.load_queries()
	if _q.is_empty():
		last_error = "queries.sql missing or empty"
		return false
	_floor_cols = TelemetrySQL.insert_columns(_q["insert_floor"])
	_session_cols = TelemetrySQL.insert_columns(_q["upsert_session"])
	_legacy_cols = TelemetrySQL.insert_columns(_q["insert_legacy_session"])
	_db = ClassDB.instantiate("SQLite")
	_db.set("path", db_path)
	_db.set("verbosity_level", 0)
	_db.set("foreign_keys", true)
	if not _db.call("open_db"):
		last_error = "open_db failed: " + str(_db.get("error_message"))
		_db = null
		return false
	if not _migrate():
		close()
		return false
	_import_legacy_once()
	return true

func close() -> void:
	if _db != null:
		_db.call("close_db")
		_db = null

func _exec(sql: String, params: Array = []) -> bool:
	var ok: bool
	if params.is_empty():
		ok = _db.call("query", sql)
	else:
		ok = _db.call("query_with_bindings", sql, params)
	if not ok:
		last_error = str(_db.get("error_message"))
	return ok

func _rows() -> Array:
	return _db.get("query_result")

func _begin() -> bool:
	return _exec("BEGIN;")

func _commit() -> bool:
	return _exec("COMMIT;")

func _rollback() -> void:
	_db.call("query", "ROLLBACK;")

func _migrate() -> bool:
	var schema := TelemetrySQL.load_schema()
	for stmt in schema["bootstrap"]:
		if not _exec(stmt + ";"):
			return false
	if not _exec(_q["get_schema_version"]):
		return false
	var current: int = int(_rows()[0]["v"])
	for mig in schema["migrations"]:
		if int(mig["version"]) <= current:
			continue
		if not _begin():
			return false
		var ok := true
		for stmt in mig["statements"]:
			if not _exec(stmt + ";"):
				ok = false
				break
		if ok:
			ok = _exec(_q["insert_schema_version"], [int(mig["version"]), int(Time.get_unix_time_from_system())])
		if not ok:
			_rollback()
			return false
		if not _commit():
			_rollback()
			return false
		current = int(mig["version"])
	return true

func _params_for(cols: PackedStringArray, row: Dictionary) -> Array:
	var p: Array = []
	for c in cols:
		var v: Variant = row.get(c, null)
		if v is bool:
			v = 1 if v else 0
		p.append(v)
	return p

func save_session(session: Dictionary) -> bool:
	if _db == null:
		return false
	return _exec(_q["upsert_session"], _params_for(_session_cols, session))

func save_floor(floor_row: Dictionary, kills: Dictionary) -> bool:
	if _db == null or not _begin():
		return false
	var ok := _exec(_q["insert_floor"], _params_for(_floor_cols, floor_row))
	if ok:
		var floor_id: int = int(_db.get("last_insert_rowid"))
		for idx in kills.keys():
			if int(kills[idx]) <= 0:
				continue
			if not _exec(_q["insert_kill"], [floor_id, int(idx), int(kills[idx])]):
				ok = false
				break
	if not ok:
		_rollback()
		return false
	if not _commit():
		_rollback()
		return false
	return true

func get_floors(session_id: String) -> Array:
	var out: Array = []
	if _db == null or not _exec(_q["select_floors"], [session_id]):
		return out
	var floors: Array = _rows().duplicate(true)
	for fl in floors:
		var kills := {}
		if _exec(_q["select_kills"], [int(fl["id"])]):
			for r in _rows():
				kills[int(r["archetype_idx"])] = int(r["count"])
		fl["kills"] = kills
		out.append(fl)
	return out

func get_session(session_id: String) -> Dictionary:
	if _db != null and _exec(_q["select_session"], [session_id]) and _rows().size() > 0:
		return _rows()[0].duplicate(true)
	return {}

func set_perceived_difficulty(session_id: String, floor_num: int, value: float) -> bool:
	return _db != null and _exec(_q["set_perceived_difficulty"], [value, session_id, floor_num])

func export_corpus_csv(path: String, consented_only: bool = false) -> int:
	if _db == null:
		return -1
	if not _exec(_q["corpus_columns"]):
		return -1
	var header: Array = []
	for r in _rows():
		header.append(r["name"])
	if not _exec(_q["export_corpus_consented" if consented_only else "export_corpus"]):
		return -1
	var rows: Array = []
	for r in _rows():
		var line: Array = []
		for h in header:
			line.append(r.get(h, null))
		rows.append(line)
	if not write_csv(path, header, rows):
		last_error = "cannot write " + path
		return -1
	return rows.size()

## Imports the legacy flat-JSON history (user://session_telemetry.json) exactly once.
func _import_legacy_once() -> void:
	if legacy_json_path.is_empty() or not _exec(_q["get_meta"], ["legacy_json_imported"]):
		return
	if _rows().size() > 0 or not FileAccess.file_exists(legacy_json_path):
		return
	var f := FileAccess.open(legacy_json_path, FileAccess.READ)
	if f == null:
		return
	var json := JSON.new()
	var parsed_ok := json.parse(f.get_as_text()) == OK
	f.close()
	if not parsed_ok or not (json.data is Array):
		return
	# The legacy writer appended a snapshot per save; keep only the last one per session id.
	var latest: Dictionary = {}
	for entry in json.data:
		if entry is Dictionary and entry.has("session_id"):
			latest[str(entry["session_id"])] = entry
	if not _begin():
		return
	var ok := true
	for sid in latest.keys():
		var e: Dictionary = latest[sid]
		var started := int(e.get("timestamp", 0))
		var row := {
			"id": sid, "install_id": "legacy", "started_at": started,
			"ended_at": started + int(float(e.get("elapsed_seconds", 0.0))),
			"game_version": "legacy-json", "mode": "unknown", "policy_version": "", "consent": 0,
			"elapsed_seconds": float(e.get("elapsed_seconds", 0.0)),
			"rooms_cleared": int(e.get("rooms_cleared", 0)),
			"total_deaths": int(e.get("total_deaths", 0)),
			"damage_dealt": float(e.get("damage_dealt", 0.0)),
			"damage_taken": float(e.get("damage_taken", 0.0)),
			"enemies_defeated": int(e.get("enemies_defeated", 0)),
			"pickups_collected": int(e.get("pickups_collected", 0)),
			"hazard_hits": int(e.get("hazard_hits", 0)),
		}
		if not _exec(_q["insert_legacy_session"], _params_for(_legacy_cols, row)):
			ok = false
			break
	if ok:
		ok = _exec(_q["set_meta"], ["legacy_json_imported", "%d sessions @ %d" % [latest.size(), int(Time.get_unix_time_from_system())]])
	if ok and _commit():
		print("[TelemetryLogger] Imported %d legacy session(s) from %s" % [latest.size(), legacy_json_path])
	else:
		_rollback()
