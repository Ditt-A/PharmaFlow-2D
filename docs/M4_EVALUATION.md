# M4A scientific evaluation

All candidates, feature lists, thresholds and selections were frozen together
before validation/test evaluation. No test metric changes a choice. Exact tables
are [metrics.csv](results/m4/metrics.csv), [selected_metrics.csv](results/m4/selected_metrics.csv),
[selected_event_runs.csv](results/m4/selected_event_runs.csv), and
[training-only selection evidence](results/m4/oof_selection.csv).

## What a warning means

A warning fires on the **second consecutive high-scoring frame**. Its timestamp
is that second frame, not the first frame retrospectively. Sampling is 0.005s;
a missing interval resets the counter. Continuous high scores produce one
episode. Re-arming requires a low score, and successive episode starts must be
at least 0.05s apart. This prevents prolonged high probabilities from becoming
many supposedly independent alerts.

An episode is valid for event i only if `0 < onset_i - alert_time <= H`.
The first such episode gives the warning timestamp/lead. An alert at or after
onset never counts. A valid alert with lead >=0.02s is additionally a **useful**
advance warning; smaller leads are imminent detection. Event recall is reported
both without this minimum and with it. Missed-event counts use both definitions.

Earlier alerts outside the prediction horizon are false, even on a run that
eventually forms an arch. A latched too-early alert is not retrospectively moved
into the horizon. Additional valid episodes are recorded as redundant rather
than independent event successes. All episodes on non-event runs are false.
An empty hopper is never an event. We predict M3's first **0.4s-confirmed finite
arch**, not indefinite clogging; onset and future confirmation are distinct.

False-alert burden includes total false episodes, false episodes per independent
non-event run, and all false episodes divided by **eligible exposure seconds**.
Exposure is eligible-frame count times 0.005s (grid-cell convention), excluding
gate-closed, empty, post-onset and insufficient-future rows. It is neither the
full 45 simulated seconds nor deployment operating time. This eligibility-
conditioned first-event evaluation is retrospective; it does not demonstrate
an online system that knows when an unknown event has already started.

## Descriptive frames and uncertainty

Report AP (stepwise average precision, not trapezoidal PR integration), ROC-AUC
when both classes exist, precision/recall/F1, Brier, confusion counts and positive
prevalence. Scores thresholded at the frozen value define frame confusion;
episode debounce/cooldown define event results. Adjacent frames and overlapping
horizons are dependent, so these are descriptions, not thousands of independent
samples. Equal-run AP/Brier supplement raw frame metrics.

The selected candidates receive 300 cluster bootstrap replicates per split:
whole runs for run-grouped, whole physical configurations for strict holdout.
No individual frames are resampled independently. Undefined metrics from
single-class or event-free resamples are omitted **with defined-replicate counts**
in [uncertainty.json](results/m4/uncertainty.json). Percentile intervals are
descriptive. With one held-out event or two configurations, event-recall intervals
can degenerate at 0 or 1 conditionally; they must not be interpreted as precise
population confidence. Eleven total events, paired seeds and adaptive M3
configuration selection further limit independence and generalization.

## Frozen selections

| Benchmark | H [s] | Selected candidate | Threshold | Training OOF useful recall | Training OOF equal-run AP |
| --- | ---: | --- | ---: | ---: | ---: |
| Run-grouped | .10 | B_current Random Forest | .90 | 5/7 | .7901 |
| Run-grouped | .05 | D_full XGBoost | .70 | 4/7 | .6061 |
| Configuration-holdout | .10 | B_current XGBoost | .60 | 8/9 | .6618 |
| Configuration-holdout | .05 | Current-observation rule | .85 | 6/9 | .5867 |

These are training selection results and are not claims of held-out performance.
The rule's selection at H=.05 is retained even though it is not an ML model.
The feature/model freeze SHA256 is
`3fdbdc3ea12e92bb0c0b8aaef12d988308ce694fb343bf6f150aab885773ecc7`.

## Held-out frame results

These are the frozen OOF-selected candidates, not candidates selected for the
largest validation/test AP. All other prespecified model/feature results remain
in metrics.csv. Prevalence and frame denominators must accompany the scores.

