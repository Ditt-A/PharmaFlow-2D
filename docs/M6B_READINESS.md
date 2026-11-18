# M6B-A readiness

**M6B_QUALITATIVE_COMPARISON_ONLY**

The bounded data-access/schema/compatibility milestone is complete; physical
calibration is not. Source and evidence are released independently of historical
M1-M6A outputs. Starting commit: `aacf6ba545af6dba5f903dff4c4331552d742ce6`.

## Evidence and checks

- **202 tests pass**: 172 historical tests plus 30 M6B tests, with strict Taichi
  CPU/CUDA verification enabled. The actual provider-example tests all run on
  the release node; fresh checkouts without ignored raw inputs explicitly skip
  those three tests until bounded acquisition. No raw fixture is committed.
- All **863** snapshotted historical files, **86** frozen model candidates and
  **13** core package versions remain unchanged. No simulator/numerical parameter
  source is edited. Taichi remains **1.7.3** in the existing conda environment.
- M5's actual ledger has **two charged attempts**, unchanged, leaving four from
  its six-attempt ceiling. This differs from the older task description's five;
  neither historical ledger state nor budget is reset. No demo was consumed.
- **Zero** new campaign/demo solver attempts, ML fits or physical calibrations.
  Existing required physics verification tests are separate from campaign runs.
- Seven of twelve conservative curated-file reservations charged; six successes,
  one failed original Dryad README. Three successes are author software, two
  are Delft documentation/metadata and one is reused experimental Numbers data.
- Retained curated inputs: **8,140,953 bytes**. New author software: **1,196,267
  bytes**. New experimental measurements: **0 bytes**. Reused genuine experimental
  profile container: **6,942,628 bytes**, verified by provider MD5 and local SHA-256.
- Node acquisition/catalog payload: **1,305,278 bytes**; known workstation
  discovery metadata: **231,490 bytes**. Combined known scripted payload:
  **1,536,768 bytes**, well below 200 MB. A conservative node reservation of
  **17,132,880 bytes** covers caps/error reads; actual errors are not data.
- Dryad README **403**; documented token-required API not retried anonymously.
  Delft author metadata query **503**, recorded without retry. Large archive
  contents remain uninspected and no archive is downloaded.

See the [audit summary](results/m6b/audit_summary.json),
[access report](M6B_DATA_ACCESS.md), [schema report](M6B_EXPERIMENTAL_SCHEMA.md),
[compatibility decision](M6B_COMPATIBILITY.md) and
[categorical evidence diagram](results/m6b/compatibility_gates.png).
The diagram is an evidence checklist, not experimental physical-agreement data.

## What was recovered

The official author software reveals a candidate MATLAB structure and warns of
coordinate swapping/future-state selection. It supplies no actual MAT run and
does not verify tracking units. Delft provides five genuine acquisition rows
with **400/600 Hz** annotations, including a catalog conflict; these are not mass
or velocity histories. Yogi provides four actual experimental spatial tables;
all 320 profile rows are preserved with nullable native floats, only 86 complete
y/uy pairs parsing directly. Units, normalization and coordinate mapping remain
unresolved. No particle IDs/time histories are present in those tables.

There are **zero quantitatively comparable physical observables** today. No
agreement residual, calibration curve, experimental event count or measured
velocity distribution has been invented. No particle-trajectory visualization
is exported because no experimental particle trajectory was obtained.

## Next decision, not execution

Send the [prepared request](M6B_DATA_REQUEST.md) only through a separately
authorized human communication. Request original README/dictionary/session
metadata and six prespecified no-fixed-particle MAT flows across three outlets,
nine files total and at most 200 MB. Do not replace inaccessible measurements
with notebook raster outputs, invented units or synthetic trajectories.

Only after real raw units, geometry, boundary definitions, uncertainty and session
dependence are established should a separate design review consider
polydispersity, measured flat-floor geometry and confinement. These are plausible
extensions, not proof that the existing strict-disk solver can reproduce the
experiment. Material contact parameters need independent measurements; fitting
friction against one outlet curve cannot identify all missing physics.

**A future calibration stage is not justified with current inputs.** Proceed, if
desired and separately authorized, with a clearly labeled **uncalibrated
engineering simulation study**. Preserve all historical held-out cohorts and
M5 dashboard budgets. This milestone launches no subsequent simulations, fitting,
training or design optimization.

## Exact reproduction

```bash
cd ~/adit/PharmaFlow-2D
conda activate pharmaflow-2d
python scripts/acquire_m6b.py --delft-catalog
python scripts/audit_m6b.py
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

First acquisition reserves all IO before access, rejects oversized/unreviewed
routes, verifies provider checksums and records failures. Subsequent execution
checks immutable successes and skips failures. Catalog discovery is four bounded
public metadata requests, at most 4,032,768 reserved bytes, with no following of
advertised experiment downloads. The audit is offline and reproducible from raw
inputs; derived tables/figures are written only under new M6B paths. Raw/large
derived files stay out of Git. Manifest-only historical preservation claims
require the original node's preflight snapshot, never an invented fresh snapshot.
