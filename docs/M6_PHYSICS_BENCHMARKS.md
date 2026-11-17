# M6 physical benchmark protocol

Version `m6-physics-benchmarks-v1` defines seven comparisons. It does not claim
they have passed. The machine-readable definitions, units, required outputs,
aggregation, uncertainty and invalidity conditions are in
[`benchmark_protocol.json`](../configs/m6/benchmark_protocol.json).

## Definitions and eligibility

| Benchmark | Physical quantity and required match | Current external eligibility |
|---|---|---|
| Rate versus D/d | Sustained downward number or mass passage rate at fixed inclination, particle system, fill and boundary; state which d is used. | None matched. Dryad raw access/schema unresolved; Delft mass series not located; Yogi has no direct rate table. |
| Time-resolved discharge | Cumulative number/mass and rates in fixed physical-time bins `(a,b]`, aligned to actual release. | Conditional on raw histories, sensor calibration and reconciled boundaries. No experimental series ingested. |
| Near-outlet velocity | Signed velocities in defined spatial bins/time windows with the same optical/center/surface selection. | Dryad potential; Delft needs calibrated PIV; Yogi native numbers lack verified units. |
| Exit occupancy/density | Matched clipped area, exit-line occupation or volume fraction, never an unlabeled mixture of these. | Not matched. M3 center-assigned occupancy is not exact packing fraction. |
| Startup/arch occurrence | Unchanged M5 operational categories plus separately reconciled source confirmation definitions. | External event counts unresolved, not zero. No labels merged. |
| Inclination/friction sensitivity | One-factor variation with actual angles and material interfaces controlled. | Delft nominal angles are known but reference and particle/contact properties unresolved; no quantitative material match. |
| Intermittency | Crossing pause with retained material followed by observed resumption, with censoring explicit. | Potential in complete Dryad/Delft histories; not observable in static Yogi profiles. |

Quantitative validation requires verified units, observation boundary/definition,
geometry, particle system, averaging, data quality, experimental uncertainty and
bounded numerical sensitivity. **Unknown fails a gate.** A checksum alone opens
none of the physical gates. An eligible comparison still cannot by itself
establish calibrated parameters. `quantitative_eligibility` always keeps the
calibration claim disabled in M6A.

Rate uncertainty must include clock quantization, counting/segmentation, particle
mass and independent fill/session variation. Profile uncertainty must include
tracking/PIV error, binning, missing spatial coverage and repeat variation.
Run or experimental-session means, not adjacent frames, are the resampling units.
For paired seeds/configurations retain the pairing or cluster at configuration/
session level. A single independent group has no estimated confidence interval.
`grouped_summary` supplies deterministic cluster resampling but no external
uncertainty is invented when measurements are missing.

## Number, mass and normalized flow

For unique first downward DEM crossings,
`QN(a,b) = [N(b)−N(a)]/(b−a)` has units particles/s. For known equal masses,
`Qm = m_particle QN` has units kg/s. A mixture requires the **sum of actual
crossing masses** in each bin: multiplying a segregating mixture's number rate by
an arbitrary mean mass is not generally valid. Recirculating experiments must
count passages, not unique particle identities over their full lifetime.

For a uniform cylindrical disk, `m = rho_material h pi d²/4`, where h is the
physical disk thickness. Plate spacing is not interchangeable with h. The
current d=4mm, rho=2500kg/m³, h=10mm model disk has mass
0.000314159kg. This is the simulator's assumed mass, not a calibrated powder mass.

Define a true bulk areal density `rho_A,bulk = rho_material h phi_bulk`, in kg/m².
A dimensional candidate for sustained strictly 2D flow is

```text
Qm = C rho_A,bulk sqrt(g) (D − k d)^(3/2)
Qm / [rho_A,bulk sqrt(g) d^(3/2)] = C (D/d − k)^(3/2)
QN sqrt(d/g) = (4 C phi_bulk / pi) (D/d − k)^(3/2)   [equal disks only]
```

`QN sqrt(d/g)` is dimensionless. Dividing kg/s by a number-flow normalization
is not. The formulation requires a defined bulk fraction; the unbounded
center-assigned near-outlet occupancy estimate must not be substituted for it.
The literature sometimes uses material areal density instead, absorbing packing
into C; such coefficients cannot be equated without reconciling definitions.

