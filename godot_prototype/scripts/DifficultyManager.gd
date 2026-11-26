class_name DifficultyManager
extends RefCounted

# Preset Profile Enums
enum ProfileTier { NOVICE, INTERMEDIATE, EXPERT, CUSTOM }

# Current Parameters (Continuous Vectors E and M)
# Enemy Vector E: [health, damage, speed, aggro_radius]
# Environmental Vector M: [hazard_density, resource_scarcity]
var current_profile: ProfileTier = ProfileTier.INTERMEDIATE

var enemy_health: float = 60.0        # Range: 20 to 120
var enemy_damage: float = 20.0        # Range: 5 to 50
var enemy_speed: float = 125.0        # Range: 60 to 220
var enemy_aggro: float = 240.0        # Range: 100 to 450
var hazard_density: float = 0.35      # Range: 0.05 to 0.80 (5% to 80%)
var resource_scarcity: float = 0.40   # Range: 0.10 to 0.90 (10% to 90%)

# --- PPO-controlled additions ---
var room_count_target: int = 6        # Range: 5 to 9 (rooms in next generated dungeon)
var enemy_count_scale: float = 1.0    # Range: 0.6 to 1.6 (multiplies per-room enemy counts)
var ranged_enemy_ratio: float = 0.35  # Range: 0.0 to 1.0 (proportion of spawned enemies that are Pyromancers)

# --- Archetype mix (CONTRACT.md section 3; must match the Python implementation) ---
# Order follows Enemy.Archetype: crawler, pyromancer, brute, skirmisher, swarmer.
const ARCHETYPE_LEVELS := [0.00, 0.50, 0.90, 0.70, 0.25]
const STATIC_BASELINE_A7: float = -0.1
var archetype_complexity: float = 0.45  # c in [0, 1]
var archetype_mix: PackedFloat32Array = PackedFloat32Array([0.0834, 0.4245, 0.1097, 0.2073, 0.1751])

## Softmax-based archetype mix for a given 8th action value a7 in [-1, 1].
## p = 0.85 * softmax(-|LEVEL_i - c| / 0.25) + 0.15 / 5, c = (a7 + 1) / 2.
static func compute_archetype_mix(a7: float) -> PackedFloat32Array:
	var c: float = (clampf(a7, -1.0, 1.0) + 1.0) / 2.0
	var n: int = ARCHETYPE_LEVELS.size()
	var e: Array = []
	var total: float = 0.0
	for i in range(n):
		var v: float = exp(-absf(ARCHETYPE_LEVELS[i] - c) / 0.25)
		e.append(v)
		total += v
	var out := PackedFloat32Array()
	for i in range(n):
		out.append(0.85 * (e[i] / total) + 0.15 / float(n))
	return out

## Sets archetype_mix / archetype_complexity / ranged_enemy_ratio from a7.
func set_archetype_from_a7(a7: float) -> void:
	archetype_complexity = (clampf(a7, -1.0, 1.0) + 1.0) / 2.0
	archetype_mix = compute_archetype_mix(a7)
	ranged_enemy_ratio = archetype_mix[Enemy.Archetype.RANGED_PYROMANCER]

## Sets an explicit mix (calibration floors). Complexity is the mix-weighted mean level.
func set_archetype_mix(mix: Array) -> void:
	archetype_mix = PackedFloat32Array(mix)
	var c: float = 0.0
	for i in range(ARCHETYPE_LEVELS.size()):
		c += archetype_mix[i] * ARCHETYPE_LEVELS[i]
	archetype_complexity = c
	ranged_enemy_ratio = archetype_mix[Enemy.Archetype.RANGED_PYROMANCER]

## Samples an archetype index from archetype_mix using u in [0, 1).
func sample_archetype(u: float) -> int:
	var acc: float = 0.0
	for i in range(archetype_mix.size()):
		acc += archetype_mix[i]
		if u < acc:
			return i
	return archetype_mix.size() - 1

# Real-value ranges used to map PPO's normalized [-1, 1] actions onto game parameters.
const PARAM_RANGES = {
	"enemy_health":      {"min": 20.0,  "max": 120.0},
	"enemy_damage":      {"min": 5.0,   "max": 50.0},
	"enemy_speed":       {"min": 60.0,  "max": 220.0},
	"enemy_aggro":       {"min": 100.0, "max": 450.0},
	"hazard_density":    {"min": 0.05,  "max": 0.80},
	"resource_scarcity": {"min": 0.10,  "max": 0.90},
	"room_count":        {"min": 5.0,   "max": 9.0},
}

