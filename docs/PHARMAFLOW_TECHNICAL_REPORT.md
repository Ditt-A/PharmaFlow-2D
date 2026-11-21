# PharmaFlow-2D: technical report

## Abstract

PharmaFlow-2D is a reproducible research implementation of a strictly two-dimensional, disk-based Discrete Element Method (DEM) hopper simulator. Across M1–M7A, the work progressed from contact mechanics and numerical checks to grouped synthetic datasets, early-warning baselines, chronological monitoring, external-data compatibility audits, an interactive viewer, and an immobile fixed-grain extension. The M8 release verification reports 237 passing tests, including strict Taichi 1.7.3 CPU/CUDA checks. M4B found the frozen physics rule competitive with the selected XGBoost baseline on seven locked independent events. M6 did not establish a quantitatively matched external validation target. M7A produced 12 valid but censored fixed-grain runs, no confirmed arch, and no reproduction of the Cornerstones phenomenon. This is an instrumented, uncalibrated engineering simulator, not an industrial risk predictor.

## 1. Introduction

Granular discharge can show continuous flow, intermittent pauses, and contact arches near an outlet. A research simulator must represent individual particle contacts, preserve trajectories, expose numerical failure, and evaluate warnings at the independent-event level. PharmaFlow-2D focuses on dry granular hopper behavior in 2D and asks whether observed particle dynamics add warning value beyond a transparent physics rule.

The scope is narrow. The model does not represent a pharmaceutical formulation, a Kalbe process, gas/liquid transport, or an industrial hopper installation. No proprietary process data were used. “PharmaFlow” describes the engineering context, not a validation claim.

## 2. Related work and reference scope

Yogi and Khakhar report gravity-driven flow from a wedge-shaped hopper and provide experimental, quasi-2D, and 3D spatial-profile/map tables. The audited tables do not contain particle IDs or time-resolved trajectories; source units and coordinate definitions remain incomplete for a matched residual [1, 2].

The Cornerstones release contains granular-flow records and an aggregate fixed-grain curve [3, 4]. User-recovered source files document pixel positions, second-valued timestamps, inter-frame displacements, cumulative ejected area, and a dimensionless fixed-grain position. Full particle-tracking MAT runs were not acquired. Its tridisperse grains, confinement, floor/outlet setup, vibration-assisted reset, recirculation, and five-second clog confirmation differ from the finite-fill 2D model.

A TU Delft hopper collection was audited [5]. The bounded accessible subset provided acquisition metadata and image/calibration archives, but not a calibrated mass-discharge history or validated velocity field. A strict-2D discharge study is cited in the benchmark report as dimensional context [6], not as independent experimental calibration.

## 3. Physical model and assumptions

Mobile material is represented by circular disks in a plane. For overlapping particles, a linear normal spring generates repulsion and normal damping acts during approach. Tangential relative displacement accumulates per persistent contact, is projected onto the changing tangent, and is limited by a Coulomb friction cap. Tangential force generates particle torque and spin. Particle-wall contacts use corresponding mechanics. Gravity drives discharge through finite hopper walls and a gated outlet.

The baseline integrator is semi-implicit and uses a cell-based neighbor search. Runs record physical timestamps, state arrays, configuration, seed, diagnostics, and provenance. A Taichi 1.7.3 kernel can evaluate contact terms on CPU or CUDA; neighbor search and other solver work remain on CPU in the verified hybrid path.

The selected M1–M3 values were `kn=4000 N/m`, `kt=1000 N/m`, `dt=5e-6 s`, and a maximum-overlap guard of `0.15 R`. These are numerical/material assumptions, not parameters measured from a matched external powder. M7A used the same stiffness and overlap guard with `dt=2.5e-6 s` to satisfy the smallest polydisperse particle's timestep limit.

The model omits true 3D particle contacts, front/back confinement friction, cohesion, humidity, air coupling, irregular morphology, and unmeasured surface roughness. M7A adds an immobile circular obstacle with its own friction-history bookkeeping and an ideal flat-floor geometry; obstacle reaction force goes to an external support.

## 4. Numerical implementation and verification

M1 verified force/contact behavior, deterministic seeded runs, bounded overlap, finite states, and actual solver-generated animations. The wide-outlet example discharged all 100 particles; the narrow-outlet case maintained a finite arch over the final 0.2 s of its observation. These are finite simulation observations, not permanent-clogging claims.

