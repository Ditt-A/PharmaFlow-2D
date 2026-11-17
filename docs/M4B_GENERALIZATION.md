# M4B model and online-warning evaluation protocol

This evaluates whether additional independent DEM runs improve first-arch
warnings beyond an interpretable rule. Primary H=.10s; secondary H=.05s.
Model/policy decisions are frozen before any locked solver outcome exists.

## Training and comparators

The exact six M4A feature sets are retained: static A, current state B, causal
temporal/state C, full D, without near-explicit arch proxies E, and without
elapsed/cumulative proxies F. Reusing C/F adds controls for history/clock effects,
not new features. Logistic regression, Random Forest and XGBoost keep the same
conservative fixed hyperparameters as M4A. No neural architecture or broad
hyperparameter search is used.

Each new model is fitted only on eligible labels in the expanded training
groups. Scalers/packing encoders and run-balanced class weights are learned
separately within each three-fold physical-configuration grouped fit. OOF
prediction then covers **every chronological frame** of held-out training runs,
including post-onset observations; fitting never uses those excluded labels.
Full training refits use no development-validation or locked rows.

Comparators include unchanged frozen M4A current-state logistic/RF/XGBoost from
its strict benchmark, its run-grouped current-state forest, and the frozen strict
physics rule, at both original horizons/thresholds. Their artifacts remain byte-
identical. A second rule uses the identical physics score but selects threshold
and policy from new training OOF data, providing a fair development-informed
rule comparator. Every newly fitted candidate also has a legacy-policy variant
whose threshold is independently selected from training OOF data only.

The rule score is unchanged: `.45*stationary_fraction + .35*spanning_arch_now +
.20*exp(-near_speed_mean/.02)` when local/remaining counts are >=2, else zero.
It is a heuristic score, not an asserted calibrated probability. Class-weighted
ML scores also require calibration diagnosis; no held-out calibrator is fitted.
Forest inference uses a sequential joblib backend to avoid the tiny parallel
summation variation observed in M4A, without changing stored trees or parameters.

## Prespecified policy comparisons

Thresholds .10-.90 in steps .10 plus 1.01 (no warnings) are tested only on
training OOF sequences, with four policies in
[baselines.json](../configs/m4b/baselines.json):

| Policy | High debounce | Clear condition | Cooldown | Repeated high-score reminders |
| --- | --- | --- | --- | --- |
| M4A legacy | 2 frames | one score below threshold | .05s | none |
| Hysteresis | 2 frames | 3 frames below .65 threshold | .10s | none |
| Bounded refresh | 2 frames | 2 frames below .65 threshold | .05s | at .05s, at most two reminders |
| Longer debounce | 4 frames | 3 frames below .70 threshold | .10s | none |

Each episode begins on the debounce-completing frame; it is never backdated.
Missing timestamp intervals reset the high/clear counters. A repeated high
score is not arbitrarily counted every frame. Refresh is a prespecified bounded
episode policy, not a post-test repair of the .05s result.

The controller receives only observed timestamps, current scores and observed
remaining particles. It runs after known gate opening and while particles remain.
It does **not** read event onset, confirmation, labels, final outcome, future
crossings or oracle first-event eligibility. No controller stops merely because
an unknown onset has occurred. Prefix-invariance and post-onset toy tests enforce
that property. Particle-empty gating is directly observable, not future truth.

Training OOF policy/model utility is:

`useful_event_recall - .25*false_per_non_event_run - .05*false_per_operating_s - .01*false_per_run`.

Useful lead is >=.020s. Exact policy ties prefer legacy then earlier-listed
policies, and a higher threshold. ML model ties use equal-run eligible AP,
fewer features and simpler models. The selected ML and development-informed
rule are frozen separately per horizon. All original/legacy variants remain
prespecified descriptive comparisons; a better test variant is never promoted
to the chosen model after seeing test results.

## Two distinct evaluation views

Frame metrics use only supported eligible pre-onset labels: AP, precision,
recall, F1, Brier, ROC-AUC when defined, confusion counts and prevalence. They
remain descriptive dependent-frame summaries. Empty/post-onset/censored states
are not manufactured binary negatives. Every preprocessing transformation is
train-fitted.

Retrospective episode evaluation can restrict replay to eligible frames, for
comparison with M4A. **Primary online replay does not apply that restriction**.
It processes the full observable run in time order. True onset/confirmation
are applied only afterward to categorize episodes:

- A hit requires `0 < onset-alert_time <= H`; useful hits additionally require
  >=.020s lead. Leads below .020s are imminent detection.
- A pre-onset episode farther than H from onset is a false first-event forecast.
- An episode at/after first onset is a late detection, never an early-warning
  hit. It is separately counted and conservatively included in false **first-
  event forecast** burden; it is not described as proof that no arch exists.
