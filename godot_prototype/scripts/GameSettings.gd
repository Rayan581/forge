## Player settings that persist across runs (user://forge_settings.cfg).
##
## consent_decided: the consent screen has been answered once (it is not shown again).
## consent_given:   the player agreed to contribute gameplay data to the FORGE study corpus.
## rate_floors:     ask "How hard did that floor feel?" after each floor (only while consenting).
class_name GameSettings
extends RefCounted

## Tests point this at a scratch file so they never touch a real player's settings.
static var file_path: String = "user://forge_settings.cfg"

var consent_decided: bool = false
var consent_given: bool = false
var rate_floors: bool = true

## Loads from file_path; missing file or keys keep the defaults above.
func load_from_disk() -> GameSettings:
	var cfg := ConfigFile.new()
	if cfg.load(file_path) == OK:
		consent_decided = bool(cfg.get_value("privacy", "consent_decided", false))
		consent_given = bool(cfg.get_value("privacy", "consent_given", false))
		rate_floors = bool(cfg.get_value("study", "rate_floors", true))
	if not consent_decided:
		consent_given = false # an unanswered prompt never counts as consent
	return self

func save_to_disk() -> bool:
	var cfg := ConfigFile.new()
	cfg.set_value("privacy", "consent_decided", consent_decided)
	cfg.set_value("privacy", "consent_given", consent_given)
	cfg.set_value("study", "rate_floors", rate_floors)
	return cfg.save(file_path) == OK

func set_consent(given: bool) -> void:
	consent_decided = true
	consent_given = given
	save_to_disk()

## True when the post-floor difficulty rating should be shown.
func should_ask_rating() -> bool:
	return consent_given and rate_floors

static func remove_file() -> void:
	var p := ProjectSettings.globalize_path(file_path)
	if FileAccess.file_exists(p):
		DirAccess.remove_absolute(p)
