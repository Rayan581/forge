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

const TELEMETRY_FILE_PATH = "user://session_telemetry.json"

func _init() -> void:
	start_new_session()

func start_new_session() -> void:
	session_id = "sess_" + str(Time.get_unix_time_from_system())
	start_timestamp = int(Time.get_unix_time_from_system())
	elapsed_seconds = 0.0
	rooms_cleared = 0
	total_deaths = 0
	damage_dealt = 0.0
	damage_taken = 0.0
	enemies_defeated = 0
	pickups_collected = 0
	hazard_hits = 0

func update_time(delta: float) -> void:
	elapsed_seconds += delta

func record_death() -> void:
	total_deaths += 1

func record_room_cleared() -> void:
	rooms_cleared += 1

func record_damage_dealt(amount: float) -> void:
	damage_dealt += amount

func record_damage_taken(amount: float) -> void:
	damage_taken += amount

func record_enemy_defeated() -> void:
	enemies_defeated += 1

func record_pickup_collected() -> void:
	pickups_collected += 1

func record_hazard_hit() -> void:
	hazard_hits += 1

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

func save_to_file() -> void:
	var current_data = get_summary()
	var history: Array = []
	
	if FileAccess.file_exists(TELEMETRY_FILE_PATH):
		var file_read = FileAccess.open(TELEMETRY_FILE_PATH, FileAccess.READ)
		if file_read:
			var content = file_read.get_as_text()
			var json = JSON.new()
			if json.parse(content) == OK and json.data is Array:
				history = json.data
			file_read.close()
			
	history.append(current_data)
	
	# Limit history to 50 entries
	if history.size() > 50:
		history = history.slice(history.size() - 50)
		
	var file_write = FileAccess.open(TELEMETRY_FILE_PATH, FileAccess.WRITE)
	if file_write:
		file_write.store_string(JSON.stringify(history, "\t"))
		file_write.close()
		print("[TelemetryLogger] Successfully logged session to: ", TELEMETRY_FILE_PATH)
