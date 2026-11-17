# Physics calibration gaps and external validation plan

The engine represents **uncalibrated dry 2D disks**, with explicit friction,
rotation, contact history and gravity. It omits cohesion, humidity sensitivity,
irregular shapes, particle-size polydispersity, gas coupling, electrostatics,
breakage and pharmaceutical surface chemistry. No proprietary pharmaceutical
measurements or industrial validation are available. Warning outputs are scores,
not validated industrial risk probabilities. No process optimization or
deployment readiness is claimed.

## Measurements still needed

| Gap | Required measurement | Proposed validation use |
|---|---|---|
| Mass and geometry | Size/shape distributions, true density, bulk density, hopper dimensions and outlet tolerances | Establish representative particle mass/size distribution and geometry uncertainty. |
| Normal contact response | Restitution versus impact speed; contact/compression tests | Constrain damping and stiffness; demonstrate overlap and timestep convergence at calibrated values. |
| Sliding and rotational friction | Particle-particle and particle-wall shear/tilt tests, wall roughness, rolling resistance | Independent friction constraints; avoid fitting every parameter to a discharge curve. |
| Cohesion and moisture | Humidity-controlled shear cells and tensile/cohesion measurements over relevant storage conditions | Decide whether a dry frictional disk model is applicable at all; document missing physics. |
| Bulk flow and startup | Repeated startup, mass-discharge histories and imaging across outlet sizes, angles and fills | Separate startup blockage, established-flow interruption and completed discharge with prespecified observation times. |
| Local kinematics and contacts | Calibrated high-speed particle tracking/velocity fields near the outlet; imaging uncertainty | Compare compatible velocity/occupancy observables and arch lifetimes, with uncertainty. |
| Dimensionality | Quasi-2D cell thickness, front/back wall friction and 3D particle arrangement | Quantify the mismatch between strict 2D disks and physical 3D particles; potentially require a different engine. |

The published Yogi & Khakhar reference contains spatial profiles/maps of a
quasi-2D system with 3D particles. It does not supply particle trajectories or
the complete calibration information required here. Read
[M2 reference comparison](M2_REFERENCE_COMPARISON.md) and
[M3 dataset report](M3_DATASET.md). Quantitative calibration remains unresolved;
M5 supplies no invented calibration values or agreement claims.

## Proposed external evaluation

Collect independent material characterization before fitting discharge data.
Reserve unseen material/geometry/humidity conditions and independent fills for
validation. Use physical mass flow, velocity profiles and observed arch lifetime
distributions with measurement uncertainty, rather than only binary event
counts. Report parameter non-identifiability and model discrepancy separately
from solver discretization error. Repeat stiffness/timestep sensitivity after
calibration. A dry-disk fit cannot establish behavior for cohesive, irregular,
humid pharmaceutical powders without additional evidence and physics.

For warning evaluation, collect substantially more independent established-flow
events and resumed interruptions. Freeze the taxonomy, horizons, thresholds and
data partitions before external testing. Assess useful lead time and false alarm
burden over complete operation; adjacent video frames are not independent events.
These are future measurements and proposed steps, not completed validation.