| Benchmark / H | Split | Frames / positive fraction | AP | ROC-AUC | Precision | Recall | F1 | Brier |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Run / .10 | validation | 338 / .1183 | .7593 | .8718 | 1.000 | .475 | .6441 | .0554 |
| Run / .10 | test | 359 / .1114 | .8900 | .9582 | 1.000 | .325 | .4906 | .0321 |
| Run / .05 | validation | 338 / .0592 | .4552 | .8423 | .4762 | .500 | .4878 | .0758 |
| Run / .05 | test | 359 / .0557 | .7332 | .9861 | .5882 | .500 | .5405 | .0267 |
| Config / .10 | validation | 242 / .0826 | .7698 | .9805 | .6061 | 1.000 | .7547 | .0453 |
| Config / .10 | test | 168 / .1190 | .9926 | .9993 | 1.000 | .850 | .9189 | .0131 |
| Config / .05 | validation | 242 / .0413 | .8896 | .9922 | .6923 | .900 | .7826 | .0649 |
| Config / .05 | test | 168 / .0595 | .9332 | .9949 | .6250 | 1.000 | .7692 | .0518 |

At H=.10, test confusion matrices are TN/FP/FN/TP **319/0/27/13**
(run-grouped) and **148/0/3/17** (configuration holdout). At H=.05 they are
**332/7/10/10** and **152/6/0/10**. The figure includes validation matrices too.

## Held-out event results

| Benchmark / H | Split | Any pre-onset hit | Useful >=.02s hit | Mean valid lead [s] | False episodes | False / non-event run | False / eligible s |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| Run / .10 | validation | 1/2 | 1/2 | .0950 | 0 | 0 | 0 |
| Run / .10 | test | 2/2 | 1/2 | .0225 | 0 | 0 | 0 |
| Run / .05 | validation | 0/2 | 0/2 | undefined | 1 | 0 | .5917 |
| Run / .05 | test | 0/2 | 0/2 | undefined | 1 | 0 | .5571 |
| Config / .10 | validation | 1/1 | 1/1 | .0700 | 2 | .25 | 1.6529 |
| Config / .10 | test | 1/1 | 1/1 | .0800 | 0 | 0 | 0 |
| Config / .05 | validation | 1/1 | 1/1 | .0250 | 1 | 0 | .8264 |
| Config / .05 | test | 0/1 | 0/1 | undefined | 1 | 0 | 1.1905 |

At H=.10, run-grouped test leads are **0.040s and 0.005s**: the latter is
imminent detection and fails the useful-warning criterion. Thus there are zero
misses without the minimum lead but one useful-warning miss. The strict test
has an 0.080s warning on **one** event; this is not strong statistical evidence.
No event denominator is pooled across the overlapping benchmarks or horizons.

At H=.05, the run-grouped selected model fires 0.080s before one test onset,
stays high and never re-arms inside the horizon; the other event has no alert.
The strict rule fires 0.075s before onset and also stays latched. These too-early
episodes are false for the declared horizons. High frame AP/ROC-AUC therefore
does not translate into successful horizon-specific warning episodes. Changing
the latch or threshold after seeing test outcomes would be a new protocol,
requiring fresh held-out data; it is not done here.

The H=.10 run-grouped test cluster-bootstrap AP interval is approximately
**[.7737, 1.0000]**, with 275/300 event-containing replicates; useful event recall
spans **[0,1]**. Strict test has only two configuration clusters and one event:
64/300 replicates contain no event. Conditional useful-recall bounds collapse
to [1,1] on the remaining 236, which is explicitly **not meaningful population
uncertainty**. The corresponding AP bound also collapses in this cohort. No
precision claim is inferred from those degenerate intervals.

## Diagnostics and interpretation

Calibration curves and Brier scores evaluate warning-score reliability without
fitting a held-out calibrator. Class balancing and the fixed rule can produce
scores unlike the empirical event prevalence. Feature importances describe
association and fitted model behavior, not physical causes.

Validation-only permutation diagnostics perturb static values between complete
runs, or circularly shift dynamic feature sequences within a run. Shifts are
at least 0.10s where sequence length permits. This retains more within-sequence
structure than independent-frame shuffling, but correlated predictors and
out-of-support perturbations still limit interpretation. Signed standardized
coefficients or tree importances are exported when the selected model supports
them. No diagnostic is used to retune a frozen candidate.

Subgroup tables report outlet ratio, packing family and both friction regimes,
with independent run/event denominators. False alerts during interior crossing
gaps >=0.05s with a later resumed crossing are counted separately. A gap is
called temporary only retrospectively in this diagnostic, never from the
feature input alone. Event timelines overlay frozen scores, episode markers,
onset, confirmation and actual saved DEM trailing discharge history. Scores
are only plotted on the eligible first-event interval.

