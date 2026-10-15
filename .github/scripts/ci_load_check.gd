# ci_load_check.gd
# Runs as the main scene (--main-pack or via --path) in headless Godot.
# Walks every .gd, .tscn, and .tres in res:// and:
#   - loads each resource (catches parse/compile errors)
#   - for .tscn files, instantiates the scene (catches missing-node errors)
# Exits 0 on success, 1 if any error is detected.
#
# Usage in CI:
#   godot --headless --path godot_prototype --script .github/scripts/ci_load_check.gd
#
# NOTE: autoloads ARE registered because we run inside --path, not --script alone.

extends SceneTree

func _init():
	var exit_code := 0
	var dir := DirAccess.open("res://")
	if dir == null:
		print("ERROR: Could not open res://")
		quit(1)
		return

	var files := _collect_files(dir, "res://")
	print("ci_load_check: scanning %d resources…" % files.size())

	for path in files:
		var ext := path.get_extension().to_lower()
		if ext not in ["gd", "tscn", "tres"]:
			continue

		# --- load -------------------------------------------------------
		var res = load(path)
		if res == null:
			print("FAIL load: %s" % path)
			exit_code = 1
			continue

		# --- instantiate scenes ----------------------------------------
		if ext == "tscn":
			if not (res is PackedScene):
				print("FAIL not a PackedScene: %s" % path)
				exit_code = 1
				continue
			var inst = res.instantiate()
			if inst == null:
				print("FAIL instantiate: %s" % path)
				exit_code = 1
			else:
				inst.queue_free()
				print("ok  scene: %s" % path)
		else:
			print("ok  res:   %s" % path)

	if exit_code == 0:
		print("ci_load_check: ALL RESOURCES OK")
	else:
		print("ci_load_check: ERRORS DETECTED (see above)")

	quit(exit_code)


func _collect_files(dir: DirAccess, base: String) -> Array:
	var result := []
	dir.list_dir_begin()
	var fname := dir.get_next()
	while fname != "":
		if fname.begins_with("."):
			fname = dir.get_next()
			continue
		var full := base.path_join(fname)
		if dir.current_is_dir():
			var sub := DirAccess.open(full)
			if sub:
				result.append_array(_collect_files(sub, full))
		else:
			result.append(full)
		fname = dir.get_next()
	dir.list_dir_end()
	return result
