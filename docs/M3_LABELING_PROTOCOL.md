# M3 first-event labeling protocol

Protocol: `first-persistent-arch-v1`. This is an operational, finite-duration
synthetic event definition, not proof of permanent or industrial clogging.
It does not use the unresolved published Numbers data as trajectories.

## Observable structure and timing

The near-outlet region is 0 <= y < 0.025 m. At each DEM force evaluation the
monitor forms an undirected graph of actual positive-overlap particle contacts
in that region and contacts with each sloped wall. The two final graph nodes
represent the walls. A spanning contact path connects them through particles.
The gate segment is never an arch-support node.

The monitor intersects these graphs over **every integration step** between
saved frames. It also records the maximum near-outlet speed and minimum retained
particle count over each interval. Thus a contact interruption between two
stored frames is not silently ignored. Snapshot graphs remain separately
available as instantaneous observations. Tests verify monitoring does not
change the DEM forces, positions or spins.

A candidate starts at a saved time at least 0.02 s after gate opening. It needs
at least two retained particles, a spanning graph, and maximum near-outlet speed
<=0.003 m/s. It is confirmed only if, throughout the next **P=0.4 s**:

- unique outlet-crossing count does not change;
- retained particle count remains at least two;
- near-outlet speed stays below the threshold at all monitored steps;
- the intersection of contact graphs still contains a wall-to-wall path.

This is stricter than a path that keeps rewiring: one shared spanning subgraph
must persist. All graphs/velocity checks include the saved endpoint as well as
the intervening integration steps. It is deliberately conservative; rapid
rearrangement or an arch above the selected region can remain unconfirmed.

**Onset time** is the first candidate start supported by a complete future
persistence window. **Confirmation time** is the first saved frame at or after
onset + P. They are distinct, and onset has 0.005 s reporting resolution. Onset
is not asserted to be the exact microscopic instant of arch nucleation.

Only the first confirmed onset per independent run is a prediction target.
The end of its supported interval and any subsequent resumed discharge are
recorded. A confirmed finite arch that later opens is still a confirmed
finite-duration event; it is never labeled permanent. Later contact-path
rewiring is not counted as an additional first event.

Sensitivity is evaluated with P=0.2, 0.4, 0.6 s. All three definitions produce
11 first-event runs in this cohort; this does not establish universality of
the thresholds. See the per-run sensitivity table for onset values.

## Prediction targets

For each time t and H in {0.05, 0.10} s, the target is:

`1 if first confirmed onset is in (t, t+H], else 0 if enough future is observed`.

Examples at or after onset are excluded from first-onset prediction, even if
the hopper later resumes flow. An already-clogged state is never turned into
a positive early-warning example. Empty states are separately excluded. Gate-
closed examples are excluded as `pre_release`.

A known confirmed onset within the horizon supports a positive immediately.
For a negative, observation must extend through **t+H+P**, because an onset
near the horizon's end needs its own future confirmation window. Insufficient
observation produces a nullable target and `right_censored`, not zero. No
exception is inferred from a quiet interval alone.

| label_status | Target | Meaning |
| --- | --- | --- |
| eligible | 0 or 1 | Supported pre-onset prediction example |
| pre_release | null | Gate still closed |
| post_onset | null | First event has already begun |
| empty | null | No retained grains above outlet |
| right_censored | null | Insufficient horizon plus confirmation observation |
| numerical_failure | null | Invalid physics; failed runs are catalogued separately |

The label table stores run/configuration identity, frame/time, H, nullable Int8
target, label status, exclusion/censoring reason, onset and confirmation times,
P and protocol version. A dataset-level processing source hash and file checksums
complete the provenance. These future-derived fields belong only in labels
or outcome metadata, never the predictor table.

## Causal predictors

`temporal_features.parquet` contains instantaneous and trailing-only quantities.
It reads saved observations at or before t, never the event list, confirmation
time, final run outcome or future crossing timestamps. Flow features use the
observed cumulative count, and the last observed crossing time is resolved to
the sample grid. Trailing windows are 0.05 and 0.10 s, without centered rolling
means or backward filling. Partial histories include explicit coverage flags.

Instantaneous spanning paths are valid observable inputs; future persistence
is not. Scalar speed percentiles are across currently active particles, not
over the complete trajectory. Velocity units remain m/s. Color scales in
posthoc figures may use a complete-run q99; that visualization scale is never
used to transform the features.

Near-outlet occupancy is center-assigned disk area divided by the geometric
trapezoid area, not exact clipped disk coverage, exact packing or 3D solid
fraction. Empty-region statistics are zero with `near_missing`/`active_missing`
flags. This is a fixed representation, not learned imputation. Static parameters
are mandatory and never statistically imputed. The feature dictionary records
units, meaning, windows, availability, role and missing-data policy.

Run/configuration IDs, physical-group IDs and frame indices are join/group keys,
not predictors. Seeds and unique packing hashes remain metadata. The packing
family is an observable initial-condition category. No normalization, encoder,
learned imputation or model is fitted. M4 must fit preprocessing on training
groups only and select one H or an explicit multiple-horizon target scheme.

## Censoring and flow interpretation

Final flow status and first-event labels answer different questions. Continuous
or intermittent flow can be right-censored if grains remain without a confirmed
event at the observation limit. An empty hopper is completed discharge, including
when it had an earlier interruption. A terminal persistent arch is finite-window
evidence only. Numerical failure is neither a flow class nor an event negative.

This cohort has **zero naturally right-censored runs or label rows**: all runs
either empty or contain a confirmed first event before 1.5 s. Do not infer
performance on censored populations from that fact. To verify the pipeline,
QA truncates each of 11 real event trajectories halfway between onset and
confirmation. Each becomes correctly censored, while prefix features remain
identical. Those truncated views are **not added to training**, do not count
as independent runs, and cannot cross splits.

Toy-trajectory tests independently cover stable arches, resumed flow, temporary
pauses, no-contact quiet intervals, empty hoppers, truncated observation,
between-frame contact loss, horizon boundaries and post-onset exclusion.
Contact-rich DEM continuation is compared with uninterrupted integration so
continuation cannot reset spring history or spin.

Reproduce labels and QA:

```bash
python scripts/build_m3_dataset.py
python scripts/audit_m3.py
```

Use only rows with `label_status == 'eligible'` for supervised first-onset
prediction in a later milestone. The 330 positive rows across both horizons
represent **11 independent events**, not 330 independent event observations.
