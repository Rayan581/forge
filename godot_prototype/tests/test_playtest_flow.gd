# tests/test_playtest_flow.gd
# Playtest-study plumbing: persisted consent, post-floor difficulty rating (and its per-run
# "Don't ask again" checkbox), developer-override flag,
# same-floor regeneration keeping telemetry consistent, playtest build hiding developer tools, and
# game_version being set. Runs Main.tscn end to end with the JSON backend on scratch files, so it
# never touches a real player's settings or telemetry.
#
# Run:  godot --headless --path godot_prototype --script res://tests/test_playtest_flow.gd
extends SceneTree

const TelemetryLoggerScript = preload("res://scripts/TelemetryLogger.gd")

var failures: Array[String] = []
var checks := 0
## A GDScript runtime error aborts the current function but not the caller, so each step counts
## itself as finished; a missing count fails the test instead of reporting a false PASS.
var steps_finished := 0
const STEPS := 6
const TAG := "test_pt"

func _initialize() -> void:
	_run()

func _eq(label: String, got: Variant, want: Variant) -> void:
	checks += 1
	if str(got) != str(want):
		failures.append("%s: got %s, expected %s" % [label, str(got), str(want)])

func _ok(label: String, cond: bool) -> void:
	_eq(label, cond, true)

func _cleanup() -> void:
	for n in ["%s_settings.cfg", "%s_tel.json", "%s_tel.db", "%s_install.txt", "%s_unit.json", "%s_unit_install.txt"]:
		var p := ProjectSettings.globalize_path("user://" + (n % TAG))
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

func _frames(n: int) -> void:
	for i in n:
		await process_frame

func _run() -> void:
	_cleanup()
	GameSettings.file_path = "user://%s_settings.cfg" % TAG
	_test_settings()
	_test_logger_override_and_restart()
	await _test_main_flow(true)
	await _test_main_flow(false)
	await _test_pause_menu()
	await _test_dont_ask_again()
	BuildInfo.force_playtest = -1
	_cleanup()
	_eq("all steps ran to the end", steps_finished, STEPS)
	if failures.is_empty():
		print("[FORGE TEST] test_playtest_flow: PASS (%d checks)" % checks)
		quit(0)
	else:
		for f in failures:
			printerr("[FORGE TEST] FAIL: " + f)
		quit(1)

# ---------------------------------------------------------------------------------------------

func _test_settings() -> void:
	GameSettings.remove_file()
	var s := GameSettings.new().load_from_disk()
	_eq("fresh settings: undecided", s.consent_decided, false)
	_eq("fresh settings: no consent", s.consent_given, false)
	_eq("fresh settings: rating on by default", s.rate_floors, true)
	_eq("no rating prompt without consent", s.should_ask_rating(), false)
	s.set_consent(true)
	var s2 := GameSettings.new().load_from_disk()
	_eq("consent persisted", s2.consent_given, true)
	_eq("decided persisted", s2.consent_decided, true)
	_eq("rating prompt with consent", s2.should_ask_rating(), true)
	s2.rate_floors = false
	s2.save_to_disk()
	_eq("rating opt-out persisted", GameSettings.new().load_from_disk().should_ask_rating(), false)
	# A file that says consent_given but was never decided must not count as consent.
	var cfg := ConfigFile.new()
	cfg.set_value("privacy", "consent_given", true)
	cfg.save(GameSettings.file_path)
	_eq("undecided never counts as consent", GameSettings.new().load_from_disk().consent_given, false)
	steps_finished += 1

func _test_logger_override_and_restart() -> void:
	var tl = TelemetryLoggerScript.new()
	tl.backend_preference = "json"
	tl.json_path = "user://%s_unit.json" % TAG
	tl.install_id_path = "user://%s_unit_install.txt" % TAG
	_ok("game_version set (was empty before)", tl._game_version().begins_with("0.9.0"))

	tl.begin_floor(1, 4)
	tl.record_room_visited(Vector2i(0, 0))
	tl.record_damage_dealt(40.0)
	tl.record_enemy_defeated()
	tl.record_death()
	tl.restart_floor_layout(6) # Defense Panel regenerate: same attempt, new layout
	_eq("restart keeps damage", tl.floor_damage_dealt, 40.0)
	_eq("restart keeps kills", tl.floor_enemies_defeated, 1)
	_eq("restart keeps deaths", tl.floor_deaths, 1)
	_eq("restart new rooms_total", tl.floor_rooms_total, 6)
	_eq("restart flags override", tl.floor_manual_override, true)
	tl.record_floor(null, {"floor_num": 1, "completion_time": 12.0, "phase": "adaptive"})
	tl.begin_floor(2, 3)
	tl.record_floor(null, {"floor_num": 2, "completion_time": 9.0, "phase": "adaptive"})
	tl.begin_floor(3, 3)
	tl.mark_manual_override("slider")
	tl.record_floor(null, {"floor_num": 3, "completion_time": 9.0, "phase": "adaptive"})
	var rows: Array = tl.load_floors(tl.session_id)
	_eq("unit rows", rows.size(), 3)
	if rows.size() == 3:
		_eq("floor 1 manual_override", int(rows[0]["manual_override"]), 1)
		_eq("floor 2 clean", int(rows[1]["manual_override"]), 0)
		_eq("floor 3 slider override", int(rows[2]["manual_override"]), 1)
		_eq("floor 1 damage kept across regenerate", float(rows[0]["damage_dealt"]), 40.0)
	_eq("session totals == floor sums (damage)", tl.damage_dealt, 40.0)
	tl.set_perceived_difficulty(2, 3.0)
	_eq("history rating updated", tl.get_floor_history()[1]["perceived_difficulty"], 3.0)
	tl.close()
	steps_finished += 1

