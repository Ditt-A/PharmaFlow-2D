# M7A readiness decision

## Decision

`M7A_NUMERICAL_ANALOGUE_FEASIBLE` — the fixed circular obstacle, friction memory, torque/reaction accounting, separate flat-floor geometry, safeguards and trajectory export passed numerical/implementation checks, and all 12 frozen pilot trajectories were numerically valid.

This decision is deliberately scoped to the **numerical analogue**. The experiment did not produce a confirmed arch, startup blockage, completed discharge or source-matched avalanche outcome. Twelve of twelve one-second observations are right-censored for a first confirmed finite arch. It is not evidence that the source phenomenon has been numerically reproduced.

## Evidence and limitations

- All 12 authorized attempts ran to completion; 12 succeeded and 0 failed. Aggregate worker wall time was 1.323 h and aggregate solver CPU time was 1.321 h. The six-worker-hour and 1,800-second-per-attempt limits were respected.
- The maximum normalized overlap was 0.04034 under the original 0.15 guard. Timestep, finite-state, checksum, timestamp, crossing/mass and boundary-leak checks passed.
- Three paired seeds were used for each control/position group. Fixed-grain-to-control finite-horizon mass ratios were 0.809 at q=0.30, 0.871 at q=0.66 and 0.842 at q=1.14. The sample is too small for a precise estimate; these values do not describe the external avalanche-mass observable.
- The Cornerstones system has a shallow fixed magnet on a flat floor, tridisperse free grains, external excitation, replenishment/recirculation and a five-second no-exit event criterion. Several dimensions/mixture/contact properties and exact outlet-boundary definitions remain unknown. M7A instead uses an ideal floor/lip, an assumed equal-count mixture, finite fill, no vibration/replenishment, an outlet-plane crossing and 0.4-second finite-arch confirmation. Friction and stiffness are uncalibrated.
- Therefore no physical agreement score, calibrated coefficient, optimal position or discharge-rate increase is reported. The published q=0.66 maximum is a sampled aggregate mean, not a validated optimum.

Historical M1–M6B evidence and labels, 86 frozen M4B candidates, the 930-file integrity snapshot and M5's two charged demo attempts remain unchanged. The M7A attempt budget is fully consumed; no further pilot or larger campaign is authorized by this result.

## Recommended next decision

Do not launch a larger fixed-grain campaign yet. First obtain/reconcile the experimental mixture fractions, actual floor/lip geometry, magnet placement/tolerance, outlet observation boundary, startup forcing and replenishment/stopping protocol. Decide whether those conditions can be represented without inventing contact or vibration parameters. If the source-compatible observable remains unrecoverable, retain M7A as an explicitly uncalibrated engineering analogue. A future controlled budget should be separately specified and frozen only after that feasibility review; M7A's q locations cannot be reused as an independent experimental test.

See [geometry audit](M7A_GEOMETRY.md), [physics verification](M7A_FIXED_GRAIN_PHYSICS.md), [pilot results](M7A_PILOT_RESULTS.md), and the [M6B source compatibility](M6B_COMPATIBILITY.md).
