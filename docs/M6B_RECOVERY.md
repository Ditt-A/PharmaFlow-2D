# M6B browser-supplied recovery supplement

Date: 18 November 2026. This supplement follows original M6B-A commit
`b8228281578f5675dc15f7beef1be25ddb711cb0`. The user successfully downloaded
four public Dryad files through their browser and supplied a local folder.
All four match the previously recorded provider size and SHA-256 exactly.
The earlier automated README request did return HTTP 403; that observation
does **not** mean browser access is unavailable. The specific cause of the
different client responses has not been established. No denied route is retried,
no browser credentials/cookies are extracted, and no source results are replaced.

## Actual recovered files

| File | Bytes | Supported content |
|---|---:|---|
| README.md | 5,424 | Original source data dictionary and protocol descriptions |
| BinCenters.txt | 425 | 17 fixed-grain position bin centers |
| Dimensionless_M.txt | 425 | 17 source-normalized mean ejected-mass values |
| Dimensionless_M_std_error.txt | 425 | 17 reported normalized standard errors |

Source: Hanlan, Dillavou, Durian and Liu,
[Dryad Cornerstones](https://doi.org/10.5061/dryad.cvdncjtb5), provider version
376462 / versionNumber 9, CC0 1.0. Hashes, access method and the source version
are in [provenance.json](results/m6b/recovery/provenance.json).
The pipeline did not observe an HTTP status for the user's browser downloads.
It establishes integrity by comparison with the official published SHA-256.
The original acquisition ledger and failed reservation remain unchanged.

Combined conservative accounting: **11/12** curated reservations, including
the old failed README and four new user-supplied files; **10 successful files**,
**8,147,652 bytes** retained. This supplement adds **6,699 bytes**, including
**1,275 bytes of genuine experimental summary arrays**, with zero new provider
requests. Counting local inputs as additional transfer allowance gives a combined
reserved ceiling of **17,139,579 bytes**, below 200,000,000. Browser page/HTTP
overhead is not measured; reported file bytes are not an estimate of that overhead.
Only one curated reservation remains under the current cap. The older unsent
nine-file author-request draft cannot be executed in full under that remaining
allowance; a larger acquisition would require a separately documented budget.

## Definitions now documented

The original release's unknown tracking units are partly resolved by the README:

| Field | Source-documented definition | Still unresolved |
|---|---|---|
| x, y, radii, D, cpt | Spatial coordinates/dimensions in pixels | Optical calibration to m, origin/sign and mapping into DEM coordinates |
| timestamp, massflow.T | Timestamps in seconds | Actual per-run timestamp/frame alignment and observation coverage |
| frame | Frame index | Actual omitted frames and interval consistency |
| dx, dy | Displacement from previous frame | A velocity requires the actual interframe time; do not call these m/s |
| species, ID | Size category and tracked grain ID | Actual encoding, fractions, ID continuity and session identity |
| massflow.M | Cumulative **ejected area** per frame | No documented conversion to kg; no automatic assumption of absolute area units |
| fixedParticle | Flag distinguishing inserted fixed grain from all free grains | Actual MAT flags have not been read |
| flow_issue | Source trial-discard flag | Actual flags/failure counts unknown; never silently discard |

The current TXT summary observable is source-labeled normalized ejected mass,
not a dimensional mass-flow rate. Its denominator is mean ejected mass without
the fixed grain at the same outlet. The original README and companion
`FixedParticleFigure.ipynb` cells 14/18 establish the x-axis as distance of the
fixed grain from the outlet edge divided by its diameter, **x/d_FG**. This is
dimensionless, not pixels, metres or elapsed time. The verified notebook is
inspected as text only; none of its code, pickle inputs or stored images is run.

The README reports 5,551 fixed-grain flows, 35,116 single-outlet no-fixed-grain
flows, and approximately 7,263 other-outlet flows. These are reported archive
counts, not independently inspected runs or a verified independent-event count.
Differences from earlier paper descriptions must not be silently reconciled.

## Quantitative source summary, without DEM agreement claims

All arrays have 17 finite entries; bin centers increase strictly and reported
standard errors are nonnegative. Position spans **0.06 to 1.98 d_FG**. The
normalized mean spans **0.343773 to 1.704680**. The largest tabulated mean is
**1.704680 ± 0.076978 SEM** at **x/d_FG=0.66**. This identifies a tabulated bin,
not an optimized design or independently significant optimum.

[Actual experimental figure](results/m6b/recovery/fixed_grain_summary.png) and
[derived table](results/m6b/recovery/fixed_grain_summary.csv) retain all bins.
Error bars are the source's reported standard errors, **not** 95% confidence
intervals. Bin sample counts, session dependence, covariance and uncertainty in
the shared normalization denominator are unavailable. Seventeen aggregate bins
are not seventeen independent runs or events. No hypothesis test, interpolation,
physical residual, fitted parameter or DEM overlay is computed.

## Compatibility and scientific decision

This recovery supplies a genuine external experimental curve and resolves some
schema/units uncertainty. Direct comparison of this fixed-grain curve with the
current solver is **INCOMPATIBLE_MODEL_FORM**: its current configuration does not
implement a matched inserted fixed-grain experiment. Tridispersity, floor/outlet
geometry, plate confinement, reset vibration, recirculation and unknown contact
parameters remain additional mismatches. Friction fitting cannot substitute for
them. Absolute tracking calibration and complete MATLAB examples remain needed.

The overall M6B decision stays **M6B_QUALITATIVE_COMPARISON_ONLY**. A useful
external observable has been recovered, but no quantitative simulator agreement
or physical calibration is established. No new DEM attempt, model extension,
ML training or calibration is performed. All original M1-M6B scientific outputs,
model freezes and the M5 ledger remain intact. Original M6B reports describe
their release-time evidence; this dated supplement supersedes their README/text
unavailability and schema-unknown statements only where explicitly resolved here.

## Reproduction

Place the four original user-downloaded files, without editing, under
`data/raw/m6b/recovery/`. Keep all raw inputs out of Git.

```bash
conda activate pharmaflow-2d
python scripts/recover_m6b.py
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

The command is offline. It verifies provider checksums before parsing, enforces
the combined historical/recovery budget, preserves an immutable local receipt,
writes the derived Parquet separately to `data/processed/m6b/recovery/`, and
publishes only a compact CSV, provenance, summary and attributed figure under
`docs/results/m6b/recovery/`. Original audit outputs are not regenerated.

Verification: **209 tests pass** (202 original + 7 recovery tests), including
strict Taichi CPU/CUDA checks. All prior release files and 863 historical files
are hash-verified unchanged; the actual M5 ledger still has two charged attempts.
