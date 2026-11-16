# M2 numerical validation and DEM benchmarking

Verified on node680, 17 November 2026 (Asia/Jakarta). This is an uncalibrated
strictly 2D disk model. These results establish tested numerical behavior for
the configurations below, not industrial validity or a full paper reproduction.

## Repository and M1 baseline

Before simulator changes, confirmed `/home/adityaakbar/adit/PharmaFlow-2D`, branch
`main`, remote `https://github.com/Ditt-A/PharmaFlow-2D.git`, and no upstream
divergence after fetch. Verified the uncommitted M1 source, tests and outputs;
29 tests passed including strict Taichi CPU/CUDA tests. `validate_m1.py` confirmed
100/100 discharge and the documented 80-disk, finite-window arch observation.
M1 was committed/published as **8988a5f837885e64c8cbe528c4aeac0fafbe8020** before
M2 source edits. The published source tree matched the staged node680 tree.
Branch updates use a checked expected head; concurrent changes are never forced.

Python 3.11.18; NumPy 1.26.4; Taichi **1.7.3**, pinned in environment.yml and
the acceleration extra; GLIBC 2.31; A100-SXM4-80GB, driver 580.126.20. CPU is
the campaign default. CUDA is a hybrid contact-law backend, not a fully GPU
integrator. Neither PyTorch nor ML is required or implemented.

## Design and quantities

All runs use SI, R=0.002 m, density=2500 kg/m³, thickness=0.01 m,
kn=1000 N/m, kt=250 N/m, gamma_n=0.15 kg/s and gamma_t=0.03 kg/s unless a
controlled benchmark explicitly disables dissipation. Gate opening is 0.05 s.
dt=1e-5 s is below the default 1.14411e-5 s guard. Initial states are
nonoverlapping staggered fills with seeded small jitter, not fully randomized
independent packings. Seeds are 11, 22 and 33; this is a small pilot ensemble.

PhysicsMonitor passively records contact-step overlap histograms (bin width
0.001 R), force peaks, angular speed, acceleration, finite state and sidewall
center leakage. Histogram quantiles are bin upper bounds and include both wall
and particle contacts, weighted by contact timestep, not independent samples.
Tests confirm instrumentation preserves trajectories exactly. Original M1
tests remain passing. Final suite: **41 passed**, including strict CUDA tests;
one upstream Taichi locale deprecation warning remains. `pip check` passes.

Per-run NPZ/JSON remains under `outputs/metrics/m2/`. Compact CSV/JSON summaries
and small PNG figures are versioned in [results/m2](results/m2/). Source and
initial-state fingerprints, physical duration, parameters, hardware and runtime
are recorded. Postprocessing also checks that an allegedly completed hopper is
actually empty above the outlet, not merely that every grain once crossed.

## Pilots and repeated experiments

The initial ten-case, 50-disk, seed-11, 0.45 s pilot had **9 successes and one
guarded failure**. A 10 mm initial lift caused overlap **0.1506 R**, exceeding
the unchanged 0.15 R limit. It is retained in `pilot.csv` as a failed experiment,
not counted as flow or clogging. A follow-up 35-disk pilot passed. Final cases
run for a constant **0.8 s** with snapshots every 0.0025 s and three seeds:

| Case | D/d | mu_pp / mu_wall | N | Funnel height [m] | Mean discharge fraction ± sample SD | Final observations |
| --- | --- | --- | --- | --- | --- | --- |
| narrow preset | 1.25 | 0.65 / 0.65 | 50 | 0.10 | 0 ± 0 | 3 persistent arches |
| outlet2 | 2 | 0.4 / 0.4 | 50 | 0.10 | 0.100 ± 0.072 | 3 persistent arches |
| baseline outlet3 | 3 | 0.4 / 0.4 | 50 | 0.10 | 0.753 ± 0.427 | 2 empty; 1 persistent arch |
| wide outlet7p5 | 7.5 | 0.4 / 0.4 | 50 | 0.10 | 1 ± 0 | 3 empty |
| low particle friction | 3 | 0.1 / 0.4 | 50 | 0.10 | 1 ± 0 | 3 empty |
| low wall friction | 3 | 0.4 / 0.1 | 50 | 0.10 | 1 ± 0 | 3 empty |
| steeper walls | 3 | 0.4 / 0.4 | 50 | 0.16 | 1 ± 0 | 3 empty |
| smaller fill | 3 | 0.4 / 0.4 | 35 | 0.10 | 1 ± 0 | 3 empty |

