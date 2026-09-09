# FORGE Project — Action Items & Status

## Completed Items
- [x] Replace all placeholders in `FORGE_Proposal.md` (team members, supervisor, date, WBS assignments)
- [x] Harmonize reward function in §5.5.2 with `train_ppo_difficulty.py` code
- [x] Align action space dimensions (Gate 1: 7-dim POC vs Gate 3: 8-dim committed deliverable)
- [x] Remove `gym-pcgrl` fork references across document and classify custom `DungeonDifficultyEnv`
- [x] Remove FastAPI / REST microservice references and reflect embedded GDScript neural runtime
- [x] Reframe player profile narrative (rolling observation deltas at Gate 1, EMA profile vector at Gate 3)
- [x] Add honest framing for SHAP feature attribution (Gate 1 weighted linear proxy vs Gate 4 regressor SHAP)
- [x] Correct telemetry format (§5.7 JSON prototype, SQLite at Gate 3)
- [x] Add exploration percentage metric to telemetry specifications
- [x] Add formal functional requirements (FR-01 to FR-07 in §4.3.2)
- [x] Add measurable non-functional requirements (NFR-01 to NFR-06 in §4.3.3 and §5.6)
- [x] Add AI-resilience diagnostic and Prior FYP structural overlap audit in §4.1
- [x] Standardize UAT protocol to 10 participants, single-blind counterbalanced within-subjects design
- [x] Fix gate numbering in §6.1 and Gantt schedule
- [x] Cite Reference [9] in §2.1
- [x] Add Professional, Societal & Ethical Compliance section (§8.4)
- [x] Create `CHANGES.md` change control register

## Upcoming Implementation Milestones (Gate 2 & 3)
- [ ] Add fixed set of 3–5 placement calibration maps in Godot prototype (`godot_prototype/`)
- [ ] Migrate `TelemetryLogger.gd` from JSON to embedded SQLite
- [ ] Implement remaining 4 enemy archetypes and activate 8th action dimension (`archetype_complexity`)