# M3 quality and release report

Evaluated on node680 in the existing `pharmaflow-2d` environment. No model is
trained. Raw inputs and processed tables remain local; this report, selected
figures and lightweight checksum/split manifests are versioned.

## Audit outcome

**36/36 planned solver attempts succeeded**: six numerical-preparation cases
and 30 independent dataset runs. The cohort contains 11 confirmed first events
and 19 completed-discharge runs. Failures and natural right-censored runs are
both **zero**; this is a measured result, not a silent exclusion. The empty
failure directory is part of the schema, and a deliberate invalid-timestep unit
test verifies failures are retained there with configurations and reasons.

**64 tests pass**, including all 41 M1/M2 tests, strict Taichi CPU/CUDA parity,
packing reproducibility, angle invariance, causal-prefix checks, event/horizon
tests, contact-rich continuation, empty-state fast-forwarding, budget rejection,
Parquet roundtrip, duplicate detection and cache tampering. One upstream Taichi
locale deprecation warning remains. `pip check` passes. Taichi is still 1.7.3.

The full-data audit checks raw/processed SHA256, embedded run identity/source,
initial particle/mass/radius consistency, monotone removal, discharge-count
consistency with crossing times, particle accounting, overlap and leakage,
uniform timestamps, finite arrays, feature completeness, label reconstruction,
future-prefix invariance and split membership.

| Check | Result |
| --- | --- |
| Valid dataset runs | 30/30 |
| Sidewall leak samples | 0 |
| Maximum normalized overlap | 0.08341397 R; limit unchanged at 0.15 R |
| Nonfinite or missing feature values | 0 |
| Duplicate trajectory fingerprints | 0 |
| Identical initial-state reuse across configurations | 0 |
| Timestamp/particle/count inconsistencies | 0 |
| Causal-prefix feature tests | 30/30 |
| Real event-prefix censoring tests | 11/11 |
| Natural right-censored runs / label rows | 0 / 0 |
| Permanent-clogging claims | None |

Both cached campaign commands were rerun: all 30 trajectory checksums and file
modification times remained unchanged, with **zero additional solver attempts**.
All five Parquet tables rebuilt bitwise identically. See
[resume_and_rebuild.json](results/m3/resume_and_rebuild.json).

## Event and class coverage

Default P=0.4 s gives 11 first events; P=0.2 and P=0.6 s also give 11 in this
cohort. Per-run onset/confirmation values and sensitivity tables are preserved.
No first-event target is assigned at or after onset. Positives have supported
lead times from 0.005 s to the requested horizon, including full 0.05 and 0.10 s
coverage for every event. A future-confirmed label is never reused as a feature.

For H=0.05 s: **110 positive / 1566 negative**, 6.56% positive among 1676 eligible
rows. For H=0.10 s: **220 / 1456**, 13.13% positive. Across both horizons,
8932 rows are excluded as empty, 5176 as post-onset, and 600 as gate-closed.
These are eligibility exclusions, not hidden negatives or natural censoring.
Adjacent frames and the two horizons are strongly dependent: effective event
sample size is 11, not the 330 positive rows.

Because the final runs all resolve under the finite protocol, naturally censored
examples are absent. QA therefore truncates each real event trajectory before
its confirmation: targets become null/right-censored while prefix features stay
identical. These administrative views are QA-only, not extra dataset runs or
training examples. The absence of naturally censored runs remains a coverage
limitation, despite the censoring code being tested.

## Split independence

| Split | Run-grouped: runs / event runs | Config-holdout: runs / event runs | Held-out physical groups |
| --- | --- | --- | --- |
| train | 18 / 7 | 20 / 9 | 8 |
| validation | 6 / 2 | 5 / 1 | 2 |
| test | 6 / 2 | 5 / 1 | 2 |

No run crosses splits. In the stricter benchmark no configuration ID or
canonical physical group crosses splits, including all seeds and packings.
Target-derived outcome strata only allocate complete groups; they do not fit
or normalize features. No preprocessing is learned from any split.

Combined-horizon eligible row counts are:

| Benchmark | Train positive / negative | Validation positive / negative | Test positive / negative |
| --- | --- | --- | --- |
| run-grouped | 210 / 1748 | 60 / 616 | 60 / 658 |
| configuration-holdout | 270 / 2262 | 30 / 454 | 30 / 306 |

The strict validation/test sets each have only one event-bearing run. This is
adequate to validate storage/grouping, not to establish predictive performance.
Do not tune a future model against this tiny test set or claim robust event F1.

## Trivial variables and selection effects

Descriptive Pearson correlations with the binary target, pooled across eligible
frames/horizons, are approximately D/d **-0.204**, discharge fraction **-0.171**,
initial count **+0.042**, and elapsed time **+0.212**. These are dependent-frame
descriptions, not significance tests or model scores. Run-level event fractions
by outlet and class counts are also exported in the machine-readable report.

The pilot correctly exposed strong outlet dependence and only two positive
physical groups. Its review was frozen before adding 12 transition runs. The
final cohort has mixed outcomes in several transition configurations and both
classes in all final benchmark splits. Still, this adaptive small cohort is
biased toward the inspected transition region, not an unbiased design-space
sample. Packing family/seed are incompletely crossed, some angle/fill presets
vary together, and seeds are paired across geometry comparisons. Initial energy
and density differ across packing families. These effects must be considered
when evaluating future models.

## Figures and reproducible evidence

All visualized particles/flow histories come from saved DEM trajectories:

- [stiffness_sensitivity.png](results/m3/stiffness_sensitivity.png): overlap,
  discharge, mechanical/advected energy and runtime at three stiffness levels.
- [parameter_coverage.png](results/m3/parameter_coverage.png): geometry, friction,
  fill, packing family and observed first-event coverage.
- [events_and_balance.png](results/m3/events_and_balance.png): onset versus
  confirmation, persistence sensitivity and horizon class imbalance.
- [flow_histories.png](results/m3/flow_histories.png): cumulative crossings and
  flux from representative transition runs.
- [onset_timelines.png](results/m3/onset_timelines.png): separate onset and
  future confirmation markers for every run.
- [particle_event_sequence.png](results/m3/particle_event_sequence.png): genuine
  pre-onset, onset and confirmation particle snapshots colored by SI speed.

Reproduce:

```bash
python scripts/build_m3_dataset.py
python scripts/audit_m3.py
python scripts/plot_m3.py
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

Machine-readable results are [summary.json](results/m3/summary.json),
[quality_report.json](results/m3/quality_report.json), [run_summary.csv](results/m3/run_summary.csv)
and the neighboring manifests/dictionary. No raw NPZ, Parquet dataset or large
temporary output is committed.

## Scientific boundary

This is an uncalibrated dry 2D disk dataset with a specified contact law, fixed
particle size, assumed thickness and a small finite fill. It omits 3D front/back
walls, material calibration, cohesion and industrial powder effects. Smaller
overlap improves this campaign's numerical behavior but does not make the flow
law stiffness-independent. Finite persistence is not indefinite clogging.
First-event labels intentionally exclude later event cycles. Natural censoring
and broader independent packing/parameter coverage need another explicit budget.
The unresolved published-data alignment/units from M2 are unchanged. M3 supplies
auditable inputs for future research, not predictive, calibrated or industrial
performance claims.
