# Codex / coding-agent instructions

## Goal and boundaries

Implement **PharmaFlow-2D**, a physically explicit **2D Discrete Element Method (DEM)** simulator for dry granular discharge through a hopper, with downstream AI-assisted clogging diagnostics. It is not CFD and does not need OpenFOAM, YADE, Docker build access, sudo, or apt.

Environment: managed Docker JupyterHub, writable user workspace, conda/pip, NVIDIA A100 80GB if exposed by container. Keep a CPU fallback.

**Current stage:** the explicit M4B request authorized a maximum of 48 new DEM
attempts; all 48 are now consumed and evaluated. The result is
M4B_RULE_BASELINE_REMAINS_COMPETITIVE. Read docs/M4B_EXPANSION.md,
M4B_GENERALIZATION.md and M4B_READINESS.md as well as the M3/M4A reports.
Preserve historical labels, splits, models and test results, and the frozen M4B
model/policy/cohort. No additional campaign, neural model, optimization or
recommendation engine is authorized by this completed budget.

M5 authorizes a separate local interactive demo budget of six solver attempts
and three cumulative simulated seconds, including failures, under
configs/m5/demo_limits.json. It does not extend the M4B campaign. Preserve the
original first-persistent-arch-v1 labels; operational-observation-v1 is a separate
descriptive taxonomy. Keep frozen M4A/M4B policies unchanged and future truth
outside online monitors. No new training, policy tuning or test-based selection.
Keep local dashboard caches, demo outputs, HTML trajectories and artifacts out
of Git; publish only selected compact actual DEM screenshots/animations.

M6A is an external-source/benchmark audit: no new campaign/demo DEM integration, ML training,
physical fitting, neural architecture or design optimization. The result is
M6A_LIMITED_COMPARISON_ONLY. Preserve M1-M5 evidence and the remaining M5 demo
budget for dashboard use. Read docs/M6_EXTERNAL_DATA_AUDIT.md,
M6_PHYSICS_BENCHMARKS.md, M6_CALIBRATION_FEASIBILITY.md and M6_READINESS.md.
Use only the bounded metadata/small-file allowlist in configs/m6; do not download
the 17.41GB Dryad release. Unknown units/geometry/definitions fail quantitative
comparison gates. Separate number and mass flow, 2D areal and 3D bulk density,
numerical convergence and physical calibration. Never fit free-flow scaling to
clogged zeros or use historical held-out results for fitting/selection. M6B's
conditional budget is a proposal, not authorization to execute it.
Existing physics verification tests remain required and are separate from campaign attempts.

M6B-A is now explicitly authorized and completed as data-access/schema recovery
only: M6B_QUALITATIVE_COMPARISON_ONLY. Read docs/M6B_DATA_ACCESS.md,
M6B_EXPERIMENTAL_SCHEMA.md, M6B_COMPATIBILITY.md and M6B_READINESS.md.
Its hard budget is 12 curated files including failed reservations and 200MB;
seven reservations are charged, six files retained. No new solver attempts,
calibration, ML training or design optimization. Preserve acquisition/catalog
ledgers: do not silently retry failures, reset budgets, bypass denials or mirror
archives. Author code is inspected statically, never executed or substituted for
measurements. Unknown units/geometry fail quantitative gates. No follow-on stage
is authorized; retain the M5 ledger and all historical scientific releases.

## Before changes
1. Read README.md and docs/RESEARCH_PLAN.md.
2. Run scripts/check_env.py, python -m pytest -q, scripts/download_reference.py --list.
3. Avoid installing CUDA/PyTorch wheels until kernel/driver version is known.
4. Never commit raw reference data, downloaded archives, generated particle trajectories, model weights or large figures.

## M1 DEM engine requirements (preserve during further work)

Build a reproducible self-contained 2D disk-based DEM implementation, not just trajectory playback.
- Coordinates and forces use SI units; document masses, stiffness, damping, friction coefficients, and collision time.
- Normal particle-particle and particle-wall force: finite overlap, elastic repulsion, damping only during approach as physically justified.
- Tangential contact/friction (Coulomb cap); implement incremental tangential displacement and persistent contact state, or document/validate simplified contact law rigorously. Particle spin and torque from tangential interactions.
- Gravity, semi-implicit integration, optional wall geometry with outlet, neighbor search (uniform spatial hashing/cell lists) for performance. Start with 50–200 disks, then scale after tests.
- Do NOT assume Taichi data structures will accept dynamic Python dictionaries in GPU kernels; maintain appropriate SoA arrays/contact state or a tested alternative.
- Unit tests for free fall, isolated contact, non-penetrating boundaries within numerical tolerances, momentum conservation in elastic isolated pairs, and deterministic run with fixed seed.
- Validate explicit timestep against contact stiffness and stable contact duration. Detect NaNs, excessive overlaps, wall tunneling; fail fast on invalid conditions.
- Save a run-level config/seed plus trajectories and timestamps in HDF5/NPZ. Keep outputs local only.
- Provide matplotlib Animation with at least one real solver-based 2D GIF/MP4; annotate outlet and show discharge count/time. Headless rendering should not require GUI or system packages.
- Each generated run must record solver version, parameters, seed, hardware, wall time, and accuracy checks.

## Published reference dataset

Zenodo record 20554446 contains quasi2D-sim.numbers, quasi2D-expt.numbers, 3D.sim.numbers, with known MD5 checksums in scripts/download_reference.py. These are Apple Numbers document containers; do not pretend they are CSV. First inspect tables using a Numbers-capable parser (for example a user-installable Python package, after verifying compatibility). Audit variable meaning, axes, units, and whether time-series particle positions exist. Published DEM is quasi-2D 3D-particle modeling, different from our 2D disks. Compare aggregate scalings only if scientifically comparable.

Reference: Yogi & Khakhar, Physical Review E (2026), DOI 10.1103/1ryw-6q89. Distinguish exact replication, approximate validation, and qualitative comparison.

## Subsequent milestones

M2: visual and quantitative DEM validation, sensitivity to contact stiffness and dt, outlet/particle ratio, friction and hopper angle.
M3: preserve the budgeted synthetic dataset, future-only first-event labels,
right-censoring policy, causal features and run/configuration grouped splits.
Do not change future labels into model inputs or quietly retry failed cases.
M4A: fit preprocessing and class weights only on training groups, including each
grouped CV fold. Freeze models/features/alert thresholds from training OOF scores
before validation/test evaluation. Do not reshuffle M3 splits or silently retune
against held-out results. Keep models/predictions local; report independent-event
limitations. M4B uses the separately requested 48-attempt ledger, delayed locked
dispatch, training-only grouped policy selection and full chronological replay.
Do not delete its ledger, replace locked configurations or retune after test.

## Quality rules

- Maintain well documented, testable modules in src/pharmaflow; notebooks import them.
- Keep raw data immutable, preserve provenance and licenses.
- Run tests after changes, show failures candidly.
- Never state the project is validated on proprietary Kalbe operations; it is a public-data research proof of concept for pharmaceutical powder handling.
- No exaggerated speedups or predictive performance.
