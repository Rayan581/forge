# Task: Implement a Complete CI/CD Pipeline for FORGE

## 1. Project Overview

We are developing **FORGE: Personalized Procedural Content Generation via Reinforcement Learning**, a university Final Year Project at FAST-NUCES Islamabad.

FORGE is a combat dungeon crawler that uses player gameplay telemetry to infer player capability and uses a trained Proximal Policy Optimization (PPO) reinforcement learning policy to generate personalized dungeon difficulty.

The project has two primary components:

**A. Game application**
- Godot Engine 4.x
- GDScript
- Native inference of the exported PPO policy through GDScript matrix operations
- Procedural dungeon generation
- A* pathfinding and solvability validation
- Enemy AI and combat mechanics
- SQLite-based gameplay telemetry
- Player progression, equipment, and in-game economy
- Difficulty prediction and explainability interface
- Standalone 64-bit Windows executable

**B. Machine learning and research code**
- Python
- PyTorch 2.x
- Stable-Baselines3
- Gymnasium
- PPO training and evaluation
- Custom `DungeonDifficultyEnv` environment
- Telemetry-based player profiling
- Difficulty regression
- SHAP or permutation-based feature attribution
- Export of trained policy parameters to JSON for inference inside Godot

The exported policy is intended to be lightweight, with a target size below 120 KB and an inference latency below 0.5 ms. These are project targets that must be measured and validated, not assumed to be true.

The project also evaluates four procedural generation approaches:
1. Constructive rule-based generation using Binary Space Partitioning (BSP).
2. Unconditioned PPO-based procedural generation.
3. PPO with static designer-defined difficulty targets.
4. FORGE's telemetry-conditioned PPO approach.

The project aims to evaluate dungeon solvability, difficulty prediction, structural diversity, adaptation speed, and player acceptance.

## 2. Primary Objective

Design and implement a reliable, maintainable, project-specific CI/CD pipeline for FORGE.

Do not merely provide an example YAML file. Inspect the existing repository, determine the actual technologies, scripts, tests, dependencies, assets, and build requirements, and implement the pipeline accordingly.

The pipeline must validate both the Godot application and the Python ML/RL components. It must also validate compatibility between the trained Python policy and the native GDScript inference implementation.

Use GitHub Actions unless the existing repository clearly uses another CI/CD platform.

Do not assume that every proposed component already exists. Discover what is present, identify gaps, and adapt the implementation to the real repository.

## 3. Mandatory Initial Repository Audit

Before modifying any files, inspect the repository structure and relevant source files.

Identify:

- The location of `project.godot`.
- The installed or configured Godot Engine version.
- Whether the project uses standard Godot or Godot .NET.
- All GDScript source files, scenes, resources, and game entry points.
- The location of the Python ML/RL code.
- Python version and dependency-management method.
- Existing `requirements.txt`, `pyproject.toml`, lockfiles, and configuration files.
- Existing test directories and test frameworks.
- The Gymnasium environment implementation and its observation/action spaces.
- PPO model initialization, training, checkpointing, and evaluation scripts.
- Policy export scripts and the JSON policy format.
- GDScript code that loads and evaluates the exported policy.
- Dungeon generation, connectivity, A* validation, and seeded random generation.
- Telemetry logging, SQLite database initialization, and migrations.
- Difficulty regression and explainability code.
- Existing export presets and Windows packaging requirements.
- Existing CI workflows, Git branching conventions, and release process.
- Any external dependencies, API keys, datasets, model checkpoints, or hardware requirements.

Produce a concise audit report listing:

1. Existing components.
2. Missing components.
3. Existing tests and their coverage.
4. Potential CI/CD blockers.
5. Recommended workflow design.
6. Files that need to be created or modified.

Do not rewrite working project code merely to fit a preferred folder structure. Preserve the current architecture unless a concrete problem requires a change.

## 4. CI Pipeline Requirements

Create a GitHub Actions workflow, preferably `.github/workflows/ci.yml`, adapted to the repository.

### 4.1 Workflow triggers

Configure the workflow to run on:

- Pull requests targeting the main development branch.
- Pushes to relevant development branches.
- Pushes to the main branch.
- Manual execution through `workflow_dispatch`, where useful.

