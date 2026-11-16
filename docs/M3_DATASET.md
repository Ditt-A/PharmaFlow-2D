# M3 synthetic DEM dataset

M3 provides a small, reproducible dataset for future first-arch early-warning
research. No classifier, neural network, optimizer or recommendation engine
has been trained. M1/M2 reports and datasets are preserved. Public-paper
calibration remains unresolved; these are strict 2D dry disks, not industrial
pharmaceutical validation.

## Numerical preparation

Six paired sensitivity runs precede campaign generation: D/d=2 and 3, N=50,
seed 101, identical initial-state hashes within each geometry, wall angle
fixed at 35° from vertical, duration 0.8 s. Normal stiffness is 1000, 2000 and
4000 N/m. kt/kn remains 0.25 and damping coefficients scale with sqrt(kn),
preserving dimensionless damping. The original overlap guard remains **0.15 R**.

| D/d | kn [N/m] | dt [s] | Peak overlap/R | p95 overlap/R upper bound | Discharged | Runtime [s] |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | 1000 | 1e-5 | 0.135875 | 0.029 | 2 | 55.1 |
| 2 | 2000 | 5e-6 | 0.075367 | 0.013 | 8 | 108.1 |
| 2 | 4000 | 5e-6 | 0.042788 | 0.008 | 2 | 117.1 |
| 3 | 1000 | 1e-5 | 0.145278 | 0.040 | 50 | 42.8 |
| 3 | 2000 | 5e-6 | 0.085663 | 0.022 | 50 | 83.7 |
| 3 | 4000 | 5e-6 | 0.049129 | 0.014 | 50 | 86.7 |

Energy, normal-dashpot work, discharge, finite-window arch observations and
runtime are exported in [stiffness.csv](results/m3/stiffness.csv) and
[stiffness_sensitivity.png](results/m3/stiffness_sensitivity.png). Energy includes
gravity, spin, contact springs and advected energy; the approximate history/gate
energy limitations from M2 still apply. No exact hopper energy closure is claimed.

Selection: **kn=4000 N/m, kt=1000 N/m, gamma_n=0.30 kg/s, gamma_t=0.06 kg/s,
dt=5e-6 s**. This markedly reduces overlap at nearly the 2000 N/m runtime using
the same dt, and retains roughly 125 steps per normal pair contact. The guard
is respected without relaxation. Narrow-case discharge is nonmonotonic with
stiffness, so this is a numerical-softness choice, not stiffness-converged flow
or calibrated material data. All values/rationale are in
`configs/m3/numerical_selection.json`.

## Controlled geometry and independent initial states

R=0.002 m, density=2500 kg/m³, assumed thickness=0.01 m and g=9.81 m/s².
Outer width is 0.16 m. For outlet width o and requested angle theta from vertical,
`funnel_height = (outer_width-o)/(2*tan(theta))`. Thus changing D/d in an
outlet-only comparison cannot silently change inclination. The angle formula is
unit-tested at several outlet widths; actual geometry is recorded in every run.

Three reproducible packing families are used:

- `staggered`: the M1/M2 seeded, nonoverlapping fill;
- `hexagonal`: triangular row spacing, independent row phases and shuffled
  row truncation order, changing structure rather than tiny point jitter;
- `random_sequential`: random positions within a prescribed low-height region,
  accepted only with wall clearance and center separation >=2.05 R.

Packing seeds and full initial-state hashes are retained. Failure to fit a
packing is a recorded failed attempt, not silent reseeding. Families have
different density/initial energy; they are deliberately not equivalent settled
random packings. Seeds are paired across parameter comparisons, and packing
family/seed are not fully factorial. Do not treat all parameter draws as IID
material experiments. No identical initial states or trajectories were found.

## Budget, pilot review and final cohort

The explicit ceiling in `configs/m3/budget.json` is **36 distinct solver
attempts**: 6 preparation, 18 pilot and at most 12 adaptive production. Maximum
planned physical time is 51.3 s including potential continuations; actual
physical time is 49.8 s. Four CPU workers are used, with no sudo or CUDA/PyTorch
installation. Taichi stays pinned to **1.7.3**. PyArrow 19.0.1 is added only to
the existing `pharmaflow-2d` environment for Parquet storage.

The pilot covers D/d=2, 2.5, 3, 3.5, 4, 6 at fixed 35°, N=40 and friction
0.4/0.4, with three seed/packing replicates per configuration. **18/18** runs
are valid; five first events occur. D/d=2 has 3/3 events; D/d=2.5 has 2/3;
the larger outlets all empty. Both requested horizons have complete positive
lead-time coverage. Pilot snapshots of QA, manifests and splits were frozen
before production, including the lack of a positive configuration-holdout
validation group at that stage.

Review therefore concentrates the remaining **12 attempts** on D/d=2.25–3.0,
varying particle/wall friction, angle and fill. See `pilot_review.json` and
`production.json` under `configs/m3/`. Some angle/fill cases are coupled presets,
not causal one-factor estimates. Generation stops at the declared budget.

Final ranges: D/d **2–6**, mu_pp and mu_wall **0.15–0.65**, wall angle
**28–42°**, **30–50** disks, seeds **101, 202, 303, 404, 505**, and three packing
families. There are **12 physical configurations**, not merely obvious clogged
and flowing anchors. Several transition configurations contain both outcomes.

Every dataset run observes 1.5 s, sampled every 0.005 s. Three prescribed pilot
random-packing cases may continue in the same DEM instance to 2.0 s if still
ambiguous at 1.5 s; none needs continuation in this cohort. A contact-rich test
proves continuation agrees with uninterrupted integration, including spring
history and spin. Once every particle is removed, only the unchanged absorbing
empty state is fast-forwarded; this optimization is tested against normal DEM.

