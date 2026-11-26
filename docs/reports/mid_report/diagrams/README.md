# FORGE draw.io diagram sources

Each `*.drawio` file is an editable draw.io diagram (open with https://app.diagrams.net or the draw.io desktop app).
`*.pdf` (vector) and `*.png` (3x) are the renders used in the LaTeX report.

| File | Used in the report |
|---|---|
| fig_4_2_use_case | Fig. 4.1 Use case diagram |
| fig_5_1_system_architecture | Fig. 5.1 Four-tier architecture |
| fig_low_level_architecture | Fig. 5.2 Low-level component/dataflow |
| fig_class_diagram | Fig. 5.3 UML class diagram |
| fig_5_8_1_activity_diagram | Fig. 5.4 Activity diagram |
| fig_seq_inter_floor_adaptation | Fig. 5.5 Sequence diagram |
| fig_state_enemy_ai | Fig. 5.6 Enemy FSMs |
| fig_6_3_godot_scene_tree_hierarchy | Fig. 6.1 Scene tree |
| fig_e_1_two_stage_procedural_pipeline | Fig. E.1 Two-stage pipeline |
| fig_e_2_visual_asset_combat_feedback | Fig. E.2 Combat feedback event flow |

## Edit and re-export
1. Open the `.drawio` file, edit.
2. File -> Export as -> **PDF** (tick "Crop") -> save as `<same name>.pdf` into the report's `ThesisFigs/` folder (overwrite).
   (PNG export also works: set zoom 300 %, transparent background off.)
3. Rebuild the report (pdflatex -> bibtex -> pdflatex x2). `\includegraphics` picks the PDF first.

Diagram text was derived from the GDScript/Python sources in the repo. If the code changes (e.g. you add the Static Baseline toggle or the solvability step to ci.yml), update the matching diagram.