Avoid running expensive jobs unnecessarily. Use path filters or conditional execution only where they will not allow required checks to be bypassed.

### 4.2 Python environment setup

The workflow must:

- Check out the repository.
- Set up the Python version required by the project.
- Install dependencies using the repository's actual dependency-management method.
- Use dependency caching when beneficial.
- Keep dependencies reproducible and avoid installing arbitrary latest versions.
- Install development and testing dependencies as appropriate.
- Fail clearly if dependency installation fails.

Do not arbitrarily upgrade the project's dependencies or change its Python version without checking compatibility.

### 4.3 Python code quality

Configure suitable static checks for the existing codebase.

Consider:

- Ruff or an equivalent Python linter.
- Formatting verification.
- Type checking where practical.
- Import and syntax validation.

Use the project's existing tools if they are already configured. Introduce new tools only when justified, and configure them to match the codebase rather than causing unrelated mass-formatting changes.

### 4.4 Automated Python tests

Discover the existing test framework and implement or integrate automated tests for:

- Telemetry processing and profile calculations.
- Construction and normalization of the 8-dimensional observation vector.
- Handling of missing, invalid, or incomplete telemetry.
- Combat Rating calculations and equipment-related difficulty adjustments.
- Gymnasium environment initialization and reset.
- Observation-space and action-space validity.
- Environment `step()` behavior, termination, and truncation.
- Reward calculation and completion-pacing logic.
- Dungeon generation and connectivity.
- A* solvability validation.
- Difficulty regression input/output behavior.
- Policy export and serialization.
- Policy loading and parameter validation.
- SQLite schema initialization, inserts, queries, and persistence.
- Existing fallback behavior when the policy file is absent or corrupted.

Do not create tests that simply execute code without asserting meaningful results.

Use deterministic test data and fixed random seeds where appropriate. Isolate tests from production databases, external services, and expensive training runs.

If a component does not yet exist, report the gap rather than inventing an implementation that misrepresents the project.

### 4.5 Gymnasium environment validation

Add appropriate checks for `DungeonDifficultyEnv`, if it exists.

Use Gymnasium's environment validation utilities where compatible.

Verify that:

- Reset returns valid observations and required metadata.
- Steps return correctly structured observations, rewards, termination flags, and metadata.
- Observations conform to the declared observation space.
- Actions conform to the declared action space.
- Rewards are finite.
- Episodes terminate under expected conditions.
- Fixed seeds produce reproducible results where determinism is intended.

Keep the validation lightweight enough for regular CI execution.

### 4.6 PPO training smoke test

Implement a short PPO smoke test where practical.

The smoke test should verify that:

- The environment can be constructed.
- The PPO model can initialize.
- A small number of training timesteps can execute.
- The model can be saved and loaded.
- Evaluation and inference produce valid outputs.

Do not train the complete research model on every commit. The full 300,000-timestep experiment is a separate research workload unless there is a specific reason to automate it.

Do not require a GPU for ordinary CI unless the actual project cannot run without one.

### 4.7 Policy JSON validation

The exported policy is consumed by the Godot application. Treat compatibility between the Python exporter and GDScript inference engine as a critical integration boundary.

Inspect the actual JSON schema and inference implementation before writing validation logic.

Validate:

- Required keys and metadata.
- Expected tensor or matrix dimensions.
- Weight and bias counts.
- Numeric values are finite and not NaN or infinity.
- Activation functions and layer ordering match the inference implementation.
- Observation dimensions and feature ordering match the 8D profile specification.
- Normalization and denormalization conventions are consistent.
- Output dimensions and action interpretation are correct.
- The policy can be loaded and evaluated using representative inputs.
- The file size meets the configured project target, if this check is appropriate.

Create a small deterministic fixture or test policy if necessary. Do not fabricate a trained policy and present it as the actual research model.

### 4.8 Cross-language inference parity

Implement an integration test for the Python-to-GDScript policy boundary.

Where technically feasible:

1. Create a deterministic test policy with known weights and biases.
2. Supply fixed input vectors to the Python reference implementation.
3. Evaluate the same policy and inputs using the actual GDScript inference implementation.
4. Compare the outputs within an explicitly justified numerical tolerance.
5. Verify the handling of invalid inputs and policy-loading failures.