## Dataset statistics

- **36 attempted / 36 successful / 0 failed** including preparation.
- **30 independent dataset runs**: 18 pilot + 12 production; all numerically valid.
- **11 confirmed first events**, 19 completed-discharge runs; no natural
  right-censored runs. Censoring is nevertheless tested on toy and real prefixes.
- **9,030 feature rows**, 45 columns including four identifiers and 41 predictors.
- **18,060 time/horizon label rows**. Of these, 3,352 are eligible across both
  horizons; empty, post-onset and gate-closed rows have nullable targets.

| H [s] | Positive | Negative | Positive fraction among eligible | Naturally censored |
| --- | --- | --- | --- | --- |
| 0.05 | 110 | 1566 | 6.56% | 0 |
| 0.10 | 220 | 1456 | 13.13% | 0 |

Maximum dataset overlap is **0.083414 R**, below the unchanged 0.15 R guard.
All runs conserve particles and pass wall-leak, finite-state and timestamp
checks. P=0.2/0.4/0.6 s sensitivity gives 11 confirmed first events in each case.
These event counts are finite-protocol outcomes, not permanent clogging claims.
See [M3_LABELING_PROTOCOL.md](M3_LABELING_PROTOCOL.md) for exact target rules.

## Storage and provenance

Default paths are relative to `/home/adityaakbar/adit/PharmaFlow-2D`:

```text
data/simulated/m3/
  pilot/<run_id>/trajectory.npz, trajectory.json, run.json
  production/<run_id>/trajectory.npz, trajectory.json, run.json
  manifests/pilot_campaign.json, production_campaign.json
  failures/<run_id>.json                     # empty in this successful cohort
data/processed/m3/
  run_metadata.parquet
  temporal_features.parquet
  event_labels.parquet
  events.parquet
  persistence_sensitivity.parquet
  feature_dictionary.json
  split_manifest.json
  dataset_manifest.json
  quality_report.json
```

NPZ has no pickle. It extends M1 positions, velocities, rotation, active masks,
crossing times and timestamps with observable frame statistics, instantaneous
graphs and integration-interval common-contact graphs. NaN crossing time means
that particle has not discharged, not numerical failure. Run JSON includes
physical/numerical configuration, seed, unique packing ID, solver version/source
hash, observation duration, runtime, diagnostics and file SHA256. Parquet metadata
preserves identity and parameters, including planned/maximum/actual durations.
Labels and features have separate provenance and a processing source hash.

Raw campaign files total about **7.8 MB**; processed tables/manifests about
**0.7 MB**. SHA256 checks protect raw NPZ and processed artifacts. Completed and
failed runs are resumable by immutable task signature; a checksum mismatch or
changed plan is an error, not an overwrite. In-flight process restart is at
run granularity, not a disk-restored integrator checkpoint. Failures retain
configuration, seed, source, reason and runtime separately. No failed attempt
is automatically retried or relabeled as a negative.

## Grouped splits

Seed 20261117 gives deterministic outcome-stratified groups, with approximate
60/20/20 allocation. Entire runs stay together. The stricter benchmark groups
canonical physical parameters, including geometry, friction and particle count,
across every seed/packing replicate. Configuration IDs and canonical group IDs
are both checked for leakage.

| Benchmark | Train runs / event runs | Validation runs / event runs | Test runs / event runs |
| --- | --- | --- | --- |
| run_grouped | 18 / 7 | 6 / 2 | 6 / 2 |
| configuration_holdout | 20 / 9 | 5 / 1 | 5 / 1 |

Configuration-holdout coverage is **8 / 2 / 2** distinct physical groups.
Full per-split class/censor counts and group assignments are in the split
manifest. Stratification uses outcomes only to allocate groups; it does not
fit feature transformations. Test/validation event counts remain very small.
Do not interpret this release as a statistically strong model benchmark.

## Reproduction and cost

```bash
conda activate pharmaflow-2d
python -m pip install -e '.[dataset,acceleration,test]'
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
python scripts/run_m2.py --suite configs/m3/stiffness.json --output outputs/metrics/m3/stiffness --jobs 3
python scripts/run_m3.py --plan configs/m3/pilot.json --jobs 4
# Inspect pilot QA/review before starting the documented 12-run expansion.
python scripts/run_m3.py --plan configs/m3/production.json --jobs 4
python scripts/build_m3_dataset.py
python scripts/audit_m3.py
python scripts/plot_m3.py
```

To reproduce the pilot review independently, build/audit after the pilot and
before running production; preserve those JSON outputs separately. On an
existing completed release, do not rebuild a pilot-only view by deleting runs.
Re-running both generation commands verifies cached checksums and does not
launch more solver attempts. Parquet rebuilding was checked bitwise identical.

Measured total: **3842.93 summed worker-wall seconds (64.05 worker-minutes)**,
including six stiffness runs. Pilot/production elapsed estimates from recorded
finishes/runtimes are about **7.11 / 8.08 min** at four workers, excluding coding,
QA and plotting; stiffness preparation adds its separately recorded cost.
This is not billed GPU time or a speedup claim. New campaign cost depends on
arch duration, particle count, packing and machine load; another campaign
requires an explicit revised budget.

Only source, plans, compact manifests/reports, CSV summaries and small PNGs
are pushed to GitHub. Raw trajectories, Parquet datasets and full logs stay
on node680. M4 preprocessing/training requires a separate task and must honor
the feature whitelist and frozen split groups.
