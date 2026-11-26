## Loads and parses telemetry/schema.sql and telemetry/queries.sql (the single source of SQL for
## both Godot and Python; see ml_spike/analysis/export_telemetry.py for the mirrored parser).
extends RefCounted

const SCHEMA_PATH := "res://telemetry/schema.sql"
const QUERIES_PATH := "res://telemetry/queries.sql"

static func _read(path: String) -> String:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_warning("[TelemetrySQL] cannot read " + path)
		return ""
	var text := f.get_as_text()
	f.close()
	return text

static func _strip_comments(text: String) -> String:
	var kept: PackedStringArray = []
	for line in text.split("\n"):
		if not line.strip_edges().begins_with("--"):
			kept.append(line)
	return "\n".join(kept)

## Splits a block on ';' (comment lines removed first).
static func split_statements(sql: String) -> PackedStringArray:
	var out: PackedStringArray = []
	for part in _strip_comments(sql).split(";"):
		var s := part.strip_edges()
		if not s.is_empty():
			out.append(s)
	return out

static func _collapse_ws(s: String) -> String:
	var joined: PackedStringArray = []
	for p in s.replace("\n", " ").replace("\t", " ").replace("\r", " ").split(" ", false):
		joined.append(p)
	return " ".join(joined)

## Returns {"bootstrap": PackedStringArray, "migrations": Array of {"version": int, "statements": PackedStringArray}}
static func load_schema(path: String = SCHEMA_PATH) -> Dictionary:
	var sections: Dictionary = {"bootstrap": []}
	var current := ""
	for raw in _read(path).split("\n"):
		var line := raw.strip_edges()
		var low := line.to_lower()
		if low.begins_with("-- migration v"):
			current = str(int(low.substr(14)))
			sections[current] = []
		elif low == "-- bootstrap":
			current = "bootstrap"
		elif current != "":
			sections[current].append(raw)
	var migrations: Array = []
	for key in sections.keys():
		if key == "bootstrap":
			continue
		migrations.append({"version": int(key), "statements": split_statements("\n".join(PackedStringArray(sections[key])))})
	migrations.sort_custom(func(a, b): return a.version < b.version)
	return {"bootstrap": split_statements("\n".join(PackedStringArray(sections["bootstrap"]))), "migrations": migrations}

## Returns {name: single statement (whitespace collapsed, no trailing ';')}.
static func load_queries(path: String = QUERIES_PATH) -> Dictionary:
	var blocks: Dictionary = {}
	var current := ""
	for raw in _read(path).split("\n"):
		var line := raw.strip_edges()
		if line.begins_with("-- name:"):
			current = line.substr(8).strip_edges()
			blocks[current] = []
		elif current != "":
			blocks[current].append(raw)
	var out: Dictionary = {}
	for key in blocks.keys():
		var stmts := split_statements("\n".join(PackedStringArray(blocks[key])))
		if stmts.size() > 0:
			out[key] = _collapse_ws(stmts[0])
	return out

## Column list of the first '(...)' group of a statement: defines positional bind order.
static func insert_columns(sql: String) -> PackedStringArray:
	var a := sql.find("(")
	var b := sql.find(")", a)
	var cols: PackedStringArray = []
	if a < 0 or b < 0:
		return cols
	for c in sql.substr(a + 1, b - a - 1).split(","):
		cols.append(c.strip_edges())
	return cols