The [strict-2D disk study by Carlevaro et al.](https://www.frontiersin.org/journals/soft-matter/articles/10.3389/frsfm.2024.1340744/full)
provides context for this areal-density form. It is a numerical study, not an
additional independent experimental calibration dataset. A 3D circular orifice
instead gives the familiar dimensional candidate with bulk kg/m³ density and
5/2 power. A quasi-2D slot can introduce a depth factor, but confinement and
front/back friction cannot be erased by multiplying a strict-2D disk result by
an arbitrary thickness. The [confinement study](https://link.springer.com/article/10.1007/s10035-021-01159-6)
shows why that model-form distinction matters.

C and k are empirical and are not supplied as universal constants. D>kd is a
mathematical domain condition, not a no-clogging guarantee. The implementation
raises an error outside that domain instead of returning zero-flow regression
samples. No coefficient, offset or exponent is fitted in M6A. The 3/2 form is a
dimensional candidate whose empirical applicability needs testing; it is not
assumed valid for every friction, inclination or confinement regime. See
[Shah et al.'s friction study](https://arxiv.org/abs/2103.09144) and the
[Cornerstones author preprint](https://arxiv.org/html/2407.05491v1#A1).

## Existing trajectories do not establish steady scaling

Only **39 permitted training runs** are screened: the intersection of both M3
training assignments (12 runs), plus M4B development-training (27 runs), spanning
15 physical configurations. M3 validation/test, M4B validation/locked and M5 demos
are excluded. No physical parameter or model is fitted from any of them.

Prospective screening requires a 100ms post-gate buffer, at least 20% of initial
grains retained throughout the window, ≥1s duration, ≥200 observed crossings,
at least five nonoverlapping 0.2s blocks, crossing gaps ≤50ms, block CV ≤0.2 and
first-to-last block-rate change ≤0.2 of the mean. These are **prespecified
diagnostic support thresholds**, not experimentally calibrated stationarity
definitions. Their sensitivity must be assessed in a future adequate-fill study.
Long arch tails do not count as flowing time. The filter does not claim proof
of stationarity just because all screens pass.

The largest existing fill is 50 particles; the maximum post-buffer crossing
count is **29**. **0/39 runs qualify**. Thus these releases cannot support a
meaningful sustained-flow Beverloo fit under the stated protocol. The result
is a limitation of the experiment design, not evidence that Beverloo scaling
fails physically. M2's outlet sweep also changes wall inclination when outlet
width changes, so it is not used as an isolated outlet-law experiment.

Avalanche mass before a clog is not a mass discharge rate. Nor is the ratio of
mean mass to mean duration generally the mean of individual flow rates.
Clogged zero-rate windows must not be treated as ordinary free-flow regression
points. Transient finite-fill discharge remains a valid, separately defined
observable, displayed with its actual physical clock and mass conversion.

## Quantitative figure evidence and limits

`available_discharge_observables.png` uses the fixed historical training example
`pilot_0151aedb5166ad43_hexagonal_s202`: real unique crossing counts and
individual crossing masses, in 50ms bins. It does not overlay a nonexistent
experimental discharge series. `native_profile_limits.png` shows the actual
strict-parseable experimental y/uy subset (43/160 rows at each outlet) on native,
unverified axes beside a **different**, explicitly signed DEM center-strip
profile: |x|<4mm, y bins of 5mm, t=.05–.25s. These are transient particle-time
averages, not a matched steady Eulerian validation. Empty bins remain missing.

No coordinate flip, normalization fit, unit inference, cell repair or residual
is applied. `acquisition_uncertainty.png` displays actual headered recording-rate
annotations, not measured flow rates. Conceptual diagrams are marked conceptual.
Input coverage, figure hashes and compact support tables are in `docs/results/m6/`.

```bash
python scripts/audit_m6_sources.py
python scripts/benchmark_m6.py
python -m pytest tests/test_m6.py -q
```

Full historical local NPZ and cached Numbers files are needed to reproduce the
figures; a fresh clone will not manufacture replacements or launch a campaign.