## End-to-end through Main.tscn (playtest build). consent=true: rating prompt pauses the game and its
## answer lands on the floor row. consent=false: no prompt, the next floor starts straight away.
func _test_main_flow(consent: bool) -> void:
	var tag := "consent" if consent else "noconsent"
	_cleanup()
	BuildInfo.force_playtest = 1
	var s := GameSettings.new()
	s.set_consent(consent)

	var main = load("res://scenes/Main.tscn").instantiate()
	root.add_child(main)
	await process_frame # Main._ready (creates the logger) runs once the tree is processing
	var tl = main.telemetry_logger
	tl.backend_preference = "json"
	tl.json_path = "user://%s_tel.json" % TAG
	tl.db_path = "user://%s_tel.db" % TAG
	tl.install_id_path = "user://%s_install.txt" % TAG
	await _frames(3)
	_eq("[%s] logger consent from settings" % tag, tl.consent_given, consent)
	_eq("[%s] no consent screen once decided" % tag, main.consent_screen == null, true)

	main.main_menu.visible = false
	main._on_start_run_requested()
	await _frames(6)
	_eq("[%s] floor 1 built" % tag, main.current_dungeon_level, 1)
	_eq("[%s] playtest: panel button hidden" % tag, main.defense_overlay.toggle_btn.visible, false)
	_eq("[%s] playtest: HUD shows only the floor" % tag, main.defense_overlay.room_label.text, "Floor 1")
	_eq("[%s] playtest: difficulty badge hidden" % tag, main.defense_overlay.hud_diff_label.visible, false)

	if consent:
		# Developer regenerate on the same floor: counters survive, floor is flagged.
		tl.record_damage_dealt(25.0)
		main._on_rebuild_dungeon_requested()
		await _frames(3)
		_eq("[%s] regenerate keeps floor damage" % tag, tl.floor_damage_dealt, 25.0)
		_eq("[%s] regenerate flags override" % tag, tl.floor_manual_override, true)

	main._on_dungeon_escaped()
	await _frames(2)
	if consent:
		_eq("[%s] rating prompt open" % tag, main.floor_rating.is_open, true)
		_eq("[%s] game paused during rating" % tag, paused, true)
		main._on_dungeon_escaped() # portal re-entered while the prompt is up: ignored
		await _frames(1)
		_eq("[%s] portal re-entry ignored" % tag, tl.get_floor_history().size(), 1)
		main.floor_rating.choose(4)
		await _frames(4)
		_eq("[%s] unpaused after rating" % tag, paused, false)
	else:
		_eq("[%s] no rating prompt" % tag, main.floor_rating.is_open, false)
		_eq("[%s] not paused" % tag, paused, false)
	await _frames(4)
	_eq("[%s] advanced to floor 2" % tag, main.current_dungeon_level, 2)

	var rows: Array = tl.load_floors(tl.session_id)
	_eq("[%s] one floor row" % tag, rows.size(), 1)
	if rows.size() == 1:
		var r: Dictionary = rows[0]
		_eq("[%s] perceived difficulty" % tag, r.get("perceived_difficulty", null), 4.0 if consent else null)
		_eq("[%s] manual_override" % tag, int(r.get("manual_override", -1)), 1 if consent else 0)
		_eq("[%s] floor damage == session damage" % tag, float(r["damage_dealt"]), tl.damage_dealt)
	var sess: Dictionary = tl._ensure_backend().get_session(tl.session_id)
	_eq("[%s] session consent" % tag, int(sess.get("consent", -1)), 1 if consent else 0)
	_ok("[%s] session game_version is the playtest build" % tag, str(sess.get("game_version", "")).ends_with("-playtest"))

	tl.close()
	main.queue_free()
	await _frames(2)
	paused = false
	steps_finished += 1