M2 evaluated contact/energy checks, timestep refinement, controlled outlet and friction experiments, deterministic replay, particle conservation, and CPU/CUDA contact parity. In an elastic pair refinement, maximum energy error decreased from 1.27746% to 0.634738% to 0.316388% for `dt`, `dt/2`, and `dt/4`. This supports numerical refinement for that assay; it is not physical calibration. In the broader campaign, maximum overlap approached the existing guard, which was retained.

M3 added stiffness sensitivity and state/overlap/data-quality checks; maximum dataset overlap was 0.0834 R under the same guard. M7A's frictionless fixed-obstacle impact yielded maximum relative energy excursions of 0.900050%, 0.448023%, and 0.223513% at 10, 5, and 2.5 microseconds. Support-impulse residual was below `6.8e-20 kg m/s`. This tests impulse accounting; mobile-particle momentum alone is not conserved because the fixed support supplies reaction force.

The M8 suite reports 237 passes, including strict Taichi CPU/CUDA checks. Convergence and backend agreement address numerical/implementation error only. Friction, damping, and exported particles can legitimately reduce mechanical energy; approximate hopper energy accounting is not exact energy closure.

## 5. Synthetic dataset generation

M3's bounded solver campaign comprised 36 attempts, of which 30 independent runs entered the released dataset. It produced 11 first-persistent-arch runs, 9,030 feature rows, and 18,060 horizon-label rows for 0.05 s and 0.10 s. Its run-grouped split uses 18/6/6 complete runs; the configuration-holdout split uses 20/5/5.

M4B froze 48 attempts: 12 pilot, up to 24 adaptive development, and 12 locked evaluation runs over four unseen configurations. All attempts yielded valid runs; the expanded cohort contained 31 first-persistent-arch events across 15 physical configurations. The locked evaluation contained seven events. It was evaluated once after model and policy freeze; historical M3 test runs were not added to new training.

## 6. Clogging and operational event definitions

The original `first-persistent-arch-v1` labels use future evidence over a 0.4 s persistence window. Event onset and confirmation are separate timestamps. Future onset/confirmation is excluded from online predictors. Post-onset, empty-hopper, and insufficient-future-observation states are handled under the release protocol.

M5 adds `operational-observation-v1` without changing M3/M4 labels. Startup blockage means a confirmed arch before any observed outlet crossing. Post-discharge arch requires at least one earlier crossing but does not establish continuous flow. Established flow uses a stricter preceding-flow criterion: a complete 100 ms interval, at least five crossings over three or more frames, and no crossing gap greater than 40 ms. Temporary interruption is confirmed only retrospectively after flow resumes. Completed discharge and unresolved/censored observations are separate outcomes.

Across 78 M3/M4B runs, the audit reports 19 startup first arches, 23 post-discharge first arches, and seven established-flow arches as a subset of the latter. Seven temporary interruption episodes occurred in four runs; 36 runs completed discharge. These synthetic counts are not external event frequencies.

## 7. Baseline ML methods

M4A evaluated constant prevalence, a current-observation physics rule, regularized logistic regression, random forest, and XGBoost with static, current-state, temporal, full, proxy-excluded, and time/cumulative-feature-excluded ablations. Preprocessing and class weighting were learned from training groups/folds. Run and configuration split assignments were frozen; adjacent frames were treated as correlated observations. The primary and secondary horizons were 0.10 s and 0.05 s.

M4B preserved frozen M4A artifacts and compared the original rule, a development-informed rule, frozen M4A models, and newly fitted classical baselines. Alert policy selection used development groups and chronological replay. Model scores are not calibrated industrial probabilities. No GNN, Transformer, world model, neural training, or design optimizer was built.

## 8. Generalization evaluation and results

On seven M4B locked events, the original frozen M4A physics rule produced 7/7 useful warnings (at least 20 ms before onset), zero false first-event forecasts, and 58 ms mean valid lead. The selected M4B XGBoost also achieved 7/7 useful warnings but produced 12 false first-event forecasts and 77 ms mean valid lead. The development-informed rule had 7/7 useful warnings and eight false forecasts. At 0.05 s, selected models and rules showed different useful-recall/false-alert trade-offs; neither result demonstrates ML superiority.

The effective independent-event count is seven across four held-out configurations. Startup blockages form a substantial portion of events, and few represent arches after established flow. Configuration, packing, and material generalization remain uncertain. Frame-level ranking does not offset a small independent event count.

## 9. Fixed-grain numerical extension

