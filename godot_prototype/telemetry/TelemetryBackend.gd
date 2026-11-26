## Storage backend interface for TelemetryLogger (no class_name on purpose: loaded via preload).
## Floor dictionaries use the column names of queries.sql::insert_floor (incl. "session_id");
## per-archetype kills are passed separately as {archetype_idx: count}.
extends RefCounted

const SESSION_CSV_FIELDS := ["session_id", "install_id", "mode", "policy_version", "game_version", "consent"]
const KILL_ARCHETYPES := 5

var last_error: String = ""

func backend_name() -> String:
	return "none"

func open() -> bool:
	return false

func close() -> void:
	pass

## Insert or update the session row (idempotent, keyed on session["id"]).
func save_session(_session: Dictionary) -> bool:
	return false

## Atomically store one floor (+ its kills). Returns false on failure.
func save_floor(_floor: Dictionary, _kills: Dictionary) -> bool:
	return false

## Floors of a session ordered by floor_num; each has a "kills" Dictionary {int: int}.
func get_floors(_session_id: String) -> Array:
	return []

func get_session(_session_id: String) -> Dictionary:
	return {}

func set_perceived_difficulty(_session_id: String, _floor_num: int, _value: float) -> bool:
	return false

## Writes the corpus CSV (one row per floor). Returns the number of data rows, or -1 on error.
func export_corpus_csv(_path: String, _consented_only: bool = false) -> int:
	return -1

## Shared CSV writer (RFC 4180 quoting; null -> empty cell).
static func write_csv(path: String, header: Array, rows: Array) -> bool:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(csv_line(header) + "\n")
	for row in rows:
		f.store_string(csv_line(row) + "\n")
	f.close()
	return true

static func csv_line(values: Array) -> String:
	var cells: PackedStringArray = []
	for v in values:
		cells.append(csv_cell(v))
	return ",".join(cells)

static func csv_cell(v: Variant) -> String:
	if v == null:
		return ""
	var s: String = str(v)
	if s.contains(",") or s.contains("\"") or s.contains("\n") or s.contains("\r"):
		s = "\"" + s.replace("\"", "\"\"") + "\""
	return s