Use a headless Godot invocation or a suitable automated Godot test framework. If direct cross-language parity testing cannot initially be implemented, document the blocker and implement the closest meaningful automated validation without falsely claiming parity has been verified.

### 4.9 Godot validation

Configure a Godot CI job using a compatible, pinned Godot 4.x version.

Determine whether the project requires the standard or .NET build.

At minimum, where supported by the project's actual structure:

- Import project resources.
- Perform headless startup or parsing checks.
- Detect GDScript parse errors.
- Validate required scenes and resources.
- Run existing automated Godot tests.
- Exercise policy loading and fallback paths where feasible.
- Check that required game assets are included.

Investigate the correct Godot command-line flags for the selected engine version. Do not assume that a successful editor launch proves that the game is functional.

A headless project check is not a substitute for gameplay testing. Document which runtime and rendering behaviors cannot be tested on a standard hosted runner.

### 4.10 Dungeon solvability and generation tests

Add lightweight automated tests that generate dungeons across a fixed collection of seeds.

Check:

- Valid room counts.
- Entry and exit room existence.
- Valid room coordinates and boundaries.
- Connected room graphs.
- A* path availability between required points.
- Correct handling of blocked or unreachable exits.
- Valid placement of enemies, traps, and resources.
- Reproducibility for fixed seeds where expected.

The proposal targets at least 95% topological solvability. Define the exact metric and test population before enforcing a threshold.

Do not claim a 95% solvability rate based on a handful of seeds. Keep quick smoke tests in regular CI and larger statistical evaluation runs in a separate workflow.

## 5. Build and Artifact Requirements

Define how the project should be packaged after CI succeeds.

For Python:

- Validate imports and dependencies.
- Run the test suite.
- Save relevant reports.
- Package model exports or experiment artifacts only where appropriate.

For Godot:

- Use the project's actual export presets.
- Configure the Windows 64-bit export template.
- Export the standalone game.
- Include the correct policy JSON and other required resources.
- Verify that the executable and packaged resources exist.
- Run a smoke test where the runner supports it.

If a complete Windows export or graphical runtime test cannot run on the chosen runner, explain why and use an appropriate Windows runner or a separate job.

Avoid uploading huge intermediate files or training checkpoints by default.

## 6. CD and Release Workflow

Create a separate `.github/workflows/release.yml` if this cleanly separates release logic from CI.

The release workflow should:

1. Trigger on a version tag or a GitHub release event.
2. Run all mandatory CI checks or depend on an equivalent verified set of checks.
3. Export the Godot project for Windows x86-64.
4. Package the executable and required resources.
5. Validate the packaged policy and fallback behavior.
6. Run available smoke tests.
7. Create a distributable ZIP or equivalent package.
8. Publish the artifact to a GitHub Release, if permissions and release configuration allow it.
9. Preserve version information and relevant build metadata.

Do not deploy the game to a cloud server unless the actual project requirements call for it. FORGE is intended to be a standalone Windows application.

If automatic publishing is initially inappropriate, create the build-and-package workflow and document the remaining manual release step.

## 7. Security and Reliability

Apply reasonable CI/CD security practices.

- Use the minimum required GitHub Actions permissions.
- Pin action versions appropriately and explain the chosen versioning strategy.
- Store secrets in GitHub Actions secrets or protected environments.
- Never commit API keys, passwords, personal credentials, or deployment tokens.
- Avoid exposing secrets in workflow logs.
- Restrict release publishing to trusted tags or authorized workflows.
- Use dependency vulnerability checks and secret scanning where practical.
- Avoid executing untrusted pull-request code with privileged credentials.
- Make essential test failures fail the workflow.
- Provide readable logs and useful failure summaries.
- Set reasonable job timeouts.
- Avoid unnecessary repeated dependency installation.
- Cache only safe, appropriate build and dependency outputs.

Do not introduce deployment secrets if the workflow does not require them.

## 8. Research Reproducibility

Because FORGE is an AI research project, preserve experiment traceability.

Where appropriate, record:

- Model checkpoint identifier.
- Git commit SHA.
- Training configuration.
- Random seeds.
- Dependency versions.
- Evaluation dataset or test fixture version.
- Number of training timesteps.
- Evaluation metrics.
- Policy export version.
- Policy artifact checksum.