# Presets matching Section 5 / Proposal Defense specifications
const PRESETS = {
	ProfileTier.NOVICE: {
		"name": "Novice (Casual)",
		"health": 35.0,
		"damage": 10.0,
		"speed": 85.0,
		"aggro": 160.0,
		"hazard": 0.15,
		"scarcity": 0.15,
		"description": "Slow, low-damage adversaries with abundant health drops and minimal traps."
	},
	ProfileTier.INTERMEDIATE: {
		"name": "Intermediate (Standard)",
		"health": 60.0,
		"damage": 20.0,
		"speed": 130.0,
		"aggro": 250.0,
		"hazard": 0.35,
		"scarcity": 0.40,
		"description": "Balanced combat pace with moderate traps and standard resource drops."
	},
	ProfileTier.EXPERT: {
		"name": "Expert (Brutal)",
		"health": 95.0,
		"damage": 35.0,
		"speed": 185.0,
		"aggro": 380.0,
		"hazard": 0.65,
		"scarcity": 0.75,
		"description": "High-velocity aggressive enemies, hazardous traps, and scarce survival drops."
	}
}

# 5-Stage Cold-Start Calibration Sequence (Proposal §5.4 / Table 4.1)
# These levels are not hand-drawn tilemaps; they are procedurally generated dungeons
# with fixed, calibrated difficulty vectors to evaluate the player's baseline capabilities.
const CALIBRATION_LEVELS = {
	1: {
		"title": "Level 1: Novice Initiation",
		"subtitle": "Cold-Start Calibration (1/5) · Pacing & Navigation",
		"rooms": 3,
		"health": 35.0,
		"damage": 10.0,
		"speed": 85.0,
		"aggro": 160.0,
		"hazard": 0.05,
		"scarcity": 0.15,
		"count_scale": 0.7,
		"archetype_mix": [0.70, 0.0, 0.0, 0.0, 0.30],
		"description": "Introductory floor with slow, low-damage adversaries and minimal environmental hazards."
	},
	2: {
		"title": "Level 2: Swarm Reflex",
		"subtitle": "Cold-Start Calibration (2/5) · Melee Combat & Reflexes",
		"rooms": 4,
		"health": 45.0,
		"damage": 14.0,
		"speed": 110.0,
		"aggro": 200.0,
		"hazard": 0.15,
		"scarcity": 0.25,
		"count_scale": 0.9,
		"archetype_mix": [0.50, 0.0, 0.0, 0.0, 0.50],
		"description": "Standard combat encounter testing basic swordplay, evasion, and crowd engagement."
	},
	3: {
		"title": "Level 3: Ranged Evasion & Traps",
		"subtitle": "Cold-Start Calibration (3/5) · Spatial Awareness & Projectiles",
		"rooms": 4,
		"health": 55.0,
		"damage": 18.0,
		"speed": 135.0,
		"aggro": 240.0,
		"hazard": 0.38,
		"scarcity": 0.35,
		"count_scale": 1.0,
		"archetype_mix": [0.0, 0.75, 0.0, 0.25, 0.0],
		"description": "Robed pyromancer casters testing projectile dodge roll evasion and spatial navigation."
	},
	4: {
		"title": "Level 4: Tactical Crucible",
		"subtitle": "Cold-Start Calibration (4/5) · Mixed Attrition & Priority Targeting",
		"rooms": 5,
		"health": 70.0,
		"damage": 24.0,
		"speed": 155.0,
		"aggro": 290.0,
		"hazard": 0.50,
		"scarcity": 0.55,
		"count_scale": 1.15,
		"archetype_mix": [0.25, 0.25, 0.0, 0.30, 0.20],
		"description": "Extended dungeon layout with mixed melee crawlers and ranged pyromancers."
	},
	5: {
		"title": "Level 5: Apex Gauntlet",
		"subtitle": "Cold-Start Calibration (5/5) · Mini-Boss Challenge & Climax",
		"rooms": 5,
		"health": 90.0,
		"damage": 30.0,
		"speed": 175.0,
		"aggro": 350.0,
		"hazard": 0.65,
		"scarcity": 0.70,
		"count_scale": 1.3,
		"archetype_mix": [0.15, 0.25, 0.30, 0.20, 0.10],
		"description": "High-intensity gauntlet with buffed adversaries and multi-caster projectile salvos."
	}
}

