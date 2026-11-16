# Data locations

Raw reference data downloaded through `scripts/download_reference.py` goes in `data/raw/zenodo_20554446/`.

- `data/raw/`: immutable third-party original files; do **not** push.
- `data/processed/`: audited/derived reference tables with a provenance manifest; do **not** push.
- `data/simulated/`: generated DEM runs, complete trajectory arrays and run-level metadata; do **not** push.

Only source code, lightweight configs, documentation, reproducibility manifests, and synthetic toy tests belong in the repository.

Do not infer physical units, time indexing, particle IDs, or variable definitions from `.numbers` filenames alone. First run `scripts/inspect_reference.py`, consult the paper, and document a parser specification.