Keep full PPO training and large statistical evaluations separate from the default pull-request workflow.

If automated research experiments are useful, create an optional manually triggered workflow that accepts validated parameters and has sensible runtime limits.

Do not automatically overwrite the validated policy artifact with a newly trained model unless the team has explicitly designed and reviewed that process.

## 9. Performance Requirements

Identify the measurable performance targets in the proposal and implement appropriate validation.

These include:

- Policy inference latency below 0.5 ms.
- Exported policy size below 120 KB.
- Game performance of at least 60 FPS at 1080p.
- Memory consumption below 250 MB.
- Dungeon solvability target of at least 95%.
- Difficulty predictor MAE of at most 0.15 on the defined normalized scale.

Do not treat all of these as ordinary CI assertions.

Use lightweight regression checks for metrics that are stable and measurable in CI. Run hardware-sensitive performance benchmarks on representative hardware under controlled conditions.

Document the benchmark method, hardware, measurement units, warm-up procedure, sample count, and acceptance criteria. Distinguish between a measured result and an unverified target.

## 10. Workflow Design and Efficiency

Prefer separate jobs for logically independent tasks.

A reasonable initial design is:

- Python lint and static checks.
- Python unit and integration tests.
- Gymnasium environment validation and PPO smoke test.
- Policy artifact validation and cross-language compatibility checks.
- Godot headless checks and automated game tests.
- Optional dungeon statistical evaluation.
- Windows export and release packaging.

Use parallel execution where it reduces overall runtime without introducing unnecessary complexity.

Ensure the required CI status check has a stable name and cannot accidentally pass because a conditional job was skipped.

Do not make every advanced job mandatory for every pull request. Clearly distinguish mandatory CI, optional scheduled/manual research evaluations, and release-only jobs.

## 11. Deliverables

Implement the solution in the existing repository.

Provide:

1. A repository audit summary.
2. A documented CI/CD architecture.
3. The complete GitHub Actions YAML files.
4. Any necessary test files and test fixtures.
5. Policy JSON validation and compatibility tests.
6. Godot headless validation configuration.
7. A Windows build and release workflow.
8. Any necessary dependency or tooling configuration.
9. Documentation explaining how to run checks locally.
10. Documentation explaining workflow triggers, jobs, artifacts, and failures.
11. A list of GitHub repository settings that must be configured manually, including branch protection, required status checks, secrets, and release permissions.
12. A list of tests that passed, failed, or could not be executed.
13. Remaining limitations and recommended next steps.

For every file created or modified, briefly explain its purpose.

## 12. Implementation Rules

- Inspect the actual repository before editing.
- Do not assume filenames, commands, folder layouts, or test frameworks without checking.
- Reuse existing working code and tooling.
- Avoid unnecessary refactoring.
- Keep the pipeline understandable for a university project team.
- Use pinned or reproducible tool and dependency versions where appropriate.
- Never fabricate test results.
- Never claim a workflow has passed unless it was actually executed successfully.
- Do not silently skip failing tests.
- Do not add unnecessary cloud infrastructure, Kubernetes, or deployment platforms.
- Avoid committing generated datasets, large model checkpoints, or secrets.
- Make sensible decisions independently and document them rather than stopping for approval on every minor implementation detail.
- If something cannot be completed because of missing code, credentials, runner limitations, or unavailable tooling, implement the remaining independent work and document the blocker.

## 13. Final Acceptance Criteria

The implementation is considered complete when:

- The repository's Python checks run successfully.
- Automated Python tests execute and produce meaningful results.
- The Gymnasium environment passes its applicable validation checks.
- The PPO smoke test works without requiring full research training.
- The exported policy is validated against its expected schema.
- Python-to-GDScript inference compatibility is tested, or any remaining blocker is explicitly documented.
- Godot headless validation runs successfully to the extent supported by the project.
- Dungeon generation and solvability have automated tests.
- Pull requests receive clear pass/fail status checks.
- A Windows build can be generated and packaged through the release workflow, subject to runner and export-template availability.
- Build artifacts and release outputs are traceable to the relevant commit.
- Documentation explains how the team can reproduce the process.

Start with the repository audit, then implement the pipeline incrementally. At the end, summarize what was implemented, which commands and workflows were actually tested, what remains incomplete, and how to run the complete pipeline.