- Unsupported future on a right-censored interval produces an unscorable
  episode, not an automatic false alarm or negative. It remains in the table.
- Empty states cannot fire. Later event cycles are outside this first-event
  task; continued open-loop simulations do not model operator intervention.

Report false episodes/run, false episodes/full observed simulation second
(duration after gate opening, including absorbing empty time), and false episodes/
observable **operating** second (remaining particles >0 after gate opening,
grid count times .005s). The operating-time rate avoids dilution by empty
fast-forward tails and includes post-onset operation. It never uses oracle
eligibility. Raw eligible exposure is also retained. Frame metrics are identical
between replay modes for a fixed candidate; episode streams can differ.

Warning lead distributions, late detections, unscorable episodes, resumed-flow
subgroups and physical/packing contrasts are exported per independent run.
Actual crossing gaps >=.05s with a later crossing are temporary interruptions,
not inferred permanent clogs. First confirmed finite arches that later resume
remain primary first events under the unchanged labeling protocol.

## Locked uncertainty and readiness criterion

After the complete freeze, the 12 locked attempts are dispatched once and their
release is built separately. All previously selected candidates/policies are
scored without model changes. Completed evaluation refuses overwrite. Cluster
bootstrap resamples all runs/frames of each of the four physical groups, using
500 paired replicates for selected ML versus the development-informed rule.
Undefined event/AP replicates are counted explicitly. Four groups still give
weak, sometimes degenerate uncertainty; frame count does not repair that.

Before inspecting locked outcomes, the minimum evidence floor is **six confirmed
events across at least three physical configurations**. Below it, the decision
is `M4B_INSUFFICIENT_INDEPENDENT_EVENT_EVIDENCE`. This floor is a pragmatic
research gate, not a power analysis or sufficient evidence for deployment.

Above that floor, support for further temporal modeling additionally requires
primary-horizon ML useful recall at least .15 above the development-informed
rule, added false forecasts/operating second <=.05, and a positive lower paired
cluster bound for recall gain. Otherwise the decision is
`M4B_RULE_BASELINE_REMAINS_COMPETITIVE`. Even a favorable exploratory result
does not establish industrial calibration or pharmaceutical readiness.

All animations use saved new DEM positions, velocities and contact graphs.
Only score/episode history at or before the animation cursor is revealed. True
onset, future confirmation and false-forecast red X markers are explicitly
posthoc annotations. Playback time differs from physical simulation seconds;
the time cursor and visualization manifest preserve the actual clip duration.

Posthoc `event_context.csv` additionally reports prior discharge at onset, quiet
spanning snapshots at gate release, and the maximum lead allowed by the .05s
gate plus two-frame debounce. These are outcome-analysis fields, never new
predictors or label changes. Events with no established flow or too little
possible lead require a different interpretation from clogging during sustained
discharge. They remain in the unchanged primary denominator and are not silently
removed to improve performance.

## Frozen choices and locked results

Freeze time is **2026-11-17 06:09:10 UTC**, before locked dispatch. SHA256:
`a5e93b1f461d539665f39719bdb8b51951da62333c7d2183fbb4f7e15e2d5683`.
H=.10 selects **D_full XGBoost, threshold .50**; H=.05 selects **C_temporal
Random Forest, threshold .10**. The rule selects .50/.70 respectively. All four
selections use bounded refresh. No model, feature list, threshold or policy is
changed after opening the test cohort.

There are **seven confirmed events across all four locked configurations**:
D/d=2.2 gives 3/3, 2.85 gives 1/3, 2.6 gives 2/3, and 3.3 gives 1/3. All 12
attempts are valid and uncensored. Eligible frame counts are 643 per horizon,
with 140/70 positives (21.77%/10.89%). No frame independence is asserted.

| H [s] / candidate | AP | Precision | Recall | F1 | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| .10 / selected full XGBoost | .9148 | .7875 | .9000 | .8400 | .0547 |
| .10 / development-informed rule | .9594 | .9440 | .8429 | .8906 | .0596 |
| .05 / selected temporal RF | .7492 | .3743 | 1.0000 | .5447 | .0543 |
| .05 / development-informed rule | .9040 | .6415 | .9714 | .7727 | .0946 |

All warning metrics below use **full chronological operation**. Observed exposure
is 29.4s after release, including empty tails; particle-present operating exposure
is 18.89s. Post-onset alerts are included in conservative false-first-event-
forecast counts and also identified separately.

| H / candidate | Useful hits >=20ms | First-valid lead mean [ms] | False forecasts | Per run | Per observed s | Per operating s | Post-onset alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| .10 / selected ML | 7/7 | 77.14 | 12 | 1.000 | .4082 | .6353 | 6 |
| .10 / informed rule | 7/7 | 62.86 | 8 | .667 | .2721 | .4235 | 5 |
| .05 / selected ML | 5/7 | 30.00 | 17 | 1.417 | .5782 | .8999 | 2 |
| .05 / informed rule | 4/7 | 26.43 | 14 | 1.167 | .4762 | .7411 | 8 |

