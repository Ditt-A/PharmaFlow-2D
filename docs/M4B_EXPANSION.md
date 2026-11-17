# M4B targeted DEM expansion protocol

M4B continues commit `9576bfa9ba17730e068e6185162e0a90929bead5`. The explicit
M4B user request authorizes the previously proposed 48-attempt campaign. M3/M4A
labels, published splits, frozen models and held-out results remain immutable.
No neural model, world model, optimization or deployment engine is introduced.

## Frozen design and accounting

The design is frozen before any new solver outcome, at
**2026-11-17 05:22:05 UTC**. Its immutable manifest is
`data/simulated/m4b/manifests/design_freeze.json`, SHA256
`6e5ca16f7397d8329e47d079c67a40d9325c5cb92611f8b97becc1dba6ddc518`.
The complete configuration is [design.json](../configs/m4b/design.json).
Locked parameters, packing families, seeds and initial-state fingerprints are
fixed before pilot execution. Four locked canonical physical groups are absent
from every M3/pilot group. Adaptive development cannot include a locked group.

| Phase | Maximum charged attempts | Design |
| --- | ---: | --- |
| Development pilot | 12 | Four outlet ratios, three packing families each |
| Adaptive development | 24 | Eight controlled cases, three families/new seeds each |
| Locked evaluation | 12 | Four new configurations, three families/new seeds each |
| Total ceiling | **48** | Failures and interrupted reservations consume slots |

The atomic attempt ledger is charged **before** dispatch. A process/file lock
prevents concurrent ledger writers. Failed runs are saved in a separate failure
catalogue and never silently retried. Interrupted reserved attempts are retained
as failures when resuming, rather than spending another uncounted integration.
Completed phase resumes verify checksums and preserve the original runtime
manifest. The ceiling counts campaign attempts; existing physics/unit-test
integrations are validation tests, not additional dataset runs.

Locked solver dispatch is blocked until `model_and_policy_freeze.json` exists
with matching design/model checksums and declares no locked outcomes seen.
An access receipt binds that exact freeze to the first locked dispatch. Thus
locked feature/label data does not even exist during model development. The
training loader rejects a locked release and training refuses an existing freeze
or already-generated locked runs. Evaluation refuses to overwrite its completed
receipt. No failed/empty/low-event test configuration is replaced.

## Physical and numerical design

The validated NumPy CPU DEM engine is unchanged. Taichi stays at **1.7.3**.
kn=4000 N/m, kt=1000 N/m, normal/tangential damping=.30/.06 kg/s,
dt=5e-6s and the **unchanged 0.15 R** overlap guard are explicit in every task.
Disk radius is .002m, density 2500kg/m3, assumed thickness .01m and g=9.81m/s2.
Gate opening is .05s. Samples occur every .005s.

Nominal observation is **2.5s**. The same integrator, contact memory and spin
continue to **3.5s** only if at 2.5s particles remain without a confirmed first
event. No state is reset. Empty absorbing states use the previously tested
fast-forward optimization. Successful records preserve full NPZ trajectories,
contacts, forces/energy diagnostics, wall/overlap checks, timing and provenance.

Pilot ratios are **2.1, 2.55, 2.95, 3.4**, at fixed 35 degrees from vertical,
mu_pp=mu_wall=.4 and N=40. Staggered, hexagonal and random-sequential families
are crossed in every configuration, with distinct seeds 11001-11012. Geometry
uses `funnel_height=(outer_width-outlet)/(2*tan(angle))`, preserving wall angle
when varying outlet. Independent packing variation remains stochastic; these
are not identical-state paired outlet contrasts.

The locked cohort is fixed as follows, with seeds 13001-13012 assigned in case
order, then staggered/hexagonal/random-sequential order:

| Case | D/d | Angle from vertical | mu_pp | mu_wall | N |
| --- | ---: | ---: | ---: | ---: | ---: |
| A narrow | 2.20 | 32 | .45 | .35 | 45 |
| A wider | 2.85 | 32 | .45 | .35 | 45 |
| B narrow | 2.60 | 39 | .35 | .55 | 35 |
| B wider | 3.30 | 39 | .35 | .55 | 35 |

The A and B pairs each isolate outlet width while preserving angle/friction/fill.
This is unseen-combination interpolation in the sampled physical range, not a
claim of arbitrary material/geometric extrapolation. Initial states are checked
against all M3 states and other planned states before dispatch; new seeds do not
silently reuse a packing.

## Pilot review before expansion

All **12/12** pilot attempts succeed: **five first-event runs**, seven completed
discharges, no naturally censored runs and no continuation required. D/d=2.1
gives 3/3 events, 2.55 gives 2/3, and 2.95/3.4 give 0/3. Maximum overlap is
**.071198 R**, below .15 R. P=.2/.4/.6s all give five events. No later-resumed
interior crossing gap >=.05s occurs in the pilot; no interruption is invented.
Pilot physical elapsed time is **783.05s** at four CPU workers.

The review selects the **mixed-outcome D/d=2.55** control, not only always-clogged
anchors. [adaptive.json](../configs/m4b/adaptive.json) repeats that control with
new seeds and adds one-factor changes: mu_pp=.25/.55, mu_wall=.25/.55,
angle=28/42 degrees, or N=50. Every other parameter stays at the control value.
This is eight cases / 24 new attempts, seeds 12001-12024. The repeat control
improves independent packing/seed coverage instead of pretending it is a new
physical group. Desired event coverage is not a quota or stopping/retry rule.