func is_in_calibration(level_num: int) -> bool:
	# The static and BSP baselines have no calibration phase and no PPO phase.
	if static_baseline_mode or bsp_baseline_mode:
		return false
	return level_num >= 1 and level_num <= 5

# --- Static non-adaptive roguelike baseline (comparison condition) ---
# When enabled, PPO adaptation and cold-start calibration are bypassed. Enemy
# health and damage grow by a fixed 8 % of their Intermediate-preset value for
# every floor after Floor 1; all other parameters stay at the Intermediate preset.
const STATIC_STEP: float = 0.08
var static_baseline_mode: bool = false

func static_scale(level_num: int) -> float:
	return 1.0 + STATIC_STEP * float(maxi(level_num - 1, 0))

func apply_static_baseline(level_num: int) -> void:
	var p = PRESETS[ProfileTier.INTERMEDIATE]
	var f: float = static_scale(level_num)
	current_profile = ProfileTier.CUSTOM
	enemy_health = p.health * f
	enemy_damage = p.damage * f
	enemy_speed = p.speed
	enemy_aggro = p.aggro
	hazard_density = p.hazard
	resource_scarcity = p.scarcity
	set_archetype_from_a7(STATIC_BASELINE_A7)  # fixed c = 0.45 on every floor
	room_count_target = 6
	enemy_count_scale = 1.0

# --- BSP non-adaptive baseline (comparison condition "Baseline A") ---
# Layouts come from BSPGenerator.gd instead of the random-walk generator, and every floor uses the
# fixed Intermediate preset (no calibration, no PPO, no +8 % growth). The room count is whatever the
# BSP tree produces (5-9), so room_count_target is set from the generated layout by Main.
var bsp_baseline_mode: bool = false

const GENERATOR_FORGE: String = "forge"
const GENERATOR_STATIC: String = "static"
const GENERATOR_BSP: String = "bsp"

## "forge" (calibration + PPO), "static" (+8 %/floor) or "bsp" (BSP layouts, fixed Intermediate).
func generator_mode() -> String:
	if bsp_baseline_mode:
		return GENERATOR_BSP
	if static_baseline_mode:
		return GENERATOR_STATIC
	return GENERATOR_FORGE

## Switch the condition. The modes are exclusive; unknown names fall back to "forge".
func set_generator_mode(mode: String) -> void:
	static_baseline_mode = mode == GENERATOR_STATIC
	bsp_baseline_mode = mode == GENERATOR_BSP

## True for the two non-adaptive comparison conditions.
func is_baseline_mode() -> bool:
	return static_baseline_mode or bsp_baseline_mode

## Layout algorithm DungeonGenerator should use for this condition.
func layout_mode() -> String:
	return GENERATOR_BSP if bsp_baseline_mode else GENERATOR_FORGE

func apply_bsp_baseline(_level_num: int) -> void:
	var p = PRESETS[ProfileTier.INTERMEDIATE]
	current_profile = ProfileTier.CUSTOM
	enemy_health = p.health
	enemy_damage = p.damage
	enemy_speed = p.speed
	enemy_aggro = p.aggro
	hazard_density = p.hazard
	resource_scarcity = p.scarcity
	set_archetype_from_a7(STATIC_BASELINE_A7)  # same fixed mix as the static baseline (c = 0.45)
	enemy_count_scale = 1.0

## Applies the per-floor settings of the active baseline (static or BSP). No-op in FORGE mode.
func apply_baseline(level_num: int) -> void:
	if bsp_baseline_mode:
		apply_bsp_baseline(level_num)
	elif static_baseline_mode:
		apply_static_baseline(level_num)

func apply_calibration_level(level_num: int) -> Dictionary:
	if CALIBRATION_LEVELS.has(level_num):
		var cal = CALIBRATION_LEVELS[level_num]
		current_profile = ProfileTier.CUSTOM
		enemy_health = cal.health
		enemy_damage = cal.damage
		enemy_speed = cal.speed
		enemy_aggro = cal.aggro
		hazard_density = cal.hazard
		resource_scarcity = cal.scarcity
		room_count_target = cal.rooms
		enemy_count_scale = cal.count_scale
		set_archetype_mix(cal.archetype_mix)  # also derives ranged_enemy_ratio = p[pyromancer]
		archetype_complexity = clampf(archetype_complexity, 0.0, 1.0)
		return cal
	return {}

