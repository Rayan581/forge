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
