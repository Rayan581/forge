# Final-1 report: what the team must fill in or check

Draft 2.0 of the Final-1 report is compiled as `FORGE_Final1_Report.pdf` (125 pages, no errors, no missing references). The source is in `latex/` (also zipped as `FORGE_Final1_Report_latex.zip` for Overleaf; compile with pdfLaTeX + BibTeX). Every open item shows in the PDF as red **[TO FILL: ...]** text (65 places). Search for `\tofill` in the source to find them.

## Before showing it to Ms. Mehreen (tomorrow)
1. **Skim the PDF.** It compiles cleanly; only four lines stick out by under 5pt, which is not visible.
2. **Decide whether to leave the red placeholders in.** For a supervisor draft they are fine. They show honestly what has not been measured yet.
3. **Read Table 7.1 (Final-1 status) and Table 3.1 (action register) together.** Make sure all three of you agree with every "Implemented / In progress / Planned" label.
4. **Effort split (Ch 9).** The Mid-1 report said 33.3% each, but the commits were mostly one account. Agree on an honest split and list each person's commits or PRs.

## Numbers to measure (quick)
- Inference latency of the shipped 8-output policy: run `tests/benchmark_inference.gd` once. Then use that one number everywhere (Ch 1 SC-02, Ch 4, Ch 5, Ch 8).
- p95 and max frame time over the 29 real floors, from the `frame_p95_ms` and `frame_max_ms` columns, and which machine was used.
- Latest green CI run: a link or screenshot, plus how many pytest tests passed.
- Real-data counts after syncing any new playtester databases (Ch 5 data audit).

## Facts to confirm
- **Reward-hacking story (Section 7.7.1).** I wrote one account: the first reward let the agent *add rooms* for fast players. It matches the README and the code. `CHANGES.md` CR-03 says the opposite ("collapsed to N=4"). Check the git history of `train_ppo_difficulty.py`, then correct CR-03.
- Who wrote the SQLite `hellsing` branch.
- Git tags. The handoff says `v0.1-poc` and `v0.2-mid1`, but the Mid-1 report said `v0.1.0`. Add a Final-1 tag.
- The asset-pack licences (2D Pixel Dungeon pack, Enemy Animations Set).
- The AI-002 model name, which differs between the AI log and the Mid-1 report. Add AI-log entries for every Iteration 3 Claude session.
- The status of the "don't ask again" rating checkbox. I marked it *In progress (prepared, not merged)*.
- Whether the Mid-1 evaluation gave written feedback. If it did, quote it in Ch 3 and Appendix A.
- Weeks and dates in the milestone table (Table 3.4) and the meeting log (Appendix F).

## Ask the supervisor tomorrow
- Is university ethics approval needed before collecting data from 25+ players and running the UAT? Who holds the tester `.db` files, and for how long?
- Which baseline is the main comparison in the UAT: BSP or static +8%?
- Should Policy SHAP appear in the game overlay, or only in the report?

## Still out of date (not blocking for the draft)
- Most UML figures (class, use case, scene tree, activity, sequence, enemy state machine, low-level architecture) still show the Mid-1 system. Their captions now say so. Redraw them before submission.
- `release.yml` still pins Godot 4.3, and `ai/jh.py` still uses tanh and lists 7 outputs. Both are logged as defects in Ch 8.
- The Hades "God Mode" figures in Ch 2 need a citation.

## What changed from the Mid-1 report (for your own reading)
- New Ch 7 (Iteration 3). The revised architecture is in Section 5.5. The status table is Table 7.1.
- The action is 8-D everywhere, with the archetype mix equation. The observation is described as the code computes it.
- The reward is now the sim-v3 reward from the code, with the hidden-skill limitation stated.
- SQLite schema and ERD replace the JSON table. The privacy section was rewritten (pseudonymous `install_id`, consent, manual file transfer).
- Results use sim-v3 and the Judge results. Real-data results are labelled pilots. The baseline comparison table has placeholders where nothing is measured yet.
- Milestones: the equipment shop moved to Mid-2, and the Judge and SHAP moved to Final-1. Roles: Rayan engine/gameplay, Rana Raza ML/PCG, Uwaid telemetry/CI/evaluation.
- Chapter numbers shift by one after Ch 6, because Iteration 3 got its own chapter.