func apply_preset(tier: ProfileTier) -> void:
	current_profile = tier
	if tier in PRESETS:
		var p = PRESETS[tier]
		enemy_health = p.health
		enemy_damage = p.damage
		enemy_speed = p.speed
		enemy_aggro = p.aggro
		hazard_density = p.hazard
		resource_scarcity = p.scarcity
		# Presets have no explicit mix: derive complexity from their predicted difficulty score.
		set_archetype_from_a7(2.0 * float(calculate_difficulty_score().score) / 100.0 - 1.0)

# --- PPO integration ---

func _normalize(value: float, key: String) -> float:
	var r = PARAM_RANGES[key]
	return clampf((value - r.min) / (r.max - r.min), 0.0, 1.0)

func _denormalize(action_val: float, key: String) -> float:
	var t = (clampf(action_val, -1.0, 1.0) + 1.0) / 2.0
	var r = PARAM_RANGES[key]
	return r.min + t * (r.max - r.min)

## Builds the 8-dim observation vector fed to the PPO policy at the end of each level.
## All values are normalized to roughly [0, 1] so the trained network sees consistent inputs.
func build_observation(completion_time_sec: float, deaths_this_level: int, damage_taken_this_level: float, player_max_health: float, level_num: int) -> PackedFloat32Array:
	var target_time = 45.0 # seconds — the "ideal pace" the policy was trained around
	var norm_time = clampf(completion_time_sec / (target_time * 2.0), 0.0, 1.0)
	var norm_deaths = clampf(float(deaths_this_level) / 3.0, 0.0, 1.0)
	var norm_dmg_ratio = clampf(damage_taken_this_level / maxf(1.0, player_max_health), 0.0, 1.0)
	var norm_hp = _normalize(enemy_health, "enemy_health")
	var norm_dmg = _normalize(enemy_damage, "enemy_damage")
	var norm_haz = _normalize(hazard_density, "hazard_density")
	var norm_rooms = _normalize(float(room_count_target), "room_count")
	var norm_level = clampf(float(level_num) / 10.0, 0.0, 1.0)

	return PackedFloat32Array([
		norm_time, norm_deaths, norm_dmg_ratio,
		norm_hp, norm_dmg, norm_haz, norm_rooms, norm_level
	])

## Builds the initial observation vector s₀ seeded by the composite 5-level CR₀ baseline.
## Ensures the entire calibration history directly guides the neural PPO policy for Floor 6+.
func build_observation_from_cr0(cr0_profile: Dictionary, level_num: int = 6) -> PackedFloat32Array:
	# Use the calibration averages expressed on the training observation scales
	# (see TelemetryLogger.compute_cr0_baseline). The CR0 score itself is a
	# human-readable summary and is not an input of the trained policy.
	var norm_time = cr0_profile.get("obs_time", 0.5)
	var norm_deaths = cr0_profile.get("obs_deaths", 0.0)
	var norm_dmg_ratio = cr0_profile.get("obs_dmg_ratio", 0.3)
	var norm_hp = _normalize(enemy_health, "enemy_health")
	var norm_dmg = _normalize(enemy_damage, "enemy_damage")
	var norm_haz = _normalize(hazard_density, "hazard_density")
	var norm_rooms = _normalize(float(room_count_target), "room_count")
	var norm_level = clampf(float(level_num) / 10.0, 0.0, 1.0)

	return PackedFloat32Array([
		norm_time, norm_deaths, norm_dmg_ratio,
		norm_hp, norm_dmg, norm_haz, norm_rooms, norm_level
	])

