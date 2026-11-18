# M6B-A physical compatibility

**No current source-variable pair is quantitatively eligible.** The machine-readable
[gates](../configs/m6b/compatibility_gates.json) require accessible measurements,
verified units/coordinates, relevant geometry/boundaries, a matched observable,
explicit repeats/uncertainty limitations and considered model-form discrepancy.
Unknown is not pass. An accessible metadata file is not a measured discharge rate.
The [evaluated table](results/m6b/compatibility.csv) has six blocked and three
qualitative-only pairings. No physical agreement score or parameter fit is computed.
The classifier additionally rejects known fatal unmatched model form even if other
gates pass; absent measurement data take priority over hypothetical compatibility.

## Protocol reconciliation

| Dimension | Cornerstones source | Current PharmaFlow | Consequence |
|---|---|---|---|
| Particles | Tridisperse circular disks: diameters 6.0, 7.4, 8.6 mm; relative fractions unresolved | Monodisperse strict 2D disks | D/dL uses the largest source diameter; never substitute mean or DEM diameter |
| Thickness/confinement | Reported 3.18 mm disks, 4.4 mm plate gap | No front/back contact walls | Out-of-plane freedom/friction and experimental alignment must be assessed |
| Geometry | Flat-floor outlet and sidewall setup, 22.7 cm vessel width, 50 cm height, roughly 35 cm fill | Inclined wedge and finite initial fill | Need independently specified matching wall segments and fill before rate comparison |
| Forcing/history | Vibration-assisted unclogging; material recirculation through separate air return | Gravity-only finite-fill discharge | Forced startup, material history/aging and replenishment do not match |
| Ejected amount | Species-dependent inferred mass across semicircular observation boundary | Unique first downward particle crossing of outlet plane | Mass/number/rate and observation boundaries are not interchangeable |
| Clog confirmation | Published five seconds without exit | First-persistent-arch-v1: 0.4 s finite contact/velocity evidence | Source clog labels are not synthetic finite-arch labels |
| Sessions | Reused grains, potentially correlated successive flows | Independent seeded initial states | Need session/sequence IDs and session-grouped uncertainty, not frame bootstrap |
| Contact/material | Reported density 940 kg/m3; friction, restitution, roughness/species masses unresolved | Assigned density/contact parameters, uncalibrated | Do not tune friction to absorb confinement or missing physics |

Experimental dimensions, sampling and protocol statements are reported from the
authors' [primary preprint, Methods II.1](https://arxiv.org/html/2407.05491v1#S2.SS1)
and [official software record](https://zenodo.org/records/10895419), not measured
by this project. Final methods and original README are still needed. The preprint
reports tracking precision 0.14 mm, whereas a final-position criterion elsewhere
uses 0.3 mm; these are separate definitions. Its inconsistent gravity unit is not
silently repaired. Composition fractions, physical raw coordinates and material
contact values remain unresolved despite knowledge of nominal disk diameters.

Delft's irregular 3D gravel, depth-dependent stress and visible-surface imaging
are substantially different from disks. No recovered mass/PIV table supports a
direct fit. A camera's 600 Hz setting does not calibrate a velocity field. A
load-cell signal would still require sensor interpretation, synchronization,
uncertainty and a force-to-mass audit. Do not infer complete volume fraction from
visible projected coverage, or adjust disk friction to mimic irregular grains.

Yogi's quasi-2D spherical particles and confinement differ from strict disks.
Accessible native `uy`/`phi` data permit only source-table inspection until units,
averaging, coordinate axes and area/volume definitions are supplied. No normalized
discharge or velocity scale can be reconstructed from magnitude alone.

## Event taxonomy scope

The existing operational-observation-v1 definitions and all historical first-arch
labels are unchanged. One previous crossing is not established continuous flow.

| M5 outcome | Cornerstones | Delft | Yogi tables |
|---|---|---|---|
| Startup blockage | Forced reset/start coverage and all attempts needed; not presently measurable | No recovered full startup/event history | Not observable |
| Post-discharge arch | Reported flow-ending clogs; source 5 s definition differs | No recovered arch evidence/annotations | Not observable |
| Established-flow arch | Requires complete raw crossing history and explicit preceding-flow test | Images/metadata alone cannot establish it | Not observable |
| Temporary interruption | Need complete pause/resumption history; selection code may remove states | Full recording/calibration needed | Not observable |
| Completed discharge | Source `Emptied` can retain an arch; not an empty hopper | Complete retained-mass history needed | Not observable |
| Censored/unresolved | Need raw observation endpoints and confirmation coverage | Coverage unresolved | No temporal outcome |

These are observability judgments, not measured zero external event counts.
Future confirmation may annotate retrospective source outcomes, never enter a
causal monitor. Source labels must not be merged with synthetic labels without
explicit reconciliation of reset, timing, boundary and confirmation definitions.

## Scientific alternatives

A. **Direct quantitative comparison:** not supported by the acquired evidence.

B. **Limited extensions:** polydisperse masses/radii and a measured flat-floor
geometry are plausible prerequisites for Cornerstones, but not sufficient by
themselves. Plate confinement, reset forcing, session dependence and material
properties must be independently resolved first. No extension or fit is executed.
Strict disks cannot automatically reproduce 3D gravel or confined spheres.

C. **Qualitative comparison:** native spatial-profile inspection and documented
flow/arching mechanisms remain possible, explicitly without agreement scores,
overlay calibration or claims of external early-warning validation.

D. **No meaningful accessible measurements:** too strong for the entire release,
because the Yogi experimental spatial tables genuinely exist and parse partly.
For time-indexed particle trajectories, however, acquisition remains blocked.

Numerical convergence, overlap guards and CPU/CUDA parity remain numerical
evidence, not physical agreement. Model form, unknown parameters and experimental
uncertainty remain distinct from discretization error. A future calibration stage
is not currently justified; the honest continuation is an explicitly labeled
**uncalibrated engineering simulation study**, while requesting documented external
inputs. Preserve historical held-out cohorts; never fit against them.
