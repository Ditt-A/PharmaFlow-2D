# M6B-A external data access

Decision: **M6B_QUALITATIVE_COMPARISON_ONLY**. Audit: 18 November 2026.
Starting main: `aacf6ba545af6dba5f903dff4c4331552d742ce6` (M6A).
This is a bounded recovery/schema audit, not calibration or a new simulation campaign.

## Acquisition and provenance

The immutable plan is [acquisition_plan.json](../configs/m6b/acquisition_plan.json).
Every curated success is checked against provider size and MD5/SHA-256, then
assigned a local SHA-256. Raw inputs and ledgers live under `data/raw/m6b/`;
derived data live separately under `data/processed/m6b/`. Neither enters Git.
The compact [manifest](results/m6b/acquisition_manifest.json) records provenance,
timestamps, endpoints, licenses, failures, reuse and checksums. A failed HTTP
response is never saved as a successful measurement file.

| Curated item | Bytes retained | How obtained | Meaning |
|---|---:|---|---|
| Cornerstones `ClassSelectionScript.py` | 5,089 | New HTTP 200; provider MD5 verified | Author software, not experimental observations |
| Cornerstones `FlowClass_WithFixedGrain.py` | 16,444 | New HTTP 200; provider MD5 verified | Candidate MATLAB loader/analysis code; never executed |
| Cornerstones `FixedParticleFigure.ipynb` | 1,174,734 | New HTTP 200; provider MD5 verified | Notebook source inspected statically; outputs are not raw data |
| Delft `README.txt`, 20 degree / 100 mm record | 1,713 | Checksum-verified M6A cache copied | Documentation |
| Delft `info_alp_20_d_100.txt` | 345 | Checksum-verified M6A cache copied | Five acquisition annotations, not discharge measurements |
| Yogi `quasi2D-expt.numbers` | 6,942,628 | Checksum-verified historical cache copied | Actual spatial-profile/map container, no particle trajectories |
| Dryad original `README.md` | 0 | HTTP **403**, 118-byte error response | Acquisition failed; no content/checksum verification claimed |

Six curated files retained: **8,140,953 bytes**. Seven curated reservations,
including the failed README, out of twelve. Newly transferred author software:
**1,196,267 bytes**. Newly transferred experimental measurement data: **0 bytes**.
The experimental Numbers container is a verified reuse, not newly recovered
particle tracking. No `.mat`, ZIP, `.7z`, image sequence or full release downloaded.

The plan's observed response payload is **1,269,263 bytes**, including metadata
and the failed response. The separate four-request Delft catalog ledger adds
**36,015 bytes**, including its 503 response: **1,305,278 bytes** for the node
pipeline. Its conservative combined reservation ceiling is **17,132,880 bytes**,
including terminal-chunk allowances and failed requests, below 200,000,000.
Eight exploratory workstation metadata responses total a further **231,490 bytes**
(provider API guide, author record metadata, search page/JS and two search responses).
Their individual hashes/URLs are in `workstation_discovery_manifest.json`.
Known scripted transfer including discovery is **1,536,768 bytes**; experimental
payload transfer remains zero. Headers and browser-tool metadata are not measured
experimental payload. No multi-GB mirroring or range extraction occurred.

## Dryad: access and author distribution

[Dryad](https://doi.org/10.5061/dryad.cvdncjtb5) metadata remain public. The inspected
version is 376462 / versionNumber 9: seven advertised files, 17,411,556,118 bytes.
Three large archives contain the advertised MATLAB runs. They were not requested.
The four small original text files remain inaccessible from this client.

The current single README request to
`https://datadryad.org/downloads/file_stream/4172597` returned 403. M6A's earlier
small-file 403 and download-API 401 attempts remain historical records, not new
successes. Official [API-account documentation](https://github.com/datadryad/dryad-app/blob/main/documentation/apis/api_accounts.md)
requires a token for file downloads; metadata access is a different capability.
No token was available. No token-required download API was probed again, no account
created, and no alternate route used to evade the denial. Failed reservations
remain charged; rerunning the script does not retry them.

The authors' official [Zenodo software distribution](https://zenodo.org/records/10895419),
linked to this Dryad release, legitimately provides the three small software files
above. It contains **no MATLAB run**. Its MIT software license is separate from
the Dryad raw-data CC0 license. Static notebook inspection reveals dependencies
on unavailable MAT files and pickle caches; these are not embedded experimental
inputs. No author code or pickle was executed/unpickled and no output image was
digitized as a measurement. See the [ready-to-send request](M6B_DATA_REQUEST.md);
it has **not** been sent.

## Delft: acquisition metadata versus measurements

[Collection](https://doi.org/10.4121/C.6415736): M6A's seven 100 mm child inventories
remain unchanged. This milestone also uses the official search UI's documented-in-
JavaScript public POST `/v3/datasets/search`, with title/description/tag/author
scope, AND query, page 1 and page size 20. The hopper query returns additional
150/200 mm recordings. The node's author query returns **503**, 197 bytes, and
is not retried. This is temporary server failure, not a successful data response.
Earlier workstation author metadata search returned 200; it is recorded separately.

Two advertised public article APIs were inspected: the 20 degree / 150 mm record
`ea3e3e6e-67ce-4629-a889-be0b04c735dd` and combined 200 mm record
`4fc30415-6463-490b-ba87-032ae94b39d1`. Their **16 file entries** contain TIFF/
calibration `.7z` archives and README/info text; no mass-history table or calibrated
PIV vector file is listed. The 150 mm calibration archive alone is 17,824,596
bytes, but cannot provide a discharge measurement by itself and is not downloaded.
The observation archives are multi-GB and outside the budget. See
[additional inventory](results/m6b/additional_delft_inventory.csv).

This does not establish that load-cell/PIV data do not exist elsewhere or inside
archives. It establishes that this bounded search did not recover such measurements.
Record descriptions, repetitions and a frame-rate annotation are not a mass-flow
history. The original 201-versus-231 catalog inconsistency remains unresolved.

## Existing Yogi reference

[Zenodo 20554446](https://zenodo.org/records/20554446) remains CC BY 4.0. Only the
experimental file is copied into M6B after published MD5 verification. Its four
tables are inspected without changing M2/M6A artifacts. Units, coordinate mapping,
normalization, averaging and error definitions remain unresolved. No source value
is reconstructed from its magnitude, and fragmented strings remain unchanged.

## Reproduce

```bash
conda activate pharmaflow-2d
python scripts/acquire_m6b.py --delft-catalog
python scripts/audit_m6b.py
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

On the release node these commands reuse verified raw inputs and skip charged
failures without network retries. On a fresh checkout they attempt the bounded
public allowlist; a previously absent cached Numbers file may be downloaded from
its official endpoint within the same cap. New provider responses can differ;
local integrity manifests must never be presented as immutable provider promises.
An interrupted lock/reservation requires inspection, not deletion/reset to retry.
No credentials, messaging, DEM execution or training is part of these commands,
apart from the required historical physics verification tests.
