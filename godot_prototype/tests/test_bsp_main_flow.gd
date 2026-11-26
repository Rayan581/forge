# tests/test_bsp_main_flow.gd
# BSP baseline end to end through Main.tscn: once the BSP condition is switched on (Defense Panel
# toggle), every floor must use the fixed Intermediate preset and a BSP layout, whatever the player
# did on the previous floor. Floors alternate between "bad" play (deaths, lots of damage, fast) and
# "good" play (no deaths, no damage, slow) for 8 floors, which covers the floor-5 -> 6 PPO seeding and
# the floor-7+ PPO steps of FORGE mode; the settings of floors 1-9 must all be identical. This catches
# Main falling through to calibration or the PPO policy in BSP mode.
# Uses the JSON telemetry backend on scratch files and consent = false (no rating prompt).
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_bsp_main_flow.gd
extends SceneTree

const TAG := "test_bspflow"
const FLOORS := 9

var failures: Array[String] = []
var checks := 0
var finished := false

func _initialize() -> void:
	_run()

func _eq(label: String, got: Variant, want: Variant) -> void:
	checks += 1
	if str(got) != str(want):
		failures.append("%s: got %s, expected %s" % [label, str(got), str(want)])

func _ok(label: String, cond: bool) -> void:
	_eq(label, cond, true)

func _frames(n: int) -> void:
	for i in n:
		await process_frame

## Waits (up to max_ms) until Main has built the given floor.
func _wait_for_level(main, level: int, max_ms: int = 6000) -> void:
	var t0 := Time.get_ticks_msec()
	while main.current_dungeon_level != level and Time.get_ticks_msec() - t0 < max_ms:
		await process_frame
	await _frames(4)

func _cleanup() -> void:
	for n in ["%s_settings.cfg", "%s_tel.json", "%s_tel.db", "%s_install.txt"]:
		var p := ProjectSettings.globalize_path("user://" + (n % TAG))
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## Every setting the PPO policy or calibration could change.
func _snapshot(dm: DifficultyManager) -> Dictionary:
	return {
		"health": dm.enemy_health,
		"damage": dm.enemy_damage,
		"speed": dm.enemy_speed,
		"aggro": dm.enemy_aggro,
		"hazard": dm.hazard_density,
		"scarcity": dm.resource_scarcity,
		"count_scale": dm.enemy_count_scale,
		"mix": str(dm.archetype_mix),
	}

func _check_floor(main, floor_num: int, want: Dictionary) -> void:
	var dm: DifficultyManager = main.difficulty_manager
	var tag := "[floor %d]" % floor_num
	_eq(tag + " current level", main.current_dungeon_level, floor_num)
	_eq(tag + " still BSP mode", dm.generator_mode(), DifficultyManager.GENERATOR_BSP)
	_eq(tag + " not in calibration", dm.is_in_calibration(floor_num), false)
	_eq(tag + " BSP layout", main.dungeon_generator.layout_mode, DungeonGenerator.LAYOUT_BSP)
	var n: int = main.dungeon_generator.rooms.size()
	_ok(tag + " 5-9 rooms (got %d)" % n, n >= 5 and n <= 9)
	_eq(tag + " room_count_target follows the BSP layout", dm.room_count_target, n)
	var got := _snapshot(dm)
	for k in want.keys():
		_eq(tag + " " + k + " unchanged", got[k], want[k])

func _run() -> void:
	_cleanup()
	GameSettings.file_path = "user://%s_settings.cfg" % TAG
	BuildInfo.force_playtest = 0 # developer build: the Defense Panel toggle is available
	var s := GameSettings.new()
	s.set_consent(false) # no rating prompt between floors

	var main = load("res://scenes/Main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	var tl = main.telemetry_logger
	tl.backend_preference = "json"
	tl.json_path = "user://%s_tel.json" % TAG
	tl.db_path = "user://%s_tel.db" % TAG
	tl.install_id_path = "user://%s_install.txt" % TAG
	await _frames(3)
	main.main_menu.visible = false
	main._on_start_run_requested()
	await _frames(6)

	# Switch to the BSP condition the way the Defense Panel does (rebuilds the current floor).
	main.defense_overlay._on_bsp_baseline_toggled(true)
	await _frames(6)

	# Expected settings: the Intermediate preset as applied by the BSP baseline.
	var ref := DifficultyManager.new()
	ref.set_generator_mode(DifficultyManager.GENERATOR_BSP)
	ref.apply_baseline(1)
	var want := _snapshot(ref)
	_check_floor(main, 1, want)

	for f in range(1, FLOORS):
		if f % 2 == 1:
			# played badly: 4 deaths, 400 damage, cleared in about 20 s
			tl.total_deaths += 4
			tl.damage_taken += 400.0
			main.level_start_time_msec = Time.get_ticks_msec() - 20000
		else:
			# played well: no deaths, no damage, slow and careful (about 4 minutes)
			main.level_start_time_msec = Time.get_ticks_msec() - 240000
		main._on_dungeon_escaped()
		await _wait_for_level(main, f + 1)
		_check_floor(main, f + 1, want)

	# Telemetry: every finished floor is stored as BSP, non-adaptive.
	var hist: Array = tl.get_floor_history()
	_eq("floors recorded", hist.size(), FLOORS - 1)
	for row in hist:
		_eq("floor %s generator" % str(row.get("floor_num")), row.get("generator"), "bsp")
		_eq("floor %s phase" % str(row.get("floor_num")), row.get("phase"), "static")

	main.queue_free()
	await _frames(2)
	BuildInfo.force_playtest = -1
	_cleanup()
	finished = true
	_eq("test ran to the end", finished, true)
	if failures.is_empty():
		print("[FORGE TEST] test_bsp_main_flow: PASS (%d checks)" % checks)
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)