Generated figures:

- [calibration_pr.png](results/m4/calibration_pr.png)
- [confusion_matrices.png](results/m4/confusion_matrices.png)
- [feature_ablations.png](results/m4/feature_ablations.png)
- [event_timelines.png](results/m4/event_timelines.png)
- [false_alarm_diagnostics.png](results/m4/false_alarm_diagnostics.png)

### Feature groups and specific failures

At H=.10, prespecified run-grouped test static-only AP is .1609 (logistic) and
.1698 (forest/XGBoost), versus .8722-.9315 for current observations. Static
scores do not localize time: all three static candidates have zero useful test
event recall. Strict static-only AP is .3922-.6897 but useful recall is still
zero. These are descriptive cohort comparisons, not statistical superiority.

Removing arch proxies does not remove all ranking signal: run-grouped forest
AP changes from D_full .8981 to E_without_arch .8648. Removing clock/cumulative
proxies yields F forest AP .8932. Temporal-only/state C has .8423-.8731 test AP.
There is no consistent evidence that adding all static/history features helps
beyond current observations. The simple current-state rule reaches H=.10 test
AP .9734 (run) and .9976 (strict), with useful recall 1/2 and 1/1. Thus this
cohort does **not** establish added warning value from ML over a physics rule.
None of these posthoc comparisons replaces the frozen selected candidates.

Validation perturbations associate local occupancy/count with the run-grouped
forest (mean AP loss about .019), and local max speed with strict XGBoost
(about .281, SD .121). Coordination also matters in the latter. Max speed is
close to a variable in the label definition, so this is evidence of a potential
protocol proxy, not an independently validated arch precursor.

The strict H=.10 validation false alarm at **t=.195s** in
`production_a1d8150e7f3d0517_hexagonal_s404` has an instantaneous spanning path,
but local maximum speed is **.08317m/s** and trailing discharge is **80 particles/s**.
The hopper eventually empties at about .3974s. This is transient structure
during continuing flow, not a confirmed persistent arch. The other false alarm
is .120s before an eventual event, outside H=.10. Across selected held-out
candidates, no false alarm falls inside the diagnostic's defined later-resumed
interior crossing gap; this absence does not establish robustness to pauses.
Exact observations/future-crossing evidence are in
[error_examples.json](results/m4/error_examples.json), used only posthoc.

All plotted flow histories originate in the existing M3 DEM trajectories. No
particle motion is handcrafted and no new simulation is needed for these plots.

Reproduce with the commands in [M4_BASELINES.md](M4_BASELINES.md). Run
`python scripts/audit_m4.py` to recheck the data/source/artifact freeze, group
isolation, train-fitted scalers/encoders, OOF-only thresholds and numerically
bounded held-out prediction replay with identical warning decisions. Recreate supplementary error evidence with
`python scripts/analyze_m4_errors.py`. Full paths and metrics remain in local outputs.

## Verification and audit correction

**89 tests pass**, including all 64 M1-M3 tests and 25 M4 scientific tests;
strict Taichi CPU/CUDA checks remain enabled. pip check passes. The data audit
verifies all 30 raw checksums, all nine processed-file snapshots, 12 grouped CV
partitions, 80 final artifacts and 160 held-out prediction tables (44280 rows).
No nonfinite scores, changed M3 files or identified group/temporal input leakage
are found. This is an implementation audit, not proof of external validity.

An initial audit required bitwise prediction equality. Parallel Random Forest
tree accumulation differed by 2.22e-16 on replay; final replay maximum difference
is 3.33e-16. The audit now uses rtol/atol 1e-12 **and requires identical threshold
decisions**, hence identical warning episodes. This is a post-evaluation audit
correction, not retraining or test tuning. The original freeze/predictions remain
byte-identical. [audit_correction.json](../configs/m4/audit_correction.json) records
the exact before/after hashes for the two audit/integrity modules; changes to
training, features, weights, scoring or selection remain rejected. One upstream
Taichi locale deprecation warning remains. Evaluation also emitted a pandas
concatenation FutureWarning; it did not affect current outputs.

Measured training wall time is **39.43s**, including grouped OOF fits and all
80 final baselines; held-out scoring/bootstrap/table generation takes **15.00s**.
These exclude plotting, audit replay, tests and development. Local compressed
models total about **2.38MB**, local predictions/freezes/threshold tables about
**1.17MB**. No GPU training or additional DEM cost is incurred.
