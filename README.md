# PharmaFlow-2D

**DEM-based granular hopper simulation and AI-assisted flow diagnostics** — a research-oriented proof of concept for powder handling in pharmaceutical manufacturing.

> **Status:** preparation/scaffolding only. No validated solver, trained AI model, or industrial performance claims yet.

## The engineering problem

Granules in a hopper can flow intermittently or form a stable arch above the outlet (clogging). We aim to (1) simulate particle motion using a **2D Discrete Element Method (DEM)** solver; (2) validate aggregate flow behavior against published DEM/experimental measurements; (3) generate multiple independent operating-condition trajectories; (4) predict early clogging risk; and (5) compare design settings within the solver's validity range.

**Why DEM, not CFD?** This version models contacting dry particles. A continuum CFD solver is better for liquid mixing or fluid pressure/heat transfer; a coupled CFD–DEM model is out of scope.

## Primary reference paper and open dataset

Yogi, J. & Khakhar, D. (2026). *Gravity-driven granular flow from a wedge-shaped hopper: Analysis of the exit region.* Physical Review E 114, 015418. DOI: [10.1103/1ryw-6q89](https://doi.org/10.1103/1ryw-6q89).

Official public reference dataset: [Zenodo 20554446](https://zenodo.org/records/20554446) (DOI: [10.5281/zenodo.20554446](https://doi.org/10.5281/zenodo.20554446)).

Published files (about 30.4 MB in total):
- `quasi2D-sim.numbers` — quasi-2D simulation data (~10.9 MB)
- `quasi2D-expt.numbers` — quasi-2D experimental data (~6.9 MB)
- `3D.sim.numbers` — 3D simulation data (~12.5 MB)

**Scientific limitation:** The study uses quasi-2D geometry and **3D DEM particles**, not the same thing as a strictly 2D disk solver. The `.numbers` layout and whether it includes framewise trajectories must be inspected before assigning column meanings. We use these files as reference data for comparisons where quantities are comparable; we do not promise exact reproduction of the authors' full DEM solver.

Secondary solver inspiration: [Taichi DEM example](https://github.com/taichi-dev/taichi_dem). Its simple example omits tangential contact force and particle rotation; these are required for a stronger research-grade DEM implementation.

## Requirements

- JupyterHub in Docker; **no sudo/root/Docker daemon required**
- User-writable workspace plus `conda` or `pip`
- NVIDIA A100 80GB optional for acceleration, provided CUDA is exposed to the notebook process
- 4+ GB free workspace initially (reference data is small; future rollouts can grow)
- No solver installation via `apt`, OpenFOAM, YADE, or LAMMPS required in phase 0

## Quick start (JupyterHub terminal)

```bash
git clone https://github.com/Ditt-A/PharmaFlow-2D.git
cd PharmaFlow-2D
conda env create -f environment.yml
conda activate pharmaflow-2d
python -m pip install -e .
python -m ipykernel install --user --name pharmaflow-2d --display-name "Python (PharmaFlow-2D)"
python scripts/check_env.py
python scripts/download_reference.py --subset sim
python scripts/inspect_reference.py
python -m pytest -q
```

If `conda` is unavailable, use a user-owned virtual environment and `pip install -e .` instead. In Jupyter choose the **Python (PharmaFlow-2D)** kernel after registering it.

**PyTorch GPU installation:** This is intentionally deferred. First check the CUDA driver and installed PyTorch with `scripts/check_env.py`. For ML experiments, install a matching GPU-enabled PyTorch build from the [official selector](https://pytorch.org/get-started/locally/), then `pip install -r requirements-ml.txt`. Do not blindly replace the JupyterHub system torch installation.

## Data commands

```bash
# Manifest only; no data downloaded
python scripts/download_reference.py --list

# Default: download quasi2D-sim.numbers and verify published checksum
python scripts/download_reference.py --subset sim

# Optionally add experimental data, or all three published files
python scripts/download_reference.py --subset expt
python scripts/download_reference.py --subset all

# Inspect format without making unsupported assumptions about columns
python scripts/inspect_reference.py
```

Data is downloaded **on the JupyterHub machine**, not into GitHub. The downloader uses Zenodo's public record API and checks MD5 checksums when supplied in the manifest.

## Repository layout

```text
PharmaFlow-2D/
├── AGENTS.md                     # Coding-agent scope and acceptance criteria
├── README.md
├── environment.yml
├── requirements-ml.txt
├── pyproject.toml
├── .gitignore
├── data/README.md                # Raw data conventions; actual datasets ignored
├── docs/RESEARCH_PLAN.md         # Physics, experimental design, validation
├── notebooks/README.md
├── outputs/README.md             # Generated rollouts/figures/checkpoints ignored
├── scripts/
│   ├── check_env.py
│   ├── download_reference.py
│   └── inspect_reference.py
├── src/pharmaflow/
│   ├── __init__.py
│   ├── config.py
│   └── dataio.py
└── tests/test_config.py
```

The DEM solver, AI modeling, notebooks, visualizer, and optimizer will be implemented in subsequent, independently tested milestones.

## Planned milestones

1. **M0 — Setup:** environment, repeatable downloads, checksum validation, format inspection, smoke tests.
2. **M1 — Physical DEM:** explicit timestep integrator; gravity; normal/tangential damping; Coulomb friction; particle rotation; wall/particle contacts; hopper geometry; save particle trajectories. Unit/integration tests must pass.
3. **M2 — Validation:** reference data schema audit; dimensional consistency; particle conservation; contact stability; discharge-rate and velocity comparisons where valid. Record any non-comparable reference variables.
4. **M3 — ML:** define pre-clog horizon; group train/validation/test by complete simulation runs and operating configurations; compare feature-based classifiers with temporal models. Evaluate precision-recall, F1, calibration, lead time, and generalization.
5. **M4 — Interactive 2D demo:** actual solver trajectories vs model warnings; outlet density, flow rate, risk-over-time, configurable outlet/particle/friction conditions and solver-backed counterfactual runs.

## Research integrity

- **This is not internal Kalbe data** and does not claim to solve a verified problem at Kalbe.
- The simulator is not a validated commercial pharmaceutical process model.
- Avoid random frame-level train/test splits (temporal leakage).
- A reconstruction from published aggregate data is **not** a reproduced paper model.
- Report both successful and failed runs, conditions, computational cost, and limits.
- Do not label the reference experimental videos/positions as DEM simulations.

## Next step for Codex

Open [AGENTS.md](AGENTS.md) and implement **M1 only**, with physical tests and a headless 2D animation export. Do not start AI training until M1/M2 quality gates are satisfied.
