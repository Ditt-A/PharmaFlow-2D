# Research plan — DEM hopper discharge and early clogging diagnostics

## A. Problem definition

Can a calibrated 2D discrete-particle model help explore how outlet size, particle size, friction and wall shape influence stable discharge versus clogging in dry granular systems? Can an ML classifier identify early-warning patterns from simulated state measurements without leakage?

## B. Paper and data

**Primary reference:** Yogi, Jeetram & Khakhar, Devang (2026), *Gravity-driven granular flow from a wedge-shaped hopper: Analysis of the exit region*, Physical Review E 114, 015418, DOI: 10.1103/1ryw-6q89.

**Public data:** https://zenodo.org/records/20554446 (2026); published quasi-2D DEM simulation and experimental Numbers files.

**Reproduction boundary:** the paper uses quasi-2D experimental geometry and 3D DEM; our solver is explicitly 2D disks, so this is an approximate extension/reproduction of physical observables, not an exact reproduction of their numerical method. Paper emphasizes exit-region velocity, acceleration and flow rate rather than an early clogging classifier. ML clogging prediction is our proposed research extension and must be justified by newly generated labeled runs.

## C. Physical state and forces

Per particle i:
- Position r_i=(x_i,y_i), velocity v_i=(vx_i,vy_i), rotation theta_i, angular velocity omega_i, mass m_i, radius R_i.
- Translation: m_i dv_i/dt = m_i g + sum(contact forces).
- Rotation: I_i domega_i/dt = sum(torque_i), I_i = (1/2)m_i R_i^2 for a uniform solid 2D disk approximation.
- Contact: normal overlap, nonadhesive elastic normal spring plus damping, tangential friction with Coulomb cap and contact memory.
- Hopper walls must be treated with geometry-aware signed distances or segment contacts; outlet is an actual gap.

Make assumptions and dimensions transparent. The 2D disk mass requires an assumed unit thickness and material density, or a consistent 2D mass model.

## D. Sample independent simulation configurations

Vary combinations of:
- outlet width in units of median particle diameter (dimensionless ratio);
- particle size distribution and density;
- particle-particle and particle-wall friction;
- wall inclination;
- initial fill height/particle count and random seed.

Use pilot simulations to select feasible ranges. Do not invent realistic pharmaceutical material calibration. Save metadata and complete particle trajectories per run, with statistics.

## E. Quantitative diagnostics

- Per-frame outlet crossing count / number discharge rate; mass discharge if masses assigned.
- Velocity field and bulk packing fraction in fixed regions.
- Near-outlet occupancy, stationary fraction, arch persistence and crossing-free duration.
- Conservation and stability checks; sensitivity to dt, stiffness, number of particles, and seed.
- For comparison with paper, check matching units and geometry first. Report dimensionless discharge rate or normalized velocity only when defensible.

## F. ML experiment

Start with interpretable logistic regression / gradient boosted trees. Temporal input features from t-T through t, target: clog onset within a future horizon after a guard gap. Evaluate 1, 2, and 5 characteristic flow times if supported.
Split by whole run and separately by unseen geometry/material regimes. Avoid overlapping trajectories across splits. Report class imbalance, prevalence, PR-AUC, calibration (Brier score/ECE), event-based recall, false alarms per operating duration, and warning lead time. Use bootstrapped CIs by run, not frames.

Research improvement only after baseline: temporal encoder or interaction-aware graph model with documented ablation.

## G. 2D simulation demo

Two synced panes: solver-generated 2D hopper animation with particles colored by speed/velocity or local density, and plots for cumulative discharged particles, flow-rate window, near-outlet packing, and predicted risk. User may choose from validated run configurations; modifying parameters triggers a new genuine solver run. Label data origin clearly.

## H. Milestone acceptance gates

- **M0**: reproducible environment; accessible verified reference data; source layout and basic tests.
- **M1**: actual DEM integration; contact tests; stable gravity flow and arching in some regimes; animated solver output.
- **M2**: convergence/sensitivity and physically comparable reference analyses (or explicitly document non-comparability).
- **M3**: budgeted scientific dataset, finite first-event labels, causal features, grouped splits and QA.
- **M4A**: CPU baselines with train-only grouped selection, frame/event warning evaluation and readiness decision. See the M4 reports for the frozen protocol and insufficient-generalization conclusion.
- **M4B**: completed 48-attempt targeted expansion and independent configuration evaluation with chronological warnings. Physics-rule baseline remains competitive; preserve the locked test and resolve event-type, policy and calibration limits before advanced modeling.

## I. Industry translation

A research-based proof of concept for powder discharge and feeding stability. Do not imply the materials, operating conditions, flow properties, compliance or validation were provided by Kalbe Farma.
