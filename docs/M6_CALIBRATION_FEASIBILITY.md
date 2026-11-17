# M6 calibration feasibility and identifiability

**No physical calibration has been performed.** None of the three audited
sources currently supplies a verified, matched measurement package for this
strictly 2D monodisperse wedge solver. Dryad is the most promising particle-shape
candidate, conditional on raw access/schema and geometry/material reconciliation.
Delft is 3D gravel; Yogi uses quasi-2D/3D particles with unresolved data units.
The current result is `M6A_LIMITED_COMPARISON_ONLY`.

## Separate four discrepancy sources

| Source | Evidence and implication |
|---|---|
| Discretization | M2 elastic-pair maximum energy excursion decreases 1.27746% → 0.634738% → 0.316388% under dt refinement. This is numerical evidence for that controlled problem, not material calibration. M3 stiffness tests reduce overlap while changing near-clog discharge nonmonotonically. |
| Model form | Strict disks omit 3D sphere/irregular-grain contacts, front/back friction, rolling resistance, cohesion and air coupling. The dry linear history law is simplified. No parameter adjustment can establish that an omitted mechanism is negligible. |
| Parameter uncertainty | Friction, restitution, wall roughness, size/shape, density, species fractions and true bulk packing are insufficiently characterized for a matched experiment. Several parameters affect the same macroscopic rate. |
| Experimental uncertainty | Pixel/time/mass calibration, PIV versus particle tracking, sampling, repetitions, startup selection, inconsistent catalogs, malformed exports and unknown averaging create separate limits. |

These terms need not be independent or simply additive. Refining dt bounds one
component; CPU/CUDA agreement checks an implementation; neither removes
model-form or experimental discrepancy. A checksum verifies content, not physics.
Approximate gate/history energy accounting in the existing hopper does not prove
exact mechanical energy closure. Frictional/damping energy loss is legitimate
physical dissipation; only the refinement-dependent part is numerical error.

M3's paired D/d=2 stiffness experiments discharge 2/8/2 grains at
kn=1000/2000/4000N/m with corresponding kt/damping and guarded dt. Those are not
stiffness-independent outcomes or a calibration curve. The fixed current
kn=4000N/m, kt=1000N/m, dt=5µs and .15R guard remain unchanged. Historical
M2/M3 results are reused with their original settings, not overwritten.

## Parameter identifiability

| Parameter/mechanism | Could constrain it with | Present assessment |
|---|---|---|
| Diameter distribution, mass, density, physical thickness | Independent dimensional/mass measurements and species counts | Dryad preprint reports several values; mixture fractions and raw field units still need verification. Do not fit them to compensate for a rate mismatch. |
| Bulk packing | Matched, calibrated clipped-area measurements over a defined bulk ROI | Not established by the current center-assigned near-outlet occupancy or unidentified phi column. |
| Particle-particle friction | Independent shear/tilt/contact tests, then multiple geometries/kinematics | Cannot separate it reliably from sidewall friction or packing using one discharge curve. |
| Sidewall friction | Material-pair wall tests with actual roughness and angle | Not equivalent to front/back friction. No independent coefficients retrieved. |
| Restitution/dashpot | Speed-dependent binary impact tests with known masses and contact law | Current damping acts during approach. Do not invert a formula for an all-contact damped spring without checking this convention. Use an independent numerical collision assay only in a later authorized study. |
| kn and kt | Contact/compression data if deformability is relevant, plus numerical stiffness sensitivity | In a rigid-grain discharge regime they are weakly identifiable from rate; select a converged numerical regime instead of fitting artificial overlap. |
| Front/back friction, rolling resistance, cohesion and shape | Physical measurements plus an engine that represents those mechanisms | Missing mechanisms are not adjustable parameters in this engine. Any extension requires separate justification and validation. |

A rate essentially constrains a composite of packing, exit velocity and material
mass. A good rate fit can hide compensating density/velocity errors. C, k,
friction and density are not jointly identified merely because an optimizer
could return numbers. M6A runs no optimizer and supplies no fitted estimates or
invented parameter confidence intervals.

