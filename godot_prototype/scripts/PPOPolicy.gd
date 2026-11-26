class_name PPOPolicy
extends RefCounted

## Loads a small MLP (obs -> hidden -> hidden -> action) exported from a
## PyTorch / Stable-Baselines3 PPO policy and runs inference in pure GDScript.
## No PyTorch or ONNX runtime is needed at game runtime — just matrix math.
##
## Expected JSON format (see ai_training/train_ppo_difficulty.py -> export_policy_to_json):
## {
##   "layers": [ {"w": [[...]], "b": [...]}, {"w": [[...]], "b": [...]}, ... ],
##   "activation": "tanh"
## }
## Hidden layers are followed by tanh. The final layer is the Gaussian mean of the
## SB3 policy; like SB3's deterministic predict() (and the training env), it is
## CLIPPED to [-1, 1] -- not squashed with tanh -- so the game acts exactly as the
## policy did during training.

var layers: Array = []
var loaded: bool = false

## Observation width the game produces (DifficultyManager.build_observation).
const OBS_SIZE := 8
## Action width: 8 (7 legacy + archetype_complexity). A legacy 7-output file still works; the
## DifficultyManager derives a7 from the difficulty score in that case.
const ACTION_SIZE := 8

func load_weights(path: String) -> bool:
	if not FileAccess.file_exists(path):
		push_warning("[PPOPolicy] No trained weights found at %s — using rule-based fallback until you train and drop in a real policy." % path)
		loaded = false
		return false

	var f = FileAccess.open(path, FileAccess.READ)
	var json = JSON.new()
	var err = json.parse(f.get_as_text())
	f.close()

	if err != OK or typeof(json.data) != TYPE_DICTIONARY or not json.data.has("layers"):
		push_warning("[PPOPolicy] Failed to parse policy JSON at %s — using rule-based fallback." % path)
		loaded = false
		return false

	layers = json.data["layers"]
	loaded = layers.size() > 0
	# Shape check: the first layer's input width must equal the observation size.
	if loaded:
		var first: Dictionary = layers[0]
		var rows: Array = first.get("w", [])
		var in_dim: int = (rows[0] as Array).size() if rows.size() > 0 and rows[0] is Array else -1
		if in_dim != OBS_SIZE:
			push_warning("[PPOPolicy] Policy at %s expects %d inputs but observation has %d -- using rule-based fallback." % [path, in_dim, OBS_SIZE])
			loaded = false
			return false
	if loaded:
		print("[PPOPolicy] Loaded trained policy with ", layers.size(), " layers from ", path)
	return loaded

## obs: PackedFloat32Array, values expected roughly in [0, 1] (see DifficultyManager.build_observation)
## returns: PackedFloat32Array of length 8 (or 7 for a legacy weights file), values in [-1, 1]
func predict(obs: PackedFloat32Array) -> PackedFloat32Array:
	if not loaded or obs.size() != OBS_SIZE:
		return _fallback_heuristic(obs)

	var x: Array = []
	for v in obs:
		x.append(v)

	for i in range(layers.size()):
		var layer: Dictionary = layers[i]
		var w: Array = layer["w"]   # shape [out_dim][in_dim]
		var b: Array = layer["b"]   # shape [out_dim]
		var y: Array = []
		y.resize(w.size())
		for o in range(w.size()):
			var s: float = b[o]
			var row: Array = w[o]
			for k in range(row.size()):
				s += float(row[k]) * float(x[k])
			y[o] = s
		var is_last := (i == layers.size() - 1)
		if not is_last:
			for o in range(y.size()):
				y[o] = tanh(y[o])
		x = y

	var out := PackedFloat32Array()
	for v in x:
		out.append(clampf(v, -1.0, 1.0))
	return out

## Used only until you've trained and dropped in real weights, so the game is
## playable/demoable immediately. Mirrors the intended learned behavior:
## fast clear + no deaths -> push difficulty up; slow / died a lot -> ease off.
## Escalation is intentionally gentle and per-parameter step is capped, so it
## takes a run of several good levels to climb from min to max — not 2-3.
## obs layout: [norm_time, norm_deaths, norm_dmg_ratio,
##              norm_enemy_hp, norm_enemy_dmg, norm_hazard, norm_rooms, norm_level]
func _fallback_heuristic(obs: PackedFloat32Array) -> PackedFloat32Array:
	var norm_time: float = obs[0]       # 0 = very fast clear, 1 = very slow
	var norm_deaths: float = obs[1]
	var norm_dmg_ratio: float = obs[2]
	var cur_hp: float = obs[3]
	var cur_dmg: float = obs[4]
	var cur_haz: float = obs[5]
	var cur_rooms: float = obs[6]

	# > 0 means the player did great (fast, no deaths) -> escalate difficulty
	# < 0 means the player struggled -> ease off
	var performance_signal: float = (0.5 - norm_time) * 1.4 - norm_deaths * 1.5 - norm_dmg_ratio * 0.8
	performance_signal = clampf(performance_signal, -1.0, 1.0)

	# How much a single level's result can nudge each normalized parameter
	# (in [-1, 1] units). Kept small so climbing from min to max takes roughly
	# 8-10 consecutive good levels instead of 2-3.
	var step := 0.12
	var out := PackedFloat32Array()
	out.append(clampf(cur_hp * 2.0 - 1.0 + performance_signal * step, -1.0, 1.0))    # enemy_health
	out.append(clampf(cur_dmg * 2.0 - 1.0 + performance_signal * step, -1.0, 1.0))   # enemy_damage
	out.append(clampf(performance_signal * 0.5, -1.0, 1.0))                           # enemy_speed
	out.append(clampf(performance_signal * 0.5, -1.0, 1.0))                           # enemy_aggro
	out.append(clampf(cur_haz * 2.0 - 1.0 + performance_signal * step, -1.0, 1.0))   # hazard_density
	out.append(clampf(performance_signal * 0.3, -1.0, 1.0))                           # resource_scarcity
	out.append(clampf(cur_rooms * 2.0 - 1.0 + performance_signal * step, -1.0, 1.0)) # room_count
	# archetype_complexity (a7): skill-based rule. Strong play (signal > 0) unlocks harder archetypes
	# (brute/skirmisher); struggling play favours crawlers/swarmers. Centred slightly below 0
	# (c ~= 0.45, the static-baseline mix) so a neutral player sees a balanced mix.
	out.append(clampf(-0.1 + performance_signal * 0.9, -1.0, 1.0))                  # archetype_complexity
	return out
