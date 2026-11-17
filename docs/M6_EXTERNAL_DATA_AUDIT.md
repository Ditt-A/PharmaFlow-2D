# M6A external data audit

Decision: **M6A_LIMITED_COMPARISON_ONLY**. Audit date: 17 November 2026.
No material parameter was fitted, no campaign/demo DEM attempt was launched and
no ML model/policy was trained or selected. Existing physics verification tests
were rerun. Public availability, measurement
extractability and physical compatibility are separate questions.

The audited `main` starts at `04960ad8801f166fa76fd7083c80f435c5428d7a`.
All 149 historical tests passed before changes. Historical trajectories,
labels, splits, predictions, models and M5 assets are preserved. The live M5
ledger already contained **two** charged attempts at M6A preflight, rather than
the one recorded at the M5 release. M6A neither consumes nor resets its remaining
four attempts; those remain reserved for dashboard use. M5 reports remain as
historical records of their original release.

## Access, provenance and reuse

| Source | Actual access observed | File inventory | Reuse conditions |
|---|---|---|---|
| [Dryad Cornerstones](https://doi.org/10.5061/dryad.cvdncjtb5) | Dataset/version/file metadata HTTP 200. Four small public UI downloads HTTP 403 on node and workstation; API download test HTTP 401. Publicly advertised files do not establish successful client access. | 7 files / 17,411,556,118 bytes: 3 ZIP archives of MATLAB structures, README (5,424B), three 425B numeric text files. No archive downloaded. | Dataset API specifies CC0 1.0. Cite Hanlan, Dillavou, Durian & Liu and retain provenance. Article/preprint licenses are separate. |
| [TU Delft collection](https://doi.org/10.4121/C.6415736) | Resolves to versioned collection `10.4121/fa7544d6-14fd-4372-a81f-e2e1b4a44832.v1`; collection and seven linked child records accessible. All 14 selected README/info files downloaded and MD5 verified. | 56 listed files in those seven 100mm-outlet children, summing 183,047,314,185 advertised bytes, mostly `.7z` TIFF/calibration archives. This is not a verified uncompressed TIFF size or the complete collection's size. | Each inspected child specifies CC BY-SA 4.0. Attribute Fransen, Schott & Langelaar; metadata-derived CSV/figure content carries that license. The collection itself does not separately specify a license. |
| [Yogi & Khakhar](https://zenodo.org/records/20554446) | Record API accessible; all three existing local files reverified against published MD5 plus ZIP CRC. No redownload needed. | 30,393,158 bytes in three `.numbers` containers; 14 tables, of which four are experimental. | Record API now establishes CC BY 4.0. This resolves the previously unverified license without rewriting M2 evidence. Attribute Yogi & Khakhar and identify derived plots. |

Exactly **480,530 bytes** of successful new metadata/text/preprint content are
cached in `data/raw/m6/`, including **13,794 bytes** of Delft README/acquisition
text. The first bounded fetch transferred 481,002 bytes including four 118B
HTTP-error bodies. No error body was saved as a valid data file. Dryad numeric
content retrieved: **0 bytes**. Cached Zenodo reuse: **30,393,158 bytes**.
Exploratory workstation metadata copies are separate ignored discovery material,
not additional ingested measurements. The reported ingest sizes come from the
node's frozen allowlist and [provenance manifest](results/m6/provenance_manifest.json).

The fetcher permits HTTPS to four named hosts, files ≤1MB, a 3MB total new-fetch
budget and only the explicit small-file list. It rejects archive URLs, oversized
streams, size mismatches and failed published checksums. Failed access remains
in the manifest. Never download the entire 17.41GB Dryad release to work around
these restrictions. Seek a provider-supported small subset or working public
access. No claims are made about why the tested endpoints reject downloads.

Published checksums exist for all 66 inventoried data files. Four inaccessible
Dryad text checksums cannot be verified from metadata alone. The fourteen Delft
text checksums and three cached Zenodo file checksums are verified; large archive
contents are not. SHA-256 of received metadata provides local integrity, not
independent proof of measurement validity. See [file_inventory.csv](results/m6/file_inventory.csv).

## A. Cornerstones circular-grain experiments

The Dryad metadata describe approximately 50,000 flow-to-clog records, MATLAB
structures with positions, radii/species, frame indices, tracked IDs and velocities,
plus outlet and ejected-mass information. Actual MATLAB field names, coordinate/
velocity units and frame coverage remain **unverified** because the README and
raw structures were not retrieved. The three numeric summary filenames alone
do not establish their axes or meanings; they are not treated as discharge rates.

The authors' [primary preprint, Methods II.1](https://arxiv.org/html/2407.05491v1#S2.SS1)
reports circular polyethylene disks with diameters 6.0/7.4/8.6mm, physical thickness
3.18mm, density 0.94g/cm³, front/back spacing 4.4mm, vessel width 22.7cm,
height 50cm and approximate fill height 35cm. These are reported experimental
values, not our measurements. The outlet groups are D/dL=3.61,3.74,3.86,3.98,4.15,
where dL is the **largest** diameter; they must not be relabeled D/mean-diameter.
The floor/opening differs from the current wedge; a matched numeric inclination
and boundary specification have not been established. Species fractions,
particle/sidewall/front-back friction, restitution and roughness are unresolved.

Sampling is reported as 130fps (7.692ms/frame). Tracking precision is reported
as 0.14mm in Methods; Appendix C uses 0.3mm in its final-position criterion.
These statements serve different definitions and are not combined into an
invented uncertainty estimate. The preprint also prints a gravity value with an
inconsistent cm/s² unit in Appendix A; M6A does not silently repair or use it as
a numerical conversion. Obtain clarified units and the final methods/source
export before any quantitative comparison.

An exciter breaks the prior arch; grains recirculate through a separate airflow
return. Clogging is confirmed after five seconds without exit, while mass is
inferred from grains passing a semicircular observation boundary. That boundary
is not automatically equivalent to our unique first downward crossing of y=0.
The preprint reports >35,000 single-outlet flows, >7,000 other-outlet flows and
>13,000 fixed-grain experiments, with analysis-specific exclusions. Those rounded
statements are not independently verified record counts. No new independent-
event denominator is inferred from them. Reused grains, material aging and
experimental sessions also matter for statistical independence.

This is the closest particle-shape candidate, but polydispersity, confinement,
flat-floor/sidewall geometry, recirculation and forced startup are unmatched.
Current monodisperse finite-fill wedge runs cannot quantitatively calibrate it.

## B. Delft gravel experiments

The [collection description](https://data.4tu.nl/collections/fa7544d6-14fd-4372-a81f-e2e1b4a44832)
advertises load-cell measurements and high-speed images across nominal angles
20,30,45,60,75,82.5,90° and openings 50,75,100,150,200mm. It states 201 experiments,
but summing the **35 listed repetition counts gives 231**. The seven currently
linked children inspected here cover 100mm with five run annotations each,
not the complete advertised parameter grid. Do not infer missing dataset links
or replace 201 by 231 as an independently verified experiment count.

All 56 inspected file entries are README/info files and TIFF/calibration `.7z`
archives. No load-cell time-series table or processed velocity field was located
in this inventory. This does not prove those measurements do not exist elsewhere
or inside an uninspected archive. Their location, units and calibration are
unresolved. README points to Chapter 2 of [Fransen's dissertation](https://doi.org/10.4233/uuid:ad7999d2-5058-4a9d-8688-be6c91f41485)
for equipment details. Particle size distribution, density, friction, full 3D
geometry and angle reference are not established by the retrieved dataset files.
The thesis is a further primary-source lead, not a license to invent missing
dataset metadata. Nominal angles are not converted to our angle from vertical.

Frame-rate evidence is inconsistent. Twenty-five run rows have an explicit
`framerate` header and values 300/400/600; **six** disagree with their own record's
catalog value. Ten rows in the 30°/45° info files lack a header; their numeric
annotations remain provisional rather than silently becoming Hz. Pixel-related
columns and `t_s` are not assigned unverified physical meanings. The
[acquisition audit](results/m6/acquisition_metadata.csv) retains these distinctions.
Repetitions and calibration pictures are provided, but uncertainty in physical
PIV scale, synchronization and sensor response is not quantified here.

Gravel is three-dimensional and irregular; visible-surface PIV is not a complete
particle-center trajectory or internal contact network. Projected surface
coverage is not a 2D area or 3D volume fraction. Load-cell support force during
acceleration is not automatically hopper mass or discharged mass. Broad flow
and inclination trends may be compared qualitatively, after definitions are
resolved; fitting disk friction to compensate for missing 3D shape is invalid.

## C. Existing wedge reference

The unchanged [M2 audit](M2_REFERENCE_COMPARISON.md) inventories four experimental,
four quasi-2D simulation and six 3D simulation tables at D=2/3cm. They contain
spatial profiles/maps, without particle IDs or time series. Candidate columns
include y, phi, uy, vx, vy and ay, but units, coordinate sign/origin, normalization,
error-column semantics, averaging and fraction definitions remain unresolved.

Fresh inspection of the **experimental** file yields only **43/160 directly
parseable y/uy pairs per outlet**. Fragmented strings are preserved, not joined,
split or repaired. The parseable subset is biased/incomplete. M6A shows native
numbers on their own axes, with no overlay, coordinate flip, scale fit, residual
or physical-agreement score. This differs from the older M2 illustrative plot
of the simulation subset; both historical files/results remain intact.

## Operational event observability

The M5 taxonomy is reused unchanged. Empty cells/unknown counts are **not zero
external events**. No external labels are combined with synthetic labels.

| M5 category | Dryad | Delft | Yogi |
|---|---|---|---|
| Startup blockage | Forced unclogging starts acquisition; startup coverage/denominator unresolved. | Requires complete startup, retained material and arch evidence; no labels retrieved. | Not observable from profiles. |
| Post-discharge arch | Flow-ending clog reported; five-second criterion differs from M3. | No event annotations/interior contact graph retrieved. | Not observable. |
| Established-flow arch | Potential with full reconciled crossing history and preceding-flow test; not yet established. | Surface PIV alone cannot count the M5 individual passages. | Not observable. |
| Temporary interruption | Metastable pauses described; original ML cleaning excludes some static flowing frames. Raw full histories must be inspected. | Possible in complete recordings after timing review; not measured here. | Not observable. |
| Completed discharge | External **Emptied does not mean empty hopper**; an arch remains and the apparatus recirculates. | Needs full-fill/mass history, not an outlet image alone. | Not observable. |
| Censoring | Truncated/nonclogging inclusion and stored future coverage need schema audit. | Coverage/endpoints unresolved. | No temporal outcome available. |

Dryad may eventually support established-flow interruptions and advance-warning
studies, but no external early-warning validation has been performed. Its
microstate classes, cleaning, five-second confirmation and observation boundary
must first be reconciled with M3/M5. Source classes named Clogged/Clogging/Emptied
are not interchangeable with our horizon labels. See
[operational_event_scope.csv](results/m6/operational_event_scope.csv).

## Reproduction

```bash
conda activate pharmaflow-2d
python scripts/audit_m6_sources.py --fetch-small  # bounded first ingest; expected Dryad failures recorded
python scripts/audit_m6_sources.py               # offline cache/checksum verification
python scripts/benchmark_m6.py                   # existing permitted training trajectories only
```

Source metadata/facts and URLs are versioned in `configs/m6/external_sources.json`.
Only compact inventories, hashes, reports and figures enter Git. No large archive,
native Numbers container, MATLAB data or generated trajectory array is committed.