Adaptive execution uses eight CPU workers with one BLAS thread per worker,
within the inspected 64-core cgroup quota (256 visible cores). There is no GPU
training or CUDA/Taichi replacement. Actual measured cost, not extrapolated
speedup, is reported with the final campaign results.

## Labels, features and versioned storage

The primary target remains M3 `first-persistent-arch-v1`: a common spanning
contact structure, low near-outlet speed, retained grains and no crossings
persist for P=.4s, checked at all monitored integration intervals. Onset and
future confirmation differ. This is a finite-duration first event, not permanent
clogging. P=.2/.4/.6 sensitivity is exported separately without modifying the
primary labels. Later resumed flow is retained and does not erase a confirmed
finite event.

For H=.10/.05s, positive means onset in `(t,t+H]`. A negative needs future
observation through `t+H+P`; unsupported future stays nullable/right-censored.
Post-onset, empty and gate-closed rows retain their original exclusion status.
Numerical failures are not negatives. The exact M3 causal extractor and byte-
identical feature dictionary are reused: 41 predictors plus four identifiers.
Genuine-prefix tests verify that later observations cannot change earlier
features. No new learned or future-derived feature is introduced.

```text
data/simulated/m4b/{pilot,adaptive,locked}/<run_id>/trajectory.npz,run.json,...
data/simulated/m4b/manifests/{design_freeze,attempts,*_campaign,locked_access_receipt}.json
data/simulated/m4b/failures/
data/processed/m4b/{pilot,development,locked}/
  run_metadata.parquet,temporal_features.parquet,event_labels.parquet
  events.parquet,persistence_sensitivity.parquet
  feature_dictionary.json,split_manifest.json,dataset_manifest.json
outputs/checkpoints/m4b/                  # new fitted artifacts
outputs/metrics/m4b/                      # OOF/full scores, freezes, receipts, logs
outputs/animations/m4b/                   # actual solver-based animations
docs/results/m4b/                        # compact published evidence only
```

Every new task preserves run/configuration IDs, physical group, seed, packing
family/fingerprint, source/version, physical/numerical configuration, duration,
sampling, checksum and validity. Old runs are copied into development only if
they were **training runs in BOTH published M3 benchmarks**. No original M3
validation/test run is promoted into new fitting. Copied labels/features remain
unchanged and the M3 release stays byte-identical.

New development validation holds out whole physical configurations: pilot
`outlet_2p95` was designated before pilot execution; adaptive `particle_friction_low`
and `angle_42` were designated before adaptive execution. All replicates stay
together. The pilot was openly reviewed for experimental design, so development
validation is descriptive; the outcome-blind independent test is the locked
cohort. Model/policy selection uses training groups only.

Completed development contains **36/36 valid new runs, 24 first events** and no
naturally censored runs. Adaptive execution takes **1241.87s** at eight workers.
The new control outcomes differ from the pilot (1/3 versus 2/3 events), showing
why packing/seed replication matters. Adding the **12 historically permitted M3
training runs** gives 48 development runs / 29 events: **39 training runs / 24
events**, and **9 validation runs / 5 events**. There are 21648 feature rows and
43296 label rows in this development release. These include copied historical
training rows and must not all be counted as new independent evidence.

## Reproduction on the existing environment/release

```bash
conda activate pharmaflow-2d
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python scripts/run_m4b.py --phase freeze
python scripts/run_m4b.py --phase pilot --jobs 4
python scripts/evaluate_m4b.py --stage build-pilot
# Review the pilot before using the documented frozen adaptive plan.
python scripts/run_m4b.py --phase adaptive --jobs 8
python scripts/evaluate_m4b.py --stage build-development
python scripts/evaluate_m4b.py --stage train
# The gate below requires a complete model/policy freeze.
python scripts/run_m4b.py --phase locked --jobs 8
python scripts/evaluate_m4b.py --stage evaluate
python scripts/evaluate_m4b.py --stage visualize
python scripts/evaluate_m4b.py --stage audit
python scripts/summarize_m4b.py
python scripts/plot_m4b_diagnostics.py
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

M3 Parquet data and M4A local artifacts are prerequisites; do not regenerate them
for this milestone. Packages are the existing M4A CPU environment (`.[ml,test]`),
with no new dependency installation. On a completed release, use audit,
visualization and summary stages; train/evaluate deliberately refuse overwrite.
Phase reruns verify cached raw checksums without dispatching another solver.

Reproduction commands, final counts and the model/generalization evidence appear
in the companion reports. Completed phases/releases are reused by checksum;
never delete historical data, relabel M3 or increase the campaign ceiling to
improve a result.

Final new-only release: **48 valid runs, 31 first events, 15 physical groups,
24048 feature rows and 48096 label rows**. All 48 observe 2.5s; no continuation,
natural censoring or failure occurs. P=.2/.4/.6 each gives 31 events. Four runs
have genuine later-resumed crossing gaps, maximum .09434s; none resumes after
a confirmed .4s arch. New peak overlap is **.078115 R**. Raw/processed/model
sizes are approximately 28.0/3.0/1.59MB and stay local. Compact manifests,
split assignments, event/context counts and checksum receipts are published
under `docs/results/m4b/`.