These are baseline/one-factor comparisons plus a coupled high-friction narrow
preset. Changing the outlet while holding outer width/funnel height fixed also
changes wall inclination. Actual angles from vertical are recorded in the CSV;
at D/d=3, increasing funnel height from 0.10 to 0.16 m changes the angle from
about 36.5° to 24.8°. Do not interpret this campaign as an isolated outlet-width
law, a full factorial study or a calibrated pharmaceutical material comparison.

All **24/24** repeated runs pass finite-state, overlap, wall-tunneling,
downstream-crossing and particle-accounting checks. Total sidewall center leak
samples: **0**. Maximum overlap across the campaign: **0.147455 R**, close to
the 0.15 R guard (7.37% of diameter). This soft-contact deformation is a material
model limitation, not evidence of negligible penetration. Higher stiffness and
material calibration remain future sensitivity work. Peak forces across the
campaign reach about **0.297 N**, and spin reaches about **284 rad/s**, all finite.

Wide-case emptying times are 0.172998–0.179892 s. The D/d=2 cases discharge
2, 4 and 9 of 50 grains before the observed persistent arch. Baseline D/d=3
discharges 50, 13 and 50 grains. Seed 33 has a crossing-free gap >=0.06 s,
subsequently resumes discharge and empties at 0.584305 s; its final state is
empty, with `interior_pause=True`. No permanent-clog label is assigned.
Successful sweep runtimes average approximately 37–58 s per case on this shared
node; runtime depends on load and contact count, and excludes rendering.

Representative wide and narrow complete runs were independently repeated;
their entire trajectory-array hashes match. See [replay.json](results/m2/replay.json).

## Timestep convergence

Same configuration/seed and initial-state hash, same physical duration, common
sampling grid, dt = 1e-5, 5e-6, 2.5e-6 s. Wide duration is 0.4 s; narrow duration
is 0.6 s. The two geometries are independent experiments, not paired with each
other. Pointwise RMSE uses particles active and above the outlet in both runs,
preventing frozen downstream removal positions from dominating the comparison.

| Case | dt [s] | Final count | Position RMSE / diameter vs dt/4 | Count-series RMSE [particles] | Max overlap/R | p95 overlap/R upper bound |
| --- | --- | --- | --- | --- | --- | --- |
| wide | 1e-5 | 50 | 0.101268 | 0.472866 | 0.082624 | 0.048 |
| wide | 5e-6 | 50 | 0.061325 | 0.315244 | 0.082846 | 0.048 |
| wide | 2.5e-6 | 50 | reference | reference | 0.082913 | 0.048 |
| narrow | 1e-5 | 0 | 0.200116 | 0 | 0.095309 | 0.017 |
| narrow | 5e-6 | 0 | 0.064817 | 0 | 0.095758 | 0.016 |
| narrow | 2.5e-6 | 0 | reference | reference | 0.095490 | 0.017 |

Discharge totals and overlap distributions are consistent here; individual
many-body trajectories are not demonstrated to be timestep-independent.
Differences shrink on refinement but the finest solution is still a numerical
reference, not exact truth. Narrow runs at 0.6 s remain unresolved transients
under the stationarity criterion; zero count alone is not called a stable arch.
Arch observations in the 0.8 s sweep must not be substituted into this table.

## Energy, force stability and CPU/CUDA

Controlled isolated elastic pair: gravity, damping and friction disabled,
duration 0.005 s, initial velocities ±0.1 m/s. Analytic contact duration and final
positions provide an independent reference. Total energy includes kinetic and
normal spring potential. The maximum energy excursion is numerical error:

| dt [s] | Max relative energy error | Final relative energy error | Final position error [m] |
| --- | --- | --- | --- |
| 1e-5 | 1.27746% | 0.0159136% | 2.52229e-8 |
| 5e-6 | 0.634738% | 0.000335552% | 1.28764e-9 |
| 2.5e-6 | 0.316388% | 0.000173060% | 4.44739e-10 |

The maximum error roughly halves with dt, consistent with first-order
integration. Very small final errors benefit from phase cancellation and must
not replace the maximum-in-contact error. Analytic free-fall position errors
are 9.81e-7, 4.905e-7 and 2.4525e-7 m at 0.02 s.

