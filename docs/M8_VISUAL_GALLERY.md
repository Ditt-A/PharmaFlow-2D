# PharmaFlow-2D visual gallery

Every moving particle scene below is rendered from an existing solver trajectory. M8 reuses the committed files without changing their frame sampling or scientific meaning. Full NPZ trajectories remain local and ignored.

## Continuous discharge and speed

![Solver-generated 50-disk discharge, speed colored](../assets/m2_demo.gif)

Source: M2 compact preview; see [validation report](M2_VALIDATION.md). The particle colors encode speed, and the preview uses stored solver states.

## Persistent arch / startup blockage

![Actual DEM startup blockage scene](results/m5/startup.gif)

Source: M5 representative scene; see [operational event report](M5_OPERATIONAL_EVENTS.md). The finite observation follows the project's event protocol and does not prove indefinite clogging.

## Temporary interruption followed by resumed flow

![Actual DEM pause and resumed discharge](results/m5/resumed.gif)

Source: M5 replay of a genuine stored run. Later outlet crossings distinguish this retrospective example from a persistent arch annotation.

## Interactive dashboard

![Streamlit dashboard screenshot](results/m5/dashboard.png)

Source: M5 dashboard validation. It displays actual trajectory frames and synchronized traces. Without ignored local trajectory files, a fresh clone displays an explicit restore-artifacts message.

## Fixed-grain numerical analogue

![Actual fixed-grain DEM trajectory](results/m7a/near.gif)

M7A used 12 valid one-second runs; all were right-censored for a confirmed arch, and none reproduced the external fixed-grain observation. See [pilot results](M7A_PILOT_RESULTS.md).

## Physics rule and ML evaluation

![Frozen M4B locked cohort comparison](results/m4b/locked_summary.png)

The original frozen M4A rule produced 7/7 useful warnings and zero false first-event forecasts on the seven-event M4B locked cohort. This small sample is not evidence of universal generalization. See [M4B evaluation](M4B_GENERALIZATION.md).

## Numerical convergence

![Timestep convergence results](results/m2/hopper_convergence.png)

This is a numerical refinement result, not external physical calibration. See [M2 validation](M2_VALIDATION.md).