## Applies the continuous action vector output by the PPO policy.
## action = [enemy_health, enemy_damage, enemy_speed, enemy_aggro,
##           hazard_density, resource_scarcity, room_count, archetype_complexity]  (each in [-1, 1])
## A legacy 7-dim vector (old weights) is accepted: a7 = 2 * difficulty_score / 100 - 1.
func apply_ppo_action(action: PackedFloat32Array) -> void:
	if action.size() < 7:
		push_warning("[DifficultyManager] PPO action vector too short, ignoring.")
		return
	current_profile = ProfileTier.CUSTOM
	enemy_health = _denormalize(action[0], "enemy_health")
	enemy_damage = _denormalize(action[1], "enemy_damage")
	enemy_speed = _denormalize(action[2], "enemy_speed")
	enemy_aggro = _denormalize(action[3], "enemy_aggro")
	hazard_density = _denormalize(action[4], "hazard_density")
	resource_scarcity = _denormalize(action[5], "resource_scarcity")
	room_count_target = int(round(_denormalize(action[6], "room_count")))
	# The training simulator assumes the default enemy count per room, so the
	# calibration-only count multiplier (up to 1.3 on Floor 5) must not carry over.
	enemy_count_scale = 1.0
	
	var a7: float
	if action.size() >= 8:
		a7 = action[7]
	else:
		# Legacy 7-output policy: derive complexity from the predicted difficulty score.
		var ppo_challenge: float = calculate_difficulty_score().score / 100.0
		a7 = 2.0 * ppo_challenge - 1.0
	set_archetype_from_a7(a7)

# Calculates a 0-100 predicted difficulty score
func calculate_difficulty_score() -> Dictionary:
	# Normalize features between 0.0 and 1.0
	var norm_hp = clampf((enemy_health - 20.0) / 100.0, 0.0, 1.0)
	var norm_dmg = clampf((enemy_damage - 5.0) / 45.0, 0.0, 1.0)
	var norm_spd = clampf((enemy_speed - 60.0) / 160.0, 0.0, 1.0)
	var norm_aggro = clampf((enemy_aggro - 100.0) / 350.0, 0.0, 1.0)
	var norm_haz = clampf((hazard_density - 0.05) / 0.75, 0.0, 1.0)
	var norm_scarcity = clampf((resource_scarcity - 0.10) / 0.80, 0.0, 1.0)
	
	# Weighted linear model simulating auxiliary difficulty regressor
	var w_dmg = 0.28
	var w_hp = 0.22
	var w_spd = 0.18
	var w_aggro = 0.14
	var w_haz = 0.10
	var w_scarcity = 0.08
	# Archetype complexity is NOT part of the score: test_static_baseline/test_cold_start and the
	# calibration difficulty labels depend on it, and the legacy-7 fallback derives a7 FROM this
	# score (using it here would be circular). It is shown separately (DefenseOverlay).
	
	var raw_score = (
		norm_dmg * w_dmg +
		norm_hp * w_hp +
		norm_spd * w_spd +
		norm_aggro * w_aggro +
		norm_haz * w_haz +
		norm_scarcity * w_scarcity
	)
	
	var score_100 = int(round(raw_score * 100.0))
	var tier_label = "Balanced"
	if score_100 < 35:
		tier_label = "Accessible / Easy"
	elif score_100 < 60:
		tier_label = "Balanced / Moderate"
	elif score_100 < 80:
		tier_label = "Intense / Challenging"
	else:
		tier_label = "Brutal / Hardcore"
		
	# Feature contributions (SHAP-style attribution percentages)
	var total_contrib = (
		norm_dmg * w_dmg + norm_hp * w_hp + norm_spd * w_spd +
		norm_aggro * w_aggro + norm_haz * w_haz + norm_scarcity * w_scarcity
	)
	if total_contrib <= 0.001:
		total_contrib = 1.0
		
	var drivers = [
		{"name": "Enemy Damage", "pct": int(round((norm_dmg * w_dmg / total_contrib) * 100.0))},
		{"name": "Enemy Health", "pct": int(round((norm_hp * w_hp / total_contrib) * 100.0))},
		{"name": "Enemy Velocity", "pct": int(round((norm_spd * w_spd / total_contrib) * 100.0))},
		{"name": "Aggro Radius", "pct": int(round((norm_aggro * w_aggro / total_contrib) * 100.0))},
		{"name": "Hazard Density", "pct": int(round((norm_haz * w_haz / total_contrib) * 100.0))},
		{"name": "Resource Scarcity", "pct": int(round((norm_scarcity * w_scarcity / total_contrib) * 100.0))}
	]
	drivers.sort_custom(func(a, b): return a.pct > b.pct)
	
	return {
		"score": score_100,
		"label": tier_label,
		"drivers": drivers
	}
