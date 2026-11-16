# M4A readiness decision

**M4A_BASELINE_COMPLETE_BUT_DATA_INSUFFICIENT_FOR_GENERALIZATION**

The source/data isolation audit passes, all 89 tests pass, both frozen benchmarks
and both horizons are evaluated, and models, preprocessing, probabilities,
warning episodes and diagnostics are reproducible. M3 labels and test cohorts
are preserved. This completes the baseline milestone without claiming a robust
industrial or pharmaceutical predictor.

The H=.10 OOF-selected current-observation forest yields run-grouped test
AP .8900, zero false episodes and 2/2 pre-onset hits, but only **1/2** has >=.02s
lead. The strict current-observation XGBoost obtains AP .9926 and an .080s
warning with zero false episodes on **one** test event. That is one observation,
not strong evidence of unseen-configuration performance. Its validation set
already contains a false warning during continuing flow and another too-early
warning. H=.05 selected candidates have zero valid test event warnings despite
high frame ranking scores. Decision-policy behavior matters as much as AP.

Current disk observations carry more within-cohort time-localizing information
than static parameters. Removing direct arch/clock proxies retains ranking
signal, but label-adjacent speed/contact variables remain strongly associated.
Full temporal/static inputs do not consistently improve over current state, and
a simple physics rule is competitive with ML. There is no evidence justifying
GNNs, Transformers, world models or optimization at this point.

## Limits that prevent a generalization claim

- Only 11 independent first events, with one strict validation and one strict
  test event. Repeated adjacent frames/horizons do not increase this count.
- Strict held-out sets contain only two physical groups. Cluster intervals
  degenerate when the sole event-bearing group is resampled; population
  uncertainty cannot be meaningfully estimated from that design.
- M3 adaptively sampled transition configurations; seeds/packings are incompletely
  crossed, some geometry/fill presets co-vary, and initial packing density/energy
  differ. Run groups are less stringent than unseen physical configurations.
- First-event-only, 1.5s runs and P=.4s finite persistence are a protocol-defined
  outcome. No naturally censored runs are present. Later event cycles and an
  operational method of detecting that the first onset has already happened
  are outside this evaluation.
- H=.05 alarm failures show horizon/latch sensitivity. Onset resolution is .005s,
  relevant to a .020s useful-lead cutoff. No post-test policy repair is made.
- Warning scores are class-weighted or heuristic, with no proven deployment
  calibration. Importance is associative; protocol-proxy exploitation is possible.
- Strict dry 2D monodisperse disks have unresolved material/reference calibration.
  Cohesion, 3D/front/back-wall effects, instrumentation and real powder behavior
  are not modeled or validated. Reported seconds/false-alert exposure are
  simulated eligible time, not plant operating hours.

## Proposed M4B: acquire evidence before advanced modeling

The explicit ceiling is **48 new DEM attempts**, including failures, in
[m4b_proposal.json](../configs/m4/m4b_proposal.json). This is a proposal; **zero
M4B simulations have been launched or scheduled**.

1. Reserve 12 runs from **four entirely new physical configurations**, spanning
   all three packing families with independent new seeds. Freeze this cohort
   before inspecting any new outcomes. Never choose or replace test cases based
   on their event outcomes. Preserve M3 validation/test assignments and do not
   promote those runs into development training.
2. Run a 12-case development pilot around D/d=2.1-3.4, controlling wall angle
   during outlet comparisons. Cross packing families/seeds and measure quiet
   intervals that resume, candidate arches and numerical validity.
3. Only after that pilot review, allocate at most 24 more development attempts
   toward transition settings, friction/angle/fill variation and independent
   initial packings. Desired coverage is >=20 new development first events,
   multiple temporary interruptions and naturally unresolved trajectories;
   this is not guaranteed by the budget. Do not manufacture negatives from
   unconfirmed/censored windows or silently retry failures.
4. Observe 2.5s, permitting a documented ambiguous-run continuation to 3.5s
   within the same budget. Preserve numerical settings/guard initially; any
   change needs paired validation outside the evaluation cohort. Re-evaluate
   onset/P sensitivity and define all alert-policy alternatives on development
   groups before accessing the locked cohort.
5. Reassess rule versus current-state/temporal baselines, probability calibration
   and alert-policy robustness. Four new test configurations still give modest
   uncertainty; if event coverage is inadequate, report insufficiency and seek
   a separately justified budget. Do not proceed automatically to deep models.

The measured M3 dataset mean is **111.65 worker-wall seconds per 1.5s run**.
Linear duration scaling gives a rough 48-run budget of **2.48 worker-hours** at
2.5s, up to **3.47 worker-hours** if every run reaches 3.5s; about 37-52 elapsed
minutes at four workers before QA/plotting. This is a planning approximation:
empty-state fast-forwarding, fill, arch duration and node load can change cost
substantially. M4A itself uses CPU ML and launches no new solver run.

Material calibration and an independent experimental reference remain separate
scientific requirements. More synthetic events alone cannot establish real-world
industrial readiness.
