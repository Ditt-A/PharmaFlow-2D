# M6A readiness decision

**M6A_LIMITED_COMPARISON_ONLY**

M6A establishes a reproducible source audit and seven benchmark definitions.
It establishes **no matched quantitative physical validation, fitted material
parameters, external early-warning performance or industrial readiness**.
External calibration is currently blocked by access/measurement definitions
and model mismatch; qualitative physical comparison remains possible.

## Evidence

- Final suite: **172 tests passed** (149 historical + 23 M6), including strict
  Taichi CPU/CUDA checks. One existing Taichi locale deprecation warning remains.
  All **805** snapshotted historical files and 86 frozen candidate checks remain
  unchanged; the M5 ledger is identical before/after and all 13 core package
  versions remain unchanged. No new dependencies or system changes were needed.
- Starting state: `main` at `04960ad8801f166fa76fd7083c80f435c5428d7a`, clean,
  correct remote and 149 passing historical tests, including strict Taichi checks.
- Three sources audited; 66 advertised data files inventoried. Downloaded/cached
  successful M6 text/metadata/preprint content: **480,530B**, including **13,794B**
  in fourteen MD5-verified Delft small files. No large archives downloaded.
- Dryad metadata are public; four small UI downloads returned HTTP 403 on both
  node and workstation, and an API download test returned 401. Zero raw Dryad
  measurement bytes ingested. Its particle shape is promising, but mixture,
  geometry, friction and observation definitions are unmatched.
- Delft has seven linked 100mm children and 56 inspected file entries, primarily
  TIFF `.7z` archives. Its collection's 201 total conflicts with a sum of 231 in
  35 listed repetition rows. Twenty-five acquisition rows have a frame-rate
  header; six conflict with the corresponding catalog, and ten other rows are
  headerless. No load-cell series or ready PIV field was located in this inventory.
- All three existing Zenodo files (**30,393,158B**) pass their MD5 and ZIP checks;
  the record specifies CC BY 4.0. Only 43/160 y/uy pairs per experimental outlet
  parse directly. Units, density definition and averaging remain unresolved.
- Training-only scaling support: **39 runs**, 15 physical configurations,
  maximum fill 50 grains, maximum post-buffer crossings 29, **0 qualified
  sustained-flow windows**. No test/locked data are used for fitting or selection.
- No new campaign/demo DEM attempts, ML training, physical fitting, label changes or guard
  relaxation. M5's live ledger already had two charged attempts at preflight;
  M6A does not consume/reset the remaining dashboard allowance.

## Readiness by question

| Question | Answer |
|---|---|
| Can number/mass/normalized flow be computed consistently? | Yes for the existing solver with known masses; conversions and boundary conventions are tested. This is measurement plumbing, not external validation. |
| Can numerical and physical errors be separated conceptually? | Yes; existing numerical evidence is reported separately from model form, parameters and experimental uncertainty. Their full magnitudes are not all known. |
| Can a physical discharge rate or velocity residual be reported now? | No matched external target with verified definitions and uncertainty was established. No residual/RMSE or calibration score is computed. |
| Can Beverloo coefficients or an exponent be fitted now? | No: short depleted fills, few crossings, unmatched external data and potential friction/geometry effects prevent a defensible fit. |
| Can established-flow warnings be externally validated now? | No. Dryad may provide useful full histories, but access, boundary and event definitions need reconciliation. Delft has no retrieved labels; Yogi has no time series. |
| Is an external calibration workflow ready? | A conditional protocol, bounds, holdout and uncertainty plan are prepared. Execution is gated on measurements and engine compatibility. |

## Reproduction and visual evidence

```bash
conda activate pharmaflow-2d
python scripts/audit_m6_sources.py --fetch-small
python scripts/audit_m6_sources.py
python scripts/benchmark_m6.py
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

The first command is bounded and records expected inaccessible Dryad files.
Subsequent offline audits verify caches without new downloads. Complete existing
training NPZ and cached reference files are needed; no automatic generation or
training fills missing assets.

Figures in `docs/results/m6/` include compatibility, actual simulated discharge,
native experimental profile limitations, scaling support, actual M2 numerical
convergence, a conceptual uncertainty diagram, conceptual identifiability,
actual acquisition metadata and a readiness checklist. Numeric plots identify
their actual data source; diagrams that are conceptual are labeled accordingly.
See [source audit](M6_EXTERNAL_DATA_AUDIT.md), [benchmark protocol](M6_PHYSICS_BENCHMARKS.md),
[calibration feasibility](M6_CALIBRATION_FEASIBILITY.md) and
[figure manifest](results/m6/figure_manifest.json).

## Next stage

Recommend the bounded, data-first M6B proposal: ≤12 curated experimental flow
files, ≤200MB, zero initial solver attempts, then a separate compatibility review.
A conditional ceiling of 12 later solver attempts is a proposal requiring
separate authorization, with numerical/resource gates and no automatic retries.
Do not proceed to advanced ML or claim pharmaceutical/industrial applicability
from these uncalibrated dry disks.
