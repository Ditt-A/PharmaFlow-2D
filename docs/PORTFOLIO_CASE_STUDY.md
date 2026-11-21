# Portfolio case study: PharmaFlow-2D

## Engineering problem

Granular hoppers can alternate between free discharge, intermittent pauses, and arches at an outlet. The engineering question was whether a transparent, reproducible 2D particle simulator could support useful event diagnostics, and whether data-driven warnings improved on an interpretable physics rule.

## Why DEM

The research state of interest is the set of particle positions, velocities, rotations, and contacts. DEM models those discrete contacts directly. A continuum CFD solver would be appropriate for fluid flow; gas coupling, humidity, cohesion, and fluid-particle effects were outside scope. This choice keeps the implemented model focused, but limits its relevance to dry 2D disks.

## Physics implementation

The solver implements normal spring/damping contact, history-dependent tangential friction with a Coulomb cap, particle spin/torque, gravity, hopper walls, neighbor search, and a semi-implicit time integrator. It exports seeded trajectories and diagnostics. Safeguards detect excessive overlap, unstable steps, nonfinite states, and boundary-accounting errors. Taichi 1.7.3 provides a tested optional contact kernel with CPU/CUDA parity; the small-particle-count GPU path is hybrid rather than a claimed speedup.

The fixed-grain extension preserves the legacy wedge behavior and adds a true immobile obstacle, separate tangential history, mobile-particle torque, and support-reaction accounting. The extension is numerically tested but not a reproduction of the Cornerstones experimental apparatus.

## Verification and data design

M1–M3 add contact tests, repeatability, timestep refinement, energy diagnostics, conservation, overlap limits, controlled experiments, and CPU/CUDA comparisons. A representative elastic pair's maximum energy error fell from 1.27746% to 0.316388% across `dt` to `dt/4`. That verifies numerical refinement under the tested conditions, not physical calibration.

The M3 release contains 30 independent runs, 11 first-arch events, 9,030 causal feature rows, and 18,060 labels across two horizons. Run- and configuration-grouped splits prevent frames from one trajectory appearing across partitions. M4B adds 48 frozen attempts and an evaluation cohort of seven events across four unseen configurations.

## Scientific ML experiment

Classical baselines included logistic regression, random forest, and XGBoost, compared with a constant baseline and physics rules. Preprocessing, class weighting, model selection, and alert thresholds were learned only on grouped training data. Chronological replay did not use future onset as online input. Frame ranking was reported separately from warning lead time and false-alert episodes.

On seven M4B locked events, the original frozen M4A physics rule produced 7/7 warnings with at least 20 ms lead, zero false first-event forecasts, and 58 ms mean valid lead. The selected M4B XGBoost also warned on 7/7 events but produced 12 false first-event forecasts and a 77 ms mean valid lead. This is a small-cohort observation. It does not establish perfect rule performance or ML inferiority in general, but ML did not show a clear event-level advantage. A neural architecture was not scientifically justified.

## External validation and fixed-grain outcome

Cornerstones, TU Delft, and Yogi & Khakhar sources were audited for access, units, geometry, boundaries, and compatible observables. None currently supplies a matched external target for quantitative calibration. The 17-bin Cornerstones fixed-grain summary is an aggregate normalized ejected-mass curve, not a time-resolved trajectory.

M7A froze 12 fixed-grain numerical attempts. All 12 runs were valid but right-censored for arch formation at 1.0 s; there were zero confirmed arches and no experimental phenomenon reproduction. Finite-horizon mass outcomes were nonmonotonic across three exploratory positions. They were not compared as a physical agreement score, and no friction was tuned.

## Interactive outcome

The Streamlit dashboard replays real stored trajectories, plots physical time and discharge history, colors particles by speed, optionally overlays contacts, and presents rule/model monitoring alongside clearly separated post-hoc annotations. A Run button creates only bounded unevaluated CPU demo runs. Fresh clones without full trajectory or model artifacts display missing-data notices rather than fabricating a replay or model score.

## Engineering lessons

- Numerical convergence and backend parity are necessary implementation checks; they do not establish physical calibration.
- Event-level evaluation and independent runs matter more than a high frame-level score when adjacent observations are correlated.
- A clear baseline can remain competitive; added model complexity should follow stronger independent evidence.
- Censoring, temporary pauses, startup blockage, and completed emptying need distinct labels.
- Experimental geometry and measurement definitions must be reconciled before fitting contact parameters.
- Portfolio visualizations should preserve their source trajectories, physical timestamps, and limitations.

## CV-ready description

**PharmaFlow-2D — Reproducible DEM and granular-flow diagnostics:** Built a 2D disk-based hopper simulator with history-dependent friction, rotational dynamics, numerical guards, trajectory export, grouped scientific datasets, classical early-warning baselines, and an interactive trajectory dashboard. Evaluated numerical convergence, independent configuration splits, and event-level warning policies; documented the lack of matched external calibration.

## Technically defensible achievements

- Implemented and tested a deterministic 2D DEM contact solver with tangential contact memory, disk rotation, timestep/overlap safeguards, and optional Taichi 1.7.3 CPU/CUDA contact parity.
- Built run- and configuration-grouped synthetic-data and causal event-monitoring pipelines; on the seven-event M4B locked cohort, the frozen physics rule had 7/7 useful warnings and zero false first-event forecasts, with explicit small-sample limits.
- Delivered an interactive solver-trajectory dashboard and a separately tested immobile fixed-grain extension; all 12 M7A pilot observations were censored for arch formation, so no experimental reproduction or calibration was claimed.

No pharmaceutical deployment, Kalbe validation, or industrial readiness is claimed.