## Pause menu: opens only during a run, freezes the clock, resumes, and "Return to Main Menu" saves the
## session, starts a fresh one and lets the player start again.
func _test_pause_menu() -> void:
	_cleanup()
	BuildInfo.force_playtest = 1
	var s := GameSettings.new()
	s.set_consent(true)
	var main = load("res://scenes/Main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	var tl = main.telemetry_logger
	tl.backend_preference = "json"
	tl.json_path = "user://%s_tel.json" % TAG
	tl.db_path = "user://%s_tel.db" % TAG
	tl.install_id_path = "user://%s_install.txt" % TAG
	await _frames(3)
	_eq("[pause] cannot pause from the main menu", main._can_pause(), false)
	main.main_menu.visible = false
	main._on_start_run_requested()
	await _frames(6)
	_eq("[pause] can pause during a run", main._can_pause(), true)
	main.pause_menu.open("test")
	await _frames(1)
	_eq("[pause] menu open", main.pause_menu.is_open, true)
	_eq("[pause] tree paused", paused, true)
	_eq("[pause] cannot open twice", main._can_pause(), false)
	var t0: float = tl.elapsed_seconds
	await _frames(12)
	_eq("[pause] clock frozen", tl.elapsed_seconds, t0)
	main.pause_menu.resume()
	await _frames(2)
	_eq("[pause] resumed: tree running", paused, false)
	_ok("[pause] resumed: clock runs again", tl.elapsed_seconds > t0)

	# Return to the main menu mid-run
	var old_session: String = tl.session_id
	tl.elapsed_seconds = maxf(tl.elapsed_seconds, 1.0) # a run shorter than 0.5 s is not worth a row
	main.pause_menu.open("test")
	await _frames(1)
	main._return_to_main_menu()
	await _frames(3)
	_eq("[pause] leaving: tree running", paused, false)
	_eq("[pause] leaving: run ended", main.game_started, false)
	_eq("[pause] leaving: menu visible", main.main_menu.visible, true)
	_eq("[pause] leaving: player hidden", main.player.visible, false)
	_eq("[pause] leaving: dungeon cleared", main.active_rooms.size(), 0)
	_ok("[pause] leaving: new session id", tl.session_id != old_session)
	_ok("[pause] leaving: fresh clock", tl.elapsed_seconds < 0.5)
	_eq("[pause] cannot pause from the menu again", main._can_pause(), false)
	_eq("[pause] old session was saved", not tl._ensure_backend().get_session(old_session).is_empty(), true)

	# And a second run starts normally
	main.main_menu.visible = false
	main._on_start_run_requested()
	await _frames(6)
	_eq("[pause] second run: floor 1 built", main.current_dungeon_level, 1)
	_eq("[pause] second run: can pause", main._can_pause(), true)

	tl.close()
	main.queue_free()
	await _frames(2)
	paused = false
	steps_finished += 1

## "Don't ask again": floor 1 ticks the box but skips (still asked next floor), floor 2 ticks it and
## rates (floor 3 shows no prompt). Starting a new run shows the prompt again (per run only).
func _test_dont_ask_again() -> void:
	_cleanup()
	BuildInfo.force_playtest = 1
	var s := GameSettings.new()
	s.set_consent(true) # the prompt only exists for consenting players
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

	# Floor 1: tick the box but skip -> still asked on floor 2.
	main._on_dungeon_escaped()
	await _frames(2)
	_eq("[dontask] floor 1 prompt open", main.floor_rating.is_open, true)
	main.floor_rating.set_dont_ask_again(true)
	main.floor_rating.choose(0)
	await _frames(8)
	_eq("[dontask] skip with box ticked does not stop asking", main.floor_rating.stop_asking, false)
	_eq("[dontask] advanced to floor 2", main.current_dungeon_level, 2)

	# Floor 2: tick the box and rate -> stop asking.
	main._on_dungeon_escaped()
	await _frames(2)
	_eq("[dontask] floor 2 prompt open", main.floor_rating.is_open, true)
	main.floor_rating.set_dont_ask_again(true)
	main.floor_rating.choose(3)
	await _frames(8)
	_eq("[dontask] rating with box ticked stops asking", main.floor_rating.stop_asking, true)
	_eq("[dontask] advanced to floor 3", main.current_dungeon_level, 3)
	_eq("[dontask] floor 2 rating still stored", tl.get_floor_history()[1]["perceived_difficulty"], 3.0)

	# Floor 3: no prompt, the game is not paused and goes straight to floor 4.
	main._on_dungeon_escaped()
	await _frames(2)
	_eq("[dontask] floor 3: no prompt", main.floor_rating.is_open, false)
	_eq("[dontask] floor 3: not paused", paused, false)
	await _frames(6)
	_eq("[dontask] advanced to floor 4", main.current_dungeon_level, 4)

	# New run: the prompt comes back.
	tl.elapsed_seconds = maxf(tl.elapsed_seconds, 1.0)
	main._return_to_main_menu()
	await _frames(3)
	main.main_menu.visible = false
	main._on_start_run_requested()
	await _frames(6)
	_eq("[dontask] new run resets the flag", main.floor_rating.stop_asking, false)
	main._on_dungeon_escaped()
	await _frames(2)
	_eq("[dontask] new run: prompt shown again", main.floor_rating.is_open, true)
	main.floor_rating.choose(0)
	await _frames(4)

	tl.close()
	main.queue_free()
	await _frames(2)
	paused = false
	steps_finished += 1