## Conditional calibration workflow, prepared but inactive

1. Recover a provider-supported small Dryad subset and its README/checksums.
   Verify fields, physical units, species fractions, mass boundary, camera
   coverage, startup/vibration, recirculation, walls and full hopper geometry.
   Reconcile against the final article, not solely its older preprint. Stop if
   the current engine cannot represent the experiment. Current monodisperse
   wedges do not match the tridisperse floor/opening setup.
2. Independently characterize particle masses/dimensions, wall and particle
   friction, roughness and restitution. Establish optical/time and sensor
   calibration. Do not estimate all of them from discharge data.
3. Before fitting, reserve complete experimental sessions/fills and an entire
   outlet configuration for validation. Two prespecified matched outlets could
   provide calibration rate/velocity observables; a third outlet, other spatial
   profiles, fluctuations/transients and reconciled event categories remain
   independent validation observables. Preserve pairing and session dependence.
   No historical M3/M4B held-out run may become calibration data.
4. Bound numerical uncertainty using identical initial states and fixed physical
   duration at dt, dt/2 and dt/4. Check overlap/forces, conservation, event and
   rate sensitivity under stiffness changes while retaining .15R. For identical
   masses, scaling damping with sqrt(kn) retains dimensionless damping; this
   does not itself calibrate restitution. Choose each dt with the existing
   guard and the smallest physical mass in any future mixture.
5. Prespecify a residual vector of matched steady rate and signed local velocity
   profiles. A candidate objective is `r.T @ Sigma^-1 @ r`, with experimental
   covariance and independently bounded numerical uncertainty. Correlated bins
   need covariance treatment. Missing measurement uncertainty is not replaced
   by a fabricated small error bar. Analyze structured model discrepancy
   separately rather than forcing friction to absorb it.
6. Propagate measured mass/geometry/size and nuisance-parameter uncertainty,
   bootstrap independent fills/sessions/configurations, examine parameter
   confounding and validate on the frozen external cohort only once. Report
   failures or non-identifiability explicitly.

Broad **proposed assay/screening ranges**, not measured material priors, are
μpp/μwall∈[0,1], restitution-assay e∈[.1,.95], and numerical kn levels
4000/8000/16000N/m with kt/kn=.25. Replace or expand these ranges after independent
characterization; do not clip a real material into them merely to obtain a fit.
Current parameters/guards are unchanged. No front/back correction factor is
silently introduced. The complete inactive plan is versioned in
`configs/m6/benchmark_protocol.json`.

## Bounded M6B proposal — not launched

Start with **at most 12 provider/author-curated no-fixed-particle MATLAB flow
files across three outlets, ≤200MB total**, accompanied by units, schema,
checksums and session information. Stage A uses **zero DEM attempts**. If only
multi-GB archives are accessible, obtain a legitimate small subset first.
Do not download the complete Dryad release or use its unidentified three text
arrays as an assumed rate curve.

Only after an explicit compatibility review and separate authorization, propose
a ceiling of **12 new solver attempts including failures**: three numerical
sensitivity/profiling attempts, then at most nine sustained-flow experiments
(three controlled outlet ratios × three independent fills). One CPU worker,
≤1800 wall seconds per attempt and ≤6 worker-hours total are budget ceilings,
not measured runtime estimates. Profile before larger fills; stop rather than
retry or relax guards if useful windows cannot be obtained.

An optional internal-scaling design would use D/d=6,8,10 at fixed 35° from
vertical with validated larger fills sufficient for ≥200 crossings over ≥1s
before depletion. That would be an **internal numerical scaling experiment**
until it is physically matched externally, not an external calibration. Larger
packings and their runtime are unmeasured and must pass a feasibility gate.
No M6B runs, fits or model changes are authorized or started by this proposal.
The M5 demo budget remains separate and reserved for dashboard usage.
