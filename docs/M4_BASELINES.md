# M4A baseline protocol

This milestone asks whether current disk dynamics improve finite-arch warnings
over static physical parameters in the frozen M3 cohort. It is baseline research
on an uncalibrated 2D disk solver, not pharmaceutical deployment validation.
M3 commit `a3e28072dcd738cb70f99a38d2c3d2c0f162114c`, all raw trajectories,
labels and split assignments are preserved. No new DEM simulations are launched.

## Data contract

The preflight verifies 30 runs, 11 first-event runs, 9030 feature rows, 18060 label
rows, both horizons, every processed manifest checksum and the published split.
The M4 loader additionally verifies all 30 raw trajectory SHA256 values. An
all-file processed-directory snapshot is rechecked after evaluation. Existing
M1-M3 tests run before development and again with the new scientific tests.

Each horizon is joined separately on exact `(run_id, frame_index, time_s)` with
a one-to-one outer merge and exact configuration/group consistency checks.
No timestamp rounding or approximate matching is allowed. Only `eligible`
pre-onset rows with observed binary targets enter classification. Each horizon
has 1676 rows: 220 positives at H=0.10s, 110 at H=0.05s. Excluded post-onset,
empty, gate-closed and censored rows never become negatives. Natural censoring
is absent in this release, so censored-population performance is unknown.

Only dictionary entries with role `predictor` can enter a pipeline. IDs, seeds,
hashes, frame indices, status, final outcomes, onset and confirmation times are
excluded. `time_s` in D/E is explicitly an observable elapsed clock, not a
unique-key encoding; ablation F removes it. Event metadata is used solely for
retrospective evaluation, not warning generation or preprocessing.

## Prespecified feature ablations

Exact ordered lists are preserved in [feature_sets.json](results/m4/feature_sets.json)
and every candidate in [frozen_protocol.json](results/m4/frozen_protocol.json).

| Set | Predictors | Definition |
| --- | ---: | --- |
| A_static | 9 | Geometry, friction, fill, particle radius, kn/kt, packing family |
| B_current | 17 | Current particle counts, occupancy estimator, speed/velocity, contact summaries and missing-region flags |
| C_temporal | 17 | Trailing 50/100ms flow/velocity/occupancy histories, interruption/history flags, since-crossing plus current local/remaining counts and missing-region flags |
| D_full | 41 | All dictionary predictors |
| E_without_arch | 36 | Full minus instantaneous spanning path, stationary fraction, maximum local speed and two local coordination summaries |
| F_without_time_discharge | 33 | Full minus elapsed clock, cumulative discharge, global active/remaining counts, ever-crossed flag, since-crossing and both history-coverage clocks |

E removes the most direct instantaneous structure/kinematic proxies for the
event definition, including max speed. Mean velocities still describe genuine
observable slowing and may correlate strongly with future labels. F conservatively
removes count/clock proxies while retaining local occupancy and trailing flux.
Neither ablation establishes causality. Occupancy remains an approximate
center-assigned area estimator, not an exact packing fraction.

## Models, weights and preprocessing

One fixed configuration per model, six ablations, two horizons and two benchmarks
gives 72 ML candidates, plus eight constant/rule baselines: 80 fitted final
artifacts and 240 grouped-fold fits. There is no hyperparameter search.

- Constant score: run-balanced training prevalence, recomputed inside each fold.
- Current-observation rule: `0.45*stationary_fraction + 0.35*spanning_arch_now +
  0.20*exp(-near_speed_mean/0.02)` when local and remaining counts are >=2,
  otherwise zero. Weights and speed scale are fixed before evaluation. This
  is a monotone physics heuristic, not a calibrated probability.
- Logistic regression: L2, C=1, liblinear, max_iter=2000.
- Random forest: 120 trees, depth<=4, leaf>=8, sqrt feature sampling.
- XGBoost CPU: 100 trees, depth<=2, learning rate .05, child weight 5,
  L2=5, no row/column subsampling, histogram algorithm.

