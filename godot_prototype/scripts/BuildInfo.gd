## Build flavour + version string, shared by telemetry and UI.
##
## Playtest builds are exports whose preset lists the custom feature "playtest" (see
## export_presets.cfg). They hide the developer Defense Panel and on-screen difficulty numbers,
## so testers cannot change the settings the policy picked, and their difficulty ratings are not
## anchored by a "Hard (64/100)" badge. Pass `-- --playtest` on the command line to try the
## playtest flavour from the editor binary.
class_name BuildInfo
extends RefCounted

const PLAYTEST_FEATURE := "playtest"

## Tests set this: -1 = detect from the build, 0 = force developer build, 1 = force playtest build.
static var force_playtest: int = -1

static func is_playtest() -> bool:
	if force_playtest >= 0:
		return force_playtest == 1
	return OS.has_feature(PLAYTEST_FEATURE) or OS.get_cmdline_user_args().has("--playtest")

## Developer tools (Defense Panel, presets, auto-kill, static toggle) are only offered outside playtests.
static func dev_tools_enabled() -> bool:
	return not is_playtest()

## application/config/version plus the build flavour, e.g. "0.9.0-playtest", "0.9.0-dev".
## This is what telemetry stores in sessions.game_version, so tester runs can be told apart
## from developer runs in the corpus.
static func version() -> String:
	var v := str(ProjectSettings.get_setting("application/config/version", "")).strip_edges()
	if v.is_empty():
		v = "0.0.0"
	if is_playtest():
		return v + "-playtest"
	if OS.has_feature("editor"):
		return v + "-dev"
	return v
