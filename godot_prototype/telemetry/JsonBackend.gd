## JSON fallback backend (used when godot-sqlite is not installed). Keeps the legacy file format:
## an Array of session dictionaries (legacy summary keys + new fields + "floors": Array).
extends "res://telemetry/TelemetryBackend.gd"

const MAX_SESSIONS := 50

var json_path: String
var floor_columns: PackedStringArray = []   # insert_floor column order (set by the logger)
var _sessions: Array = []

func _init(p_json_path: String = "user://session_telemetry.json") -> void:
	json_path = p_json_path

func backend_name() -> String:
	return "json"

func open() -> bool:
	_sessions = []
	if FileAccess.file_exists(json_path):
		var f := FileAccess.open(json_path, FileAccess.READ)
		if f:
			var json := JSON.new()
			if json.parse(f.get_as_text()) == OK and json.data is Array:
				_sessions = json.data
			f.close()
	return true

func _find(session_id: String) -> int:
	for i in range(_sessions.size()):
		if _sessions[i] is Dictionary and str(_sessions[i].get("session_id", "")) == session_id:
			return i
	return -1

func _flush() -> bool:
	if _sessions.size() > MAX_SESSIONS:
		_sessions = _sessions.slice(_sessions.size() - MAX_SESSIONS)
	var f := FileAccess.open(json_path, FileAccess.WRITE)
	if f == null:
		last_error = "cannot write " + json_path
		return false
	f.store_string(JSON.stringify(_sessions, "\t"))
	f.close()
	return true

func save_session(session: Dictionary) -> bool:
	var entry: Dictionary = session.duplicate(true)
	entry["session_id"] = session.get("id", session.get("session_id", ""))
	var i := _find(str(entry["session_id"]))
	if i >= 0:
		entry["floors"] = _sessions[i].get("floors", [])
		_sessions[i] = entry
	else:
		entry["floors"] = []
		_sessions.append(entry)
	return _flush()

func save_floor(floor_row: Dictionary, kills: Dictionary) -> bool:
	var i := _find(str(floor_row.get("session_id", "")))
	if i < 0:
		last_error = "unknown session"
		return false
	var row: Dictionary = floor_row.duplicate(true)
	var k := {}
	for idx in kills.keys():
		k[str(int(idx))] = int(kills[idx])
	row["kills"] = k
	var floors: Array = _sessions[i]["floors"]
	for j in range(floors.size()):
		if int(floors[j].get("floor_num", -1)) == int(row.get("floor_num", -2)):
			last_error = "duplicate floor"
			return false
	floors.append(row)
	return _flush()

func get_floors(session_id: String) -> Array:
	var i := _find(session_id)
	if i < 0:
		return []
	var out: Array = []
	for fl in _sessions[i].get("floors", []):
		var row: Dictionary = fl.duplicate(true)
		var kills := {}
		for key in row.get("kills", {}).keys():
			kills[int(key)] = int(row["kills"][key])
		row["kills"] = kills
		out.append(row)
	out.sort_custom(func(a, b): return int(a["floor_num"]) < int(b["floor_num"]))
	return out

func get_session(session_id: String) -> Dictionary:
	var i := _find(session_id)
	return _sessions[i].duplicate(true) if i >= 0 else {}

func set_perceived_difficulty(session_id: String, floor_num: int, value: float) -> bool:
	var i := _find(session_id)
	if i < 0:
		return false
	for fl in _sessions[i].get("floors", []):
		if int(fl.get("floor_num", -1)) == floor_num:
			fl["perceived_difficulty"] = value
			return _flush()
	return false

## Header = session fields, floor columns (minus session_id), kills_0..kills_4: same order as v_corpus.
func corpus_header() -> Array:
	var h: Array = SESSION_CSV_FIELDS.duplicate()
	for c in floor_columns:
		if c != "session_id":
			h.append(c)
	for a in range(KILL_ARCHETYPES):
		h.append("kills_%d" % a)
	return h

func export_corpus_csv(path: String, consented_only: bool = false) -> int:
	var header := corpus_header()
	var rows: Array = []
	var sessions: Array = _sessions.duplicate()
	sessions.sort_custom(func(a, b): return str(a.get("session_id", "")) < str(b.get("session_id", "")))
	for s in sessions:
		if consented_only and not bool(s.get("consent", false)):
			continue
		var floors: Array = get_floors(str(s.get("session_id", "")))
		for fl in floors:
			var merged: Dictionary = fl.duplicate()
			merged["session_id"] = s.get("session_id", "")
			merged["install_id"] = s.get("install_id", "")
			merged["mode"] = s.get("mode", "")
			merged["policy_version"] = s.get("policy_version", "")
			merged["game_version"] = s.get("game_version", "")
			merged["consent"] = 1 if bool(s.get("consent", false)) else 0
			for a in range(KILL_ARCHETYPES):
				merged["kills_%d" % a] = int(fl["kills"].get(a, 0))
			var line: Array = []
			for h in header:
				line.append(merged.get(h, null))
			rows.append(line)
	if not write_csv(path, header, rows):
		last_error = "cannot write " + path
		return -1
	return rows.size()
