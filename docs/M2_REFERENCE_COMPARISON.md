# M2 published reference audit and comparison boundary

Primary sources: [Yogi & Khakhar, PRE 114, 015418 (2026)](https://journals.aps.org/pre/abstract/10.1103/1ryw-6q89)
and [Zenodo record 20554446](https://zenodo.org/records/20554446), checked
17 November 2026 (Asia/Jakarta). The publisher abstract was accessible; the PDF
returned HTTP 401. Do not substitute assumptions from a related paper for this
paper's method. Units and normalization are not inferred from numerical magnitude.

## Reproducible inventory

`download_reference.py --subset all` verifies these published MD5 values:

| File | MD5 | Tables parsed |
| --- | --- | --- |
| quasi2D-sim.numbers | 00e53f48ae587beca990c5d1f709b24d | 4 |
| quasi2D-expt.numbers | c701fb415580d6ffa6d9fc9945bce0fe | 4 |
| 3D.sim.numbers | 00fff3dd1a07b3cb7966edfb744cae29 | 6 |

All three ZIP containers pass CRC testing; tables are read with
numbers-parser 4.22.2. No raw file is rewritten or redistributed.

| Subset | Sheets, each at D=2 cm and D=3 cm | Rows incl. header | Columns |
| --- | --- | --- | --- |
| quasi2D simulation | Profiles; 2D map | 201; 40001 | Profiles: y, phi, dphi, uy, duy, ay, day. Maps: x, y, phi, vx, vy, ay |
| quasi2D experiment | Profiles; 2D map | 161; 25601 | Same profile/map column names as above |
| 3D simulation | Profiles; 2D map; Cyl coord | 201; 40001; 501 | Profiles additionally sxx, syy, E. Maps additionally sxx, syy, sxy, E. Cyl: r, th, phi, vr, vt, srr, stt, srt |

Table names are `ua`/`va`/`vra`, except experimental D=2 cm profile table
`Profiles`. The machine-readable audit preserves each exact name, dimensions,
numeric counts/ranges, parsing coverage and nonnumeric examples in
[reference_audit.json](results/m2/reference_audit.json). None of the 14 table
headers contains particle IDs or timestamps. These are not trajectory tables.

## Parsing and unit limitations discovered in M2

Many cells are native strings containing several numeric fragments, e.g.
`-0.134409 0`, `.576967 0`, or `.000000 -0`. These are not valid single floats.
They are preserved as malformed/unresolved strings rather than silently joined,
split into invented columns, or converted by deleting whitespace. Some numeric
cells also produce suspicious ranges (negative candidate phi values, very large
candidate acceleration/error values). A checksum proves faithful download,
not correct column alignment or physical semantics.

For quasi2D simulation profiles only **63/200 rows** yield directly parseable
y/uy pairs under the strict parser; this is a biased subset of the domain.
Consequently the earlier M1 claim of a complete table schema is supported, but
it did **not** establish a clean numerical table. M2 explicitly records this
additional data-quality limitation. A reliable repair requires the authors'
source export or a verified Numbers interpretation, not heuristic guesses.

The sheet labels establish D=2 cm and D=3 cm (0.02 and 0.03 m). They do not
establish the x/y origin, coordinate normalization, speed units, acceleration
units, stress scale or E definition. `dphi`, `duy`, `day` cannot be called errors
or gradients solely from names. No nondimensional status is confirmed for these
columns. The audit assigns unresolved units/status explicitly, including numeric
cells, and flags fragmented strings. Unverified normalization could also explain
some out-of-range candidate fractions; these are warnings, not automatic deletions.

## What can be compared

The publisher describes a quasi-2D wedge with 3D particles and front/back walls;
its 3D variant uses periodic boundaries. Our model is uniform 2D disks with
assumed thickness and two side walls, a finite fill, no replenishment, and no
front/back-wall friction. Material parameters and averaging intervals are not
matched. The paper concerns exit-region velocity/acceleration and stress-driven
discharge; our small finite-fill ensemble is not that experimental protocol.

Candidate common observables are spatially averaged vertical velocity, flow
rate and local occupied fraction. Quantitative comparison is presently blocked
by units, alignment/fragmented cells, 2D/3D fraction definitions, averaging and
geometry differences. We therefore report **no reference RMSE, validation
score, calibrated flow-rate match, or full method reproduction**.

[reference_qualitative.png](results/m2/reference_qualitative.png) shows the strict
parseable y/uy subset on its own published-number axes, next to our solver's
center-strip mean |vertical velocity| in SI. Our bins use |x|<0.004 m,
0.05–0.25 s and 12 height bins over 0–0.06 m. The two panels use independent
axes; no overlay, scale fitting, coordinate flipping or missing-value repair is
performed. They illustrate spatially variable velocity in the inspected subset
and our solver, not physical agreement. Partial-domain descriptive values are
stored in `reference_descriptors.json` with that restriction.

The abstract's reported near-exit acceleration enhancement cannot be used as a
numerical target until the published ay scaling, coordinate sign, averaging and
geometry are verified. A Lagrangian particle acceleration is also not directly
interchangeable with a published Eulerian averaged acceleration profile.

## Reproduction and next evidence needed

```bash
python scripts/download_reference.py --subset all
python scripts/audit_m2_reference.py
python scripts/summarize_m2.py
```

Obtain a documented CSV/text export from the authors, establish the units,
origins, normalization, stress/fraction conventions, material/contact parameters
and averaging protocol, then match geometry or state a defensible transformation.
Only then select quantitative observables and uncertainty measures. M2 completes
the numerical/benchmark campaign and a reproducible audit; public-paper
calibration remains unresolved. This distinction is intentional and does not
authorize ML training or industrial claims.
