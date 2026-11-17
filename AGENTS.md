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
