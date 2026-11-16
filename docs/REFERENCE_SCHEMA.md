# Published simulation file: first schema audit

Inspected on node680 using `numbers-parser==4.22.2`, Python 3.11.18.
Source: https://zenodo.org/records/20554446, simulation subset only.

`quasi2D-sim.numbers` is 10,938,165 bytes, has 445 ZIP entries, passes ZIP CRC
testing and matches the published MD5 `00e53f48ae587beca990c5d1f709b24d`.
The source is immutable in `data/raw/zenodo_20554446/`; no raw data is committed.

Actual sheets/tables read from the container:

| Sheet | Table | Rows incl. header | Columns | Header values |
| --- | --- | --- | --- | --- |
| D=2 cm: Profiles | ua | 201 | 7 | y, phi, dphi, uy, duy, ay, day |
| D=2 cm: 2D map | va | 40001 | 6 | x, y, phi, vx, vy, ay |
| D=3 cm: Profiles | ua | 201 | 7 | y, phi, dphi, uy, duy, ay, day |
| D=3 cm: 2D map | va | 40001 | 6 | x, y, phi, vx, vy, ay |

The profile/map interpretation follows the sheet labels and column headers.
There are no particle ID/time columns in these four tables, so they are not
assigned as framewise particle trajectories. The 40000 data rows must not be
interpreted as 40000 moving particles. Many numeric-looking cells are stored as
strings; preserve that fact before choosing conversion and missing-value rules.

The headers alone do not establish normalization, coordinate origins, velocity
units, phi conventions or the meaning of d-prefixed columns. In particular,
`D=2 cm` in the sheet name is not evidence that every coordinate column is in
centimeters. Those details require the paper/methods and careful grid inspection
before comparisons. The published system is quasi-2D with 3D particles; our
strictly 2D disks have a different mass/geometry model. No quantitative validation
against these tables is claimed for M1. Experimental/3D subsets remain unaudited.

Reproduce and inspect all collected previews and cell types:

```bash
python scripts/download_reference.py --subset sim
python scripts/inspect_reference.py
```

The complete generated schema report stays in the ignored local path
`outputs/metrics/reference_schema.json`.
