# M7A geometry audit and numerical analogue

This is a feasibility study, not calibration. Original M6B source files and
17 aggregate bins remain unchanged. The numerical coordinate convention below
is explicit and must not be mistaken for recovered MATLAB wall coordinates.

## Supported source information

Primary evidence: [Cornerstones preprint v1, II.A and III.B / Fig. 4](https://arxiv.org/pdf/2407.05491),
the checksum-verified original README, and verified author notebook cells 14/18.
The paper version is pinned; final-article equivalence is not assumed.

| Property | Source-supported value/definition | Remaining limitation |
|---|---|---|
| Free disk diameters | 6.0 / 7.4 / 8.6 mm | Species proportions unknown |
| Free material | UHMW polyethylene; nominal density 940 kg/m3, thickness 3.18 mm | Not independent mass/contact characterization |
| Fixed grain | Magnet, diameter dFG=dM=7.4 mm, held externally; on floor | Exact vertical center, mounting clearance and friction unmeasured |
| Position | Center distance from outlet edge divided by dFG | Raw axes/origins and geometric tolerances unresolved |
| Vessel | Width 227 mm, height 500 mm; approximately 350 mm fill | Floor/lip thickness and full coordinates absent |
| Fixed-grain outlet | D=3.86 dL=33.196 mm | Opening tolerances unknown |
| Confinement | 4.4 mm pane gap | No equivalent front/back mechanics in strict 2D |
| Startup | Exciter breaks prior arch | No excitation waveform recovered |
| Ejection | Source semicircular observation boundary | Exact tracking/count implementation unrecovered |
| Termination | Five seconds without grain exit | Differs from numerical 0.4-second finite-arch observation |
| Replenishment | Air-assisted recirculation, shielded from outlet | Sequential histories/session dependence unresolved |

The original README supports pixel positions/radii and second timestamps.
`dx/dy` are interframe displacements; raw `massflow.M` is cumulative ejected
area. The three TXT summaries are source-normalized mean ejected mass and SEM,
not kg/s or particle time series. The notebook establishes outward edge distance
and dFG normalization, but its raster coordinate recipe is not an optical or
wall calibration. No raw MAT structure was acquired.

## Declared numerical geometry

`FixedGrainSystem` selects `flat_floor` independently of the legacy wedge:
two floor segments at chosen y=0 separated by a centered gap D, and vertical
sides at x=±W/2 up to H. The ideal zero-thickness floor has finite segment lips.
The same closing gate spans the outlet until 0.05s. W=0.227m, H=0.5m and
D=0.033196m are held fixed across all conditions. An ideal circle is centered at

```text
x_FG = -D/2 - q*dFG          q in {0.30, 0.66, 1.14}
y_FG = R_FG                 R_FG = 0.0037 m
```

This chooses the left edge, outward-positive distance, and a circle tangent to
the ideal floor. These are analogue coordinates, not an inference that the
source floor's numeric y-coordinate is zero or that its magnet center is exactly
one radius above that plane. q<0.5 overlaps the outlet's horizontal projection;
q>0.5 clears it. All circles clear the outer sidewalls. No walls move when q
changes, and initial mobile states are byte-identical within each paired seed.

Sixty free disks have 20 of each source-reported diameter. **Equal composition
is an assumption**, not a recovered experimental proportion. Nominal cylinder
masses use rho*pi*R_i^2*h, with density/thickness above, and are stored individually.
The fixed magnet is excluded from mobile mass/accounting; its mass is irrelevant
to the prescribed immobile support. No actual magnet density is invented.
The initial fill is a seeded nonoverlapping lattice starting at y=0.025m;
row ordering, species ordering and small jitter vary independently by seed.
This shallow finite fill is substantially different from the source fill and
recirculation. No parameter is tuned to compensate for that difference.

## Compatibility gates and completed pilot

The [geometry gate](results/m7a/geometry_gate.json) checks packing clearance,
smallest-mass timestep, all obstacle placements and paired initial fingerprints.
`numerical_geometry_representable=true` authorizes this bounded analogue only.
`experimental_geometry_matched=false` and `physical_agreement_score_allowed=false`.
Missing plate friction, real lip details, source mixture fractions, excitation,
replenishment, passage boundary and termination prevent matched reproduction.

The [frozen design](../configs/m7a/pilot.json) contains three seeds and four
conditions, selected after inspecting the published curve. They are not an
independent experimental test, an optimization or a discovered optimum.
The first no-fixed-grain run profiled this same small 60-disk design. It did not
empty by half the observation window, so the remaining frozen cases were
permitted to run, with at most three one-thread CPU workers. All 12 charged
attempts (including the profile) succeeded within the 1800s-per-attempt and six
CPU-worker-hour caps. The 1.0s horizon was not changed after outcomes were seen.
There were no confirmed finite arches, startup blockages or empty hoppers; all
12 runs are right-censored for an arch event. See the [completed pilot report](M7A_PILOT_RESULTS.md)
and [readiness decision](M7A_READINESS.md). The budget is exhausted; this gate
does not authorize a follow-on campaign.