Seed 20261117 and two estimator/BLAS threads are fixed. Numeric StandardScaler
and packing OneHotEncoder are fitted on training rows within each fold, then
refitted only on the complete official training split. Unknown held-out packing
categories are ignored by the train-fitted encoder. No feature is normalized
using full-run future information. No learned imputation is needed: M3 features
are complete and its fixed empty-region representations are preserved.

Each run receives equal total **base** weight, independent of its eligible frame
count. Positive/negative multipliers balance the run-weighted training classes;
these are recomputed using only each fit fold. After class balancing, run totals
can differ with within-run class composition. Adjacent frames remain dependent;
weights do not create independent observations. Class weighting changes the
effective class prior, so warning scores are not asserted to be calibrated
probabilities. Brier/reliability plots diagnose this; no posthoc calibrator is
fitted on validation/test. Raw-frame and equal-run AP/Brier are both saved.

The CPU-only wheel avoids installing CUDA/NCCL dependencies, as described in
the [official XGBoost installation guide](https://xgboost.readthedocs.io/en/stable/install.html).
Recorded versions are scikit-learn 1.6.1, xgboost-cpu 2.1.4, joblib 1.4.2,
pandas 2.3.3 and pyarrow 19.0.1. Taichi remains 1.7.3; no torch is installed.

## Grouping and selection freeze

Published run-grouped splits remain 18/6/6 runs (7/2/2 events); strict
configuration holdouts remain 20/5/5 runs (9/1/1 events, 8/2/2 physical groups).
Training-only three-fold StratifiedGroupKFold uses run or canonical physical
group respectively. No group crosses a fit/OOF partition. Preprocessing and
weights are fitted independently in each fold. Both benchmarks/horizons are
trained and frozen before any held-out metric is evaluated.

For each candidate, threshold search uses only coherent per-run OOF scores.
Grid: .05 through .95 in steps .05 plus 1.01 (no warnings). Fixed two-frame
confirmation, 0.05s cooldown and 0.02s minimum useful lead apply. The utility is:

`useful_event_recall - 0.25*false_alerts_per_non_event_run - 0.02*false_alerts_per_eligible_second`.

This deliberately rewards usable lead while penalizing false warnings, including
too-early alerts on event runs. Threshold ties choose the higher threshold.
Candidate ties use equal-run OOF AP, fewer features, model simplicity, then a
deterministic identifier. Constants/rules can win if ML offers no benefit.
Selection is exploratory on this tiny training cohort, and OOF selection scores
are optimistic estimates of the chosen candidate, not held-out evidence.

The freeze contains exact feature lists, model parameters, OOF fold memberships,
data/source hashes, artifact checksums, thresholds and selected candidate IDs.
Training refuses to overwrite it. Evaluation refuses changed inputs/source/models
and refuses to overwrite a completed evaluation. Validation is descriptive and
does not alter the selected model or policy. All other test ablations were
prespecified; they are not used to pick a new test winner.

## Reproduce without new simulations

From the repository root in the existing environment, with the frozen M3 local
data present:

```bash
conda activate pharmaflow-2d
python -m pip install -e '.[ml,test]'
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
python scripts/train_m4.py
python scripts/evaluate_m4.py
python scripts/analyze_m4_errors.py
python scripts/audit_m4.py
# After an existing completed evaluation, regenerate only diagnostics:
python scripts/evaluate_m4.py --plots-only
```

For independent replay, use new `--output outputs/metrics/m4_replay`,
`--models outputs/checkpoints/m4_replay` at training, and matching `--output`
plus `--report outputs/metrics/m4_replay/report` at evaluation/audit. Do not
delete a completed freeze or rebuild M3 merely to rerun M4. Paths, artifact
digests and runtime fields differ between replays; deterministic predictions
and frozen choices should agree for identical code/configuration/packages.

Large models, OOF/held-out predictions and full per-run tables stay locally in
`outputs/checkpoints/m4/` and `outputs/metrics/m4/`. Only compact metrics,
protocol manifests and selected plots under `docs/results/m4/` enter Git.
