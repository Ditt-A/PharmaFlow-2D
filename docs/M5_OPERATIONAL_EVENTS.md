# M5 operational event taxonomy

Version `operational-observation-v1` adds descriptive diagnostics to M3/M4B;
`first-persistent-arch-v1`, every historical label, split and evaluation remain
unchanged. There is no new training or policy selection.

## Definition fixed before the descriptive audit

The online monitor consumes the current saved timestamp, cumulative observed
outlet crossings and retained particle count. Sampling is 5 ms. It never reads
crossing-time arrays, event labels, final outcomes, onset or confirmation times.

Established flow requires a complete **100 ms post-gate window**, at least five
crossings in at least three distinct saved frames, and no gap greater than 40 ms
between crossing frames or either window edge. The interval is `(t−0.10,t]`.
The criterion must hold while grains remain. One prior crossing is insufficient.
At each crossing the monitor records whether this criterion holds. A subsequent
pause retains this flag from the most recent crossing; it does not infer flow
establishment from a distant successful period. These explicit operational
choices are descriptive, not experimentally calibrated industrial definitions.

| Category | Definition |
|---|---|
| Startup blockage | Original confirmed finite arch, zero observed crossings at its onset frame. |
| Post-discharge arch | Original confirmed finite arch, at least one observed crossing at onset. |
| Established-flow interruption | Subset of post-discharge arches: the most recent crossing strictly before onset met the established-flow criterion. |
| Temporary interruption | A pause is observed with retained grains for ≥50 ms since the last crossing, then a later observed crossing resumes discharge. |
| Completed discharge | No particle center remains in the hopper. Active particles falling below the outlet may still be rendered. |
| Unresolved/censored | Observation ends with retained grains and neither confirmed first arch nor completed discharge. Numerical failures are recorded separately. |

The current state is only `awaiting_first_discharge`, `discharge_observed_not_established`,
`established_flow_observed`, `pause_after_discharge`, `pause_after_established_flow`,
`no_particle_remaining` or `gate_closed`. A pause alone is never called a clog.
The pause becomes temporary only when resumption has actually been observed;
its notification is not backdated to the last crossing.

Future confirmation is used exclusively by `annotate_outcomes` and the separate
research view. Original arch confirmation requires the M3 persistent contact,
low-velocity, retained-grain and no-crossing conditions over 0.4 s; see
[M3 protocol](M3_LABELING_PROTOCOL.md). Persistence establishes a finite observed
arch, never indefinite clogging. Onset counts are sampled observations, not
sub-frame event ordering; `crossing_in_onset_frame` exposes ambiguous same-frame
ordering. The established-flow test uses the preceding saved frame.

## Observed counts

| Release | Runs | First arches | Startup | Post-discharge | Established-flow subset | Temporary episodes (runs) | Completed | Unresolved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M3 | 30 | 11 | 2 | 9 | 4 | 1 (1) | 19 | 0 |
| M4B | 48 | 31 | 17 | 14 | 3 | 6 (3) | 17 | 0 |
| Total | 78 | 42 | 19 | 23 | 7 | 7 (4) | 36 | 0 |

The M4B locked cohort contains **only two** established-flow arch events.
It cannot support a strong claim about prediction during established flow.
The seven temporary episodes span sampled crossing gaps of 55–95 ms and do not
imply that confirmed persistent arches broke. The representative resumed M3
trajectory subsequently empties; it is not an invented unclogging example.
Temporary episodes can coexist with a later first arch or completed discharge.
Startup/post-discharge partition the confirmed first arches; established-flow
counts are a subset, not a third disjoint arch category.

Full counts by configuration and packing are in
[counts_by_configuration_id.csv](results/m5/counts_by_configuration_id.csv),
[counts_by_packing_family.csv](results/m5/counts_by_packing_family.csv), and
[arch_taxonomy.csv](results/m5/arch_taxonomy.csv). Each arch record preserves
prior discharge count, onset-frame crossing flag, onset and confirmation.
Exact event counts by prior observed discharge count are in
[counts_by_prior_crossings.csv](results/m5/counts_by_prior_crossings.csv).
All 78 histories are in [operational_runs.csv](results/m5/operational_runs.csv).

## Reproduction

```bash
conda activate pharmaflow-2d
python scripts/audit_m5.py
python scripts/export_m5.py
python -m pytest -q
```

Auditing reads local historical NPZ, cached predictions and frozen models; it
does not solve or train. It checks 42 original rule/model replay combinations
(21 validation/locked runs × two comparators), with maximum score difference
**0.0** and identical emitted warning timestamps. Other historical runs are
retrospective inference, including training runs, not new generalization tests.