M7A implemented a separate immobile circular obstacle, contact history, mobile-body torques, support-reaction accounting, ideal flat-floor geometry, and polydisperse mobile radii/masses while preserving legacy wedge behavior. Tests cover contact, sliding, memory reset, torque, overlap, timestep constraints, conservation, determinism, and Taichi parity.

The frozen pilot used 12 attempts: three paired seeds each for no fixed grain and `x/dFG = 0.30, 0.66, 1.14`, with 60 disks over 1.0 s. All 12 runs were valid; all 12 were right-censored for a confirmed arch; there were zero confirmed arches, startup blockages, or completed discharges. Maximum normalized overlap was 0.04034 under the unchanged 0.15 guard. Fixed-grain/control finite-horizon ejected-mass ratios were 0.809, 0.871, and 0.842. These small-sample numerical results are not the experimental avalanche-mass observable, not discharge rates, and not an agreement score. M7A did not reproduce the experiment.

## 10. Discussion

The project demonstrates an end-to-end engineering workflow: explicit force modeling, numerical guards, deterministic output, run-level validation, leakage-aware data handling, configuration holdout, event-based warning evaluation, causal monitoring, and an interface for actual trajectories. The baseline result is neutral: the physics rule remained competitive and ML did not show a clear event-level advantage with the available evidence.

External comparison remains blocked by missing or incompatible measurements. Cornerstones is the closest circular-grain candidate but differs in mixture, confinement, geometry, forcing, replenishment, boundaries, and event confirmation. Delft concerns irregular 3D gravel and the accessible subset lacks calibrated discharge/velocity tables. Yogi & Khakhar offers spatial profiles/maps without a compatible time history or fully resolved units. The Cornerstones 17-bin fixed-grain summary is not a trajectory and is not quantitatively comparable to M7A's finite-fill mass crossing.

## 11. Limitations

1. The engine models dry 2D disks with simplified soft-contact laws, not 3D or pharmaceutical material behavior.
2. Friction, restitution, roughness, particle distribution, and real wall interfaces have not been measured for a matched target.
3. Numerical convergence and CPU/CUDA parity do not demonstrate physical calibration.
4. M3/M4B contain few independent positive events; the M4B locked cohort has seven events across four configurations.
5. Warning scores are not calibrated risk probabilities. Startup blockage and established-flow interruption are different phenomena.
6. Full trajectories, Parquet datasets, and model artifacts are local/ignored; a fresh clone has committed figures and a compact animation but cannot replay every run without restoring those artifacts.
7. All M7A observations were censored for arches, under geometry, forcing, and stopping conditions unlike the experiment.
8. No pharmaceutical deployment or industrial validation is claimed.

## 12. Conclusion

PharmaFlow-2D is a verified numerical research platform and an engineering portfolio in computational physics and scientific ML evaluation. Its strongest evidence is implementation and evaluation discipline, not physical agreement or predictive superiority. Current results support carefully scoped, uncalibrated engineering simulation and further data-access work. They do not support parameter calibration, advanced temporal modeling, optimized design recommendations, or industrial deployment claims.

## References

1. Yogi, J. & Khakhar, D. (2026). “Gravity-driven granular flow from a wedge-shaped hopper: Analysis of the exit region.” *Physical Review E* 114, 015418. [DOI](https://doi.org/10.1103/1ryw-6q89).
2. Yogi & Khakhar data release. [Zenodo record 20554446](https://zenodo.org/records/20554446). Schema limits: [M2 reference comparison](M2_REFERENCE_COMPARISON.md).
3. Hanlan, Dillavou, Durian & Liu. Cornerstones granular-flow study, author preprint [arXiv:2407.05491](https://arxiv.org/abs/2407.05491).
4. Hanlan et al., [Dryad Cornerstones record](https://doi.org/10.5061/dryad.cvdncjtb5), CC0 dataset. Recovery and fixed-grain summary: [M6B recovery](M6B_RECOVERY.md).
5. Fransen, Schott & Langelaar, [TU Delft Hopper Discharge collection](https://doi.org/10.4121/C.6415736); audit: [M6 external report](M6_EXTERNAL_DATA_AUDIT.md).
6. Carlevaro et al. (2024), strict-2D granular-flow study, *Frontiers in Soft Matter*. [DOI](https://doi.org/10.3389/frsfm.2024.1340744). Dimensional context only, not independent experimental calibration.

Additional configurations, checksums, and reproduction commands are in the milestone reports linked from the [README](../README.md).