In the frictional/damped oblique pair, E_final/E_initial is 0.951113, 0.953478,
0.954687 on refinement. A nonzero loss persists toward the finer solution:
this is physical dissipation; the difference between refinements is numerical.
Do not label the full ~4.5% physical loss as solver error.

Hopper energy figures include translational/rotational kinetic energy,
gravity, normal and history springs, and energy advected through downstream
removal. Normal dashpot loss is integrated separately. Tangential contact work
is signed and includes spring exchange; it is not all irreversible frictional
loss. Gate removal does external work. History springs are sampled after the
preceding force update, and gate spring removal is approximate. Thus no exact
hopper energy-budget closure is claimed; instantaneous energy fluctuations
must not be interpreted as energy creation without this accounting.

Strict CPU/CUDA comparison: 400 identical oblique-contact steps (0.004 s), f64,
same initial states. Maximum absolute errors: position **0 m**, velocity
**0 m/s**, spin **3.55271e-15 rad/s**. Tolerances are 1e-10 m, 1e-8 m/s,
1e-6 rad/s, far below disk size and characteristic speeds. This verifies the
bounded contact benchmark, not long chaotic trajectories or a GPU speedup.

## Flow definitions and outputs

Flow rate counts unique first downward outlet crossings in 0.02 s bins. Completed
discharge requires all particles crossed and no active particles remain above
the outlet. Continuous flow requires recent repeated crossings without a long
interior gap. Intermittent flow requires a >=0.06 s gap followed by resumed
crossings. Persistent clogging is an **observation over the last 0.2 s** requiring
retained particles, low near-outlet speed (<0.003 m/s), and a spanning contact
chain at every sampled frame. Other states stay unresolved. No infinite-time
permanence claim is possible. Tests cover resumed flow, re-entry and emptying.

Near-outlet density is disk area assigned by center in the 0–0.02 m trapezoid,
divided by that trapezoid's area. Boundary circles are not clipped, so this is
an occupancy estimator, not exact packing fraction or published 3D solid fraction.
Velocity p50/p95 uses active particle/frame observations; this weighting is
explicitly different from a steady-state spatial profile. JSON includes density
and mean near-outlet speed series, bins/rates, flags and numerical diagnostics.

Figures: `results/m2/parameter_sweep.png`, `outlet_comparison.png`,
`overlap_rotation.png`, `hopper_energy.png`, `hopper_convergence.png`,
`controlled_convergence_energy.png`, `reference_qualitative.png`.
Solver animations and snapshot PNGs: `outputs/animations/m2_wide.*` and
`m2_arch.*`. README preview: `assets/m2_demo.gif`, 36 real-trajectory frames.
Velocity scales use SI and fixed active-speed q99 clipping, explicitly labeled.
GIF playback time differs from the simulation clock. No handcrafted motion.

## Exact reproduction

```bash
conda activate pharmaflow-2d
python -m pip install -e '.[acceleration,reference,test]'
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
python scripts/run_m2.py --suite configs/m2/pilot.json --output outputs/metrics/m2/pilot --jobs 4
# Expected nonzero exit: raised_fill fails its physical overlap guard; keep results.
python scripts/run_m2.py --suite configs/m2/pilot_fill.json --output outputs/metrics/m2/pilot_fill --jobs 1
python scripts/run_m2.py --suite configs/m2/sweep.json --output outputs/metrics/m2/sweep --jobs 4
python scripts/run_m2.py --suite configs/m2/convergence.json --output outputs/metrics/m2/convergence --jobs 3
python scripts/benchmark_m2.py --cuda
python scripts/download_reference.py --subset all
python scripts/audit_m2_reference.py
python scripts/replay_m2.py
python scripts/summarize_m2.py --render
```

The runner resumes only successful runs matching task/source signatures. Failed
cases retain errors and runtime. Aggregation separately rechecks empty-hopper
classification from saved frames; this refinement does not change any reported
cohort state. Raw data/trajectories, full animations and temporary logs are
ignored. Only compact summaries, PNGs and the explicitly allowed small README
GIF are versioned. Reference comparison limitations are detailed separately in
[M2_REFERENCE_COMPARISON.md](M2_REFERENCE_COMPARISON.md).
