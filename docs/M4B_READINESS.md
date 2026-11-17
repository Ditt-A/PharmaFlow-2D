# M4B readiness decision

**M4B_RULE_BASELINE_REMAINS_COMPETITIVE**

M4B completes the authorized 48-attempt expansion and an independent,
outcome-blind configuration evaluation. It does not establish an ML early-
warning advantage over an interpretable rule or pharmaceutical deployment
readiness.

## Evidence and completion

- **48 attempts / 48 valid / 0 failed**, consisting of 12 pilot, 24 controlled
  adaptive development and 12 locked evaluation runs. No extra solver dispatch
  occurs on a verified three-phase cached resume.
- **31 new independent first events**, zero natural right-censored cases and
  zero continuations needed. All observe 2.5s; the tested inherited continuation
  mechanism allows 3.5s for ambiguous cases but is not exercised here.
- **15 new physical configurations**, three packing families, 48 distinct new
  seeds/initial states; no duplicate trajectories or old packing reuse.
- **Seven locked events across four new configurations**; five locked runs
  complete discharge. Test settings/seeds are never replaced.
- **116 tests pass**: all 89 historical tests plus 27 new tests for budgets,
  resume/tampering, physical group isolation, frozen evaluation, causal replay,
  censoring and deterministic inference. Strict Taichi CPU/CUDA tests and
  pip check pass. Taichi remains 1.7.3, with no new dependency installation.
- All **208 historical data/model/result files** retain their checksums.
  Original M3 assignments/labels and M4A models/test results stay unchanged.
  New fits use only the 12 M3 runs that were training in both historical splits.
- Raw/feature finite checks, .005s timestamps, particle accounting, source and
  SHA256 checks pass. Peak overlap is **.078115 R**, below the unchanged .15 R
  guard. All 48 initial packings reproduce; all 31 real truncated event-prefix
  QA views correctly censor and are not added as new training examples.
- Full online prediction/episode replay passes **1806 run/candidate checks**,
  with zero numerical prediction replay difference. No oracle post-onset gate
  is used. Every new scaler/encoder/prior is audited against training rows.

## Why additional model complexity is unjustified

At primary H=.10, the frozen chosen full-feature XGBoost and the development-
informed rule both provide >=20ms warning for 7/7 test events. ML produces
**12 false first-event forecasts** versus **eight** for the rule, or **.6353
versus .4235 per particle-present operating second**. Six/five are late
post-onset notifications, separately identified rather than hidden by oracle
cropping. ML mean lead is 77.14ms versus 62.86ms, but additional lead does not
establish reliability when false burden rises.

The original **unchanged frozen M4A physics rule** gives 7/7 useful warnings,
**zero false forecasts**, and 57.86ms mean lead. This predeclared comparator is
reported as evidence; it is not used to rewrite the selected model/policy after
test. The new policy's stronger development utility did not transfer reliably.

At H=.05, selected temporal RF reaches 5/7 useful warnings versus 4/7 for the
informed rule, but produces **17 versus 14** false forecasts. The paired cluster
interval includes no gain, and simpler legacy rule variants remain competitive.
Current/temporal dynamics improve frame ranking over static-only inputs, yet
neither ranking nor policy recall alone proves an operational ML advantage.

## Remaining scientific limits

1. Only four independent test configurations and seven events. Equal 7/7 recall
   yields degenerate empirical cluster intervals, not a population guarantee.
   Locked settings are new combinations within a narrow sampled range.
2. Targeted adaptive sampling produces 24 events in 36 development runs. This
   is a controlled transition study, not an unbiased estimate of event frequency.
   Development validation was descriptive after open pilot review; the locked
   cohort is the independent evaluation.
3. **17/31 new events have no prior outlet discharge**. The first-arch task mixes
   initial blocked packings and arching after flow. None has an impossible <20ms
   timing ceiling under two-frame release gating, but startup-event performance
   must not be presented as established-flow industrial clog prediction.
4. Four short later-resumed crossing gaps occur, but only one such locked run
   and no resumed confirmed .4s arch. There is no naturally censored or failed
   population on which to estimate model behavior, despite passing handling tests.
5. Finite persistence P=.2/.4/.6 gives 31 events each; this is sensitivity within
   a quiescent finite-fill 2D model, not proof of permanent clogging. Repeated
   later event cycles and operator interventions are not modeled.
6. Alarm utility weights are prespecified research choices. Bounded refresh
   increases episode burden and transfers imperfectly. Late detections are
   conservatively counted as false first-event forecasts, not claims that no
   arch exists. Reporting only eligible windows hides this behavior.
7. Class-balanced/heuristic scores are not proven calibrated risk probabilities.
   Feature ablations/importance cannot establish causation. Frame sample counts
   and overlapping horizons are not independent physical-event sample counts.
8. Dry monodisperse 2D disks, assumed thickness, uncalibrated contact/material
   parameters and unresolved quasi-2D paper alignment remain unchanged. No
   cohesion, front/back wall effects, fluid coupling or industrial validation
   is introduced.

## Cost, paths and next research step

Measured solver worker-wall time is **13709.80s = 3.81 worker-hours**. Summed
phase elapsed time is **2540.46s = 42.34min**: pilot 783.05s at four workers,
adaptive 1241.87s and locked 515.54s at eight workers. CPU training/OOF policy
selection takes **340.00s**, evaluation **34.19s**. These exclude development,
plotting, audit and test overhead; they are not GPU billing or speedup claims.

New trajectories/manifests occupy about **28.0MB**, versioned processed releases
about **3.0MB**, new compressed models **1.59MB**. New-only feature/label counts
are **24048 / 48096**; development also retains unchanged permitted M3 training
rows. Data stays under `data/simulated/m4b/` and `data/processed/m4b/`; models
under `outputs/checkpoints/m4b/`; full predictions/freezes under
`outputs/metrics/m4b/`; full animations under `outputs/animations/m4b/`.
Only compact manifests/tables and representative figures/GIF enter Git.

Next work should refine the **physics-rule/alert-policy benchmark** using
development groups, distinguish startup blockage from established-flow onset
in a separately versioned future target, and improve independent interruption,
censoring and material-calibration evidence. Any new evaluation cohort must be
locked before outcomes and must not recycle the current test for tuning.
No additional campaign, neural model or deployment engine is launched by M4B.
