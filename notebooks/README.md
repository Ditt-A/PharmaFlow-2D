# Notebooks (planned)

Create notebooks only once their upstream scripts are reproducible:
- `00_reference_data_audit.ipynb`: inspect Zenodo published `.numbers`, units and shapes
- `01_dem_smoke.ipynb`: visualize a small, validated headless DEM run
- `02_validation.ipynb`: compare meaningful quantities with published data
- `03_feature_baselines.ipynb`: build non-leaky run-wise ML baselines
- `04_ai_early_warning.ipynb`: temporal early-warning experiments

Notebooks must **call code in `src/pharmaflow/`**, not duplicate the solver or model implementation.
