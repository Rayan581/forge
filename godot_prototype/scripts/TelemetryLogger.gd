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
