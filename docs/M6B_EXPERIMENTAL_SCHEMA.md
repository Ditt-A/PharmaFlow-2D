# M6B-A experimental schema recovery

No particle-tracking MATLAB file was acquired. Accordingly there is no validated
MATLAB measurement parser or experimental particle animation in this release.
The recovered code contract is explicitly **code evidence only**; actual accessible
examples test the Delft metadata and literal Numbers parsers. Raw files are immutable.

## Cornerstones candidate contract

Static inspection of the official author software establishes:

| Code-evidenced field | Supported interpretation | Unresolved |
|---|---|---|
| `trackinfo` / `tinfo_header` | Numeric matrix with column names selected dynamically from header | Actual arrays, shapes, missing markers and run-specific headers unverified |
| Comment-named columns `x,y,timestamp,frame,species,dx,dy,ID` | Author's proposed tracking attributes | Position, timestamp and velocity units; coordinate origin/sign; ID lifetime |
| `parameters` structured fields | Loader copies dynamically named parameters; uses `rads,D,cpt` and outlet endpoints | Actual values, species fractions, dimensions and unit calibration |
| `massflow` structured fields | Code elsewhere uses `M,T` | Mass unit, time alignment, boundary definition and all field names |
| `frameinfo` | Dynamically named frame metadata | Header names, recording duration, censoring and confirmation coverage |
| Optional `fixedParticle` | Code substitutes zero if absent | Absence cannot establish a verified no-fixed-particle experimental condition |

The renderer plots `(y,x)` and `(dy,dx)` and reverses its displayed vertical axis.
These names therefore do not establish PharmaFlow's x-horizontal/y-up convention.
Raster loops and numerical magnitudes do not establish a physical pixel conversion.
The documented camera rate is 130 frames/s, but no actual frame/timestamp alignment
has been verified; `dx,dy` are not assigned m/s or pixels/frame.

`ClassSelectionScript.py` uses future final-arch positions and displacement/mass
thresholds to select states. These classes are neither causal monitor outputs nor
M3 horizon labels. It exports selected state arrays, not an independently validated
full flow trajectory. We never execute this script.

Notebook cell 1 loads `BinCenters.txt`, `Dimensionless_M.txt` and
`Dimensionless_M_std_error.txt` for its fixed-particle analysis. This improves
filename context over M6A, but supplies neither inaccessible values nor a verified
normalization/uncertainty definition. Other cells require unprovided MAT files,
filename lists and pickle caches. Saved raster outputs are not used as measured
positions or velocities. A movie-output frame rate in code is not camera sampling.

See [candidate schema](results/m6b/dryad_candidate_schema.json). Complete static
line evidence, including software SHA-256, is stored locally in
`data/processed/m6b/author_schema_evidence.json`. No untrusted pickle is loaded.

## Delft actual example

Provider MD5 `da45f2071241856a0173b2ecd9732dbb` verifies the actual 345-byte
`info_alp_20_d_100.txt`. The explicit framerate header supports five local run
indices and mixed 400/600 Hz annotations, despite the catalog's 600 Hz description.
This inconsistency is preserved. The parser returns `run_index`,
`recorded_rate_value`, `sampling_hz`, `header_verified`, provenance and uncertainty
notes. Headerless files are not promoted to Hz. The selected record's nominal
20 degree angle and 100 mm opening are catalog geometry annotations; angle origin,
full 3D apparatus, particle size distribution and pixel calibration remain unknown.

`timestamp_s`, `particle_id`, `mass_discharge_kg_s`, `velocity_m_s` and
`coordinate_units` remain null. No positions or load-cell observations are present
in this text. Parsed acquisition metadata are not granular-flow measurements.
The compact [schema/example rows](results/m6b/delft_acquisition_schema.json) attribute
Fransen, Schott and Langelaar and retain CC BY-SA 4.0.

## Yogi actual example

Provider MD5 `c701fb415580d6ffa6d9fc9945bce0fe` verifies the 6,942,628-byte
experimental Numbers container. Its four original tables remain separate: two
160-row profiles and two spatial maps. The [schema](results/m6b/yogi_experimental_schema.json)
records literal table/column names, row counts, units status and lack of time/ID fields.

All **320 profile rows** are exported with source sheet/table/row and input SHA-256.
For every column, `*_raw` preserves literal source content and `*_native` holds a
finite float only when the whole original value parses directly. Nonparseable,
missing, NaN/Inf or fragmented cells are nullable, never silently removed/repaired.
Only **43/160 y/uy pairs per outlet**, 86 total, parse directly. This incomplete
subset cannot represent an unbiased physical velocity distribution. A row index
is not a frame/time identifier. No units, normalization, axis flip or interpolation
is applied. Maps are inventoried, not converted to disk packing fractions.

Derived paths:

- `data/processed/m6b/yogi_native_profiles.parquet`
- `data/processed/m6b/delft_acquisition_metadata.parquet`
- `data/processed/m6b/author_schema_evidence.json`

The [processed manifest](results/m6b/processed_manifest.json) records their sizes
and hashes. No early-warning labels or source event counts are invented. Particle
frames, outlet trajectories, crossing histories and source event timelines cannot
be drawn from these inputs. The M5 genuine DEM scenes remain available separately;
they are not experimental evidence and are not overlaid here.