At H=.10, ML leads span **50-100ms** and rule leads **40-90ms**. At H=.05 both
produce a pre-onset episode for all seven events, but two ML and three rule
episodes have <20ms lead and are imminent detections. Their useful-warning
misses are therefore 2/7 and 3/7. Full per-event timestamps/leads are in
[selected_event_runs.csv](results/m4b/selected_event_runs.csv).

Oracle-cropped replay hides substantial notification burden: H=.10 false
forecasts fall from **12 to 6** for ML and **8 to 3** for the informed rule when
post-onset frames are removed. Frame AP is unchanged. Both mode tables retain
the same full-operation denominators for direct comparison; eligible exposure
is separately stored in the run table. Online deployment performance cannot
be inferred from the cropped stream.

### Frozen comparators and policy transfer

These candidates/policies were all defined before test; none replaces the
preselected primary model after seeing its result.

| H=.10 comparator | AP | Useful hits | False forecasts |
| --- | ---: | --- | ---: |
| Frozen M4A strict physics rule (.85, original policy) | .9594 | **7/7** | **0** |
| Frozen M4A strict current logistic | .9348 | 5/7 | 4 |
| Frozen M4A strict current forest | .9499 | 6/7 | 1 |
| Frozen M4A strict current XGBoost | .9015 | 6/7 | 3 |
| Frozen M4A run-grouped current forest | .9219 | 5/7 | 4 |
| New full XGBoost, training-selected legacy policy | .9148 | 6/7 | 3 |
| Rule, training-selected legacy policy | .9594 | 7/7 | 0 |

The unchanged M4A rule already gives all seven useful warnings with **zero false
forecasts**, mean lead **57.86ms**, on this cohort. The development-informed
bounded-refresh rule increases burden without an observed primary recall gain.
This is evidence of policy-selection transfer uncertainty, not a reason to
silently replace the frozen policy with the best test row.

At H=.05, selected ML bounded refresh improves useful hits from its predeclared
legacy variant's **1/7 to 5/7**, while false forecasts rise **7 to 17**. The
informed rule's legacy variant gets 5/7 with four false forecasts, compared with
4/7 and 14 for its selected refresh policy. The original M4A frozen .05 rule
gets 4/7 with five false forecasts. Thus improved recall can be purchased with
more notifications, and the policy favored by development OOF need not transfer.

### Ablations, interrupted flow and uncertainty

For the prespecified XGBoost feature ablations at H=.10, locked AP is A_static
**.2616**, B_current **.9201**, C_temporal **.8890**, D_full **.9148**,
E_without_arch **.9170**, and F_without_time_discharge **.9284**. Observed state
carries more ranking information than static parameters, but full input does
not consistently outperform the simpler groups. Removing arch/clock proxies
retains signal; it does not establish a causal precursor or ML superiority over
the physics rule. All logistic/forest/XGBoost ablations remain in
[metrics.csv](results/m4b/metrics.csv), not selected again from test results.

Four new runs contain later-resumed crossing gaps >=50ms; the maximum is
**94.34ms**. One locked event-bearing run contains such a gap before its later
first confirmed arch. On that one run, both primary candidates give useful
warnings, but ML generates three false forecasts (two late), versus two (both
late) for the rule. This is only one independent interrupted-flow test case.
No confirmed .4s arch resumes in the observed cohort. See
[resumed_flow_timeline.png](results/m4b/resumed_flow_timeline.png).

Primary ML cluster-bootstrap AP bounds are approximately **[.8663,.9930]**.
Both primary candidates detect every observed event, so paired useful-recall
gain is **0**, with empirical bootstrap bounds **[0,0]**. Those degenerate bounds
reflect no observed discordance, not proven equivalence or a population recall
of one. There are still only four configurations/seven test events. Secondary
useful-recall gain is 1/7; paired bounds **[0,.4286]** include zero and false
burden increases. No stronger generalization or causal claim follows.

**Decision: `M4B_RULE_BASELINE_REMAINS_COMPETITIVE`.** The primary ML model has
equal useful recall and a higher false-forecast burden than the informed rule,
and the original frozen rule remains especially strong. This does not justify
neural complexity or deployment.

The publication bundle includes [locked_summary.png](results/m4b/locked_summary.png),
[calibration.png](results/m4b/calibration.png), a synchronized actual DEM
[animation](results/m4b/demo.gif) and [snapshot](results/m4b/demo.png), plus complete
compact metrics, configuration event counts, class proportions and uncertainty.
Full GIFs remain in `outputs/animations/m4b/`. Regenerate supplementary plots with
`python scripts/plot_m4b_diagnostics.py`; it reads saved predictions and fits nothing.
