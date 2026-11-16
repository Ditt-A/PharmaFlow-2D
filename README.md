# PharmaFlow-2D

**DEM-based granular hopper simulation and AI-assisted flow diagnostics** — a research-oriented proof of concept for powder handling in pharmaceutical manufacturing.

> **Status:** M1 DEM, M2 physics benchmarks and M3 synthetic dataset/first-event labeling are implemented. 64 tests pass, including strict CUDA checks. Published-data calibration remains unresolved. No model training, optimization or industrial performance claims.

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

The NumPy CPU solver requires no Taichi, PyTorch, CUDA toolkit, sudo or display.
For optional acceleration, reference table inspection and tests:

```bash
python -m pip install -e '.[acceleration,reference,test]'
```

On this JupyterHub container, GLIBC is 2.31. The Taichi 1.7.4 wheel requests
`GLIBC_2.32` and cannot import. The acceleration extra and environment file pin
**Taichi 1.7.3**, verified with real CPU/CUDA kernels on the A100. Do not replace
the container's system GLIBC. See the [upstream report](https://github.com/taichi-dev/taichi/issues/8768).

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

The Numbers parser now reads the actual sheets/tables, verifies the ZIP and MD5,
and exports `outputs/metrics/reference_schema.json`. The inspected simulation
file contains four aggregate profile/map tables for D=2 cm and D=3 cm; its headers
do not provide particle IDs or timestamps. See [the schema audit](docs/REFERENCE_SCHEMA.md).

## Run the M1 simulator

```bash
# Real 100-particle discharge; NPZ + JSON provenance and a headless Pillow GIF
python scripts/run_hopper.py --backend cpu --particles 100 --duration 0.6 \
  --output outputs/rollouts/m1_hopper.npz --gif outputs/animations/m1_hopper.gif

# Narrow outlet: retain particles and examine a persistent contact bridge
python scripts/run_hopper.py --config docs/m1_narrow.json --duration 0.8 \
  --sample-every 500 --output outputs/rollouts/m1_narrow.npz \
  --gif outputs/animations/m1_narrow.gif
python scripts/validate_m1.py

# Optional explicit CUDA; fails clearly if CUDA is unavailable
python scripts/run_hopper.py --backend cuda --particles 50 --duration 0.002 \
  --output outputs/rollouts/m1_cuda_smoke.npz

# --backend auto tries CUDA and reports a NumPy fallback on failure
# Include strict optional Taichi CPU and CUDA physics parity tests
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
```

Each run starts from a seeded nonoverlapping fill, settles behind a finite gate,
opens the actual outlet, and integrates particle/wall contact forces. The GIF is
generated from those trajectories and shows particle spin, speed and discharge
count. Simulation time and animation playback time are distinct.

CUDA currently evaluates the contact law in f64; spatial hashing, contact memory,
force reduction and integration stay on CPU. It is a tested hybrid backend and
does not promise a speedup at 50–200 particles. CPU is the default.

Read [the physical model and numerical limits](docs/M1_METHODS.md) and
[node680 verification evidence](docs/M1_VERIFICATION.md). Generated trajectories
and full animations stay in ignored local folders.

## M2 numerical validation and controlled experiments

![Real DEM discharge, 50 disks, speed in SI units](assets/m2_demo.gif)

This optimized preview contains 36 actual solver frames. Full-size wide/arch
GIFs and PNG snapshots are generated locally. The M2 campaign includes 24
repeated cases (8 configurations × 3 seeds), 6 paired timestep runs, controlled
analytic energy/contact benchmarks, independent replay checks and an audit of
all 14 published Numbers tables.

- Elastic maximum energy error decreases **1.277% → 0.635% → 0.316%** at dt,
  dt/2 and dt/4. Individual many-body trajectories retain measurable errors.
- The wide outlet empties for all three seeds. At D/d=3, two seeds empty and
  one retains a finite-window arch; another completed run temporarily pauses.
- All 24 repeated runs conserve particles and pass sidewall leak checks.
- One deliberately reported pilot fails the unchanged overlap guard.
- Published data contains fragmented numeric strings and unresolved units;
  the reference comparison is explicitly partial and qualitative.

Read [M2 validation and exact reproduction commands](docs/M2_VALIDATION.md),
[reference comparison limits](docs/M2_REFERENCE_COMPARISON.md), and
[quantitative CSV/JSON/PNG results](docs/results/m2/).

```bash
python scripts/run_m2.py --suite configs/m2/sweep.json --output outputs/metrics/m2/sweep --jobs 4
python scripts/run_m2.py --suite configs/m2/convergence.json --output outputs/metrics/m2/convergence --jobs 3
python scripts/benchmark_m2.py --cuda
```

These are a small research pilot, not a permanent-clogging classifier, an
industrial material calibration, or a full reproduction of the published DEM.

## M3 scientific dataset and first-event labels

![Real DEM pre-onset, onset and future-confirmation frames](docs/results/m3/particle_event_sequence.png)

The bounded M3 campaign performs **6 stiffness checks + 18 pilot + 12 adaptive
runs**, then stops. All 36 attempts succeed; 30 independent runs enter the
dataset, with 11 finite-duration first-arch events. Geometry-controlled outlet
studies keep the requested wall angle fixed. Three structurally different packing
families, five seeds and transition cases avoid using only trivial anchors.

Selected numerics are kn=4000 N/m, kt=1000 N/m and dt=5e-6 s. Maximum dataset
overlap is 0.0834 R, below the unchanged 0.15 R guard. The dataset contains 9030
feature rows and 18060 time/horizon label rows, with targets for H=0.05/0.10 s.
Future-only confirmation uses a 0.4 s common-contact persistence window; predictors
are instantaneous or trailing-only. Post-onset and empty states are excluded.

Run-grouped and complete-configuration holdouts are both supplied. No encoder,
normalizer or predictive model is fitted. Naturally censored runs are absent
in this small cohort; censoring is tested with toy cases and 11 truncated real
prefixes, without adding duplicated training trajectories.

```bash
python -m pip install -e '.[dataset,acceleration,test]'
python scripts/run_m3.py --plan configs/m3/pilot.json --jobs 4
# Review the pilot before the documented 12-run adaptive expansion.
python scripts/run_m3.py --plan configs/m3/production.json --jobs 4
python scripts/build_m3_dataset.py
python scripts/audit_m3.py
python scripts/plot_m3.py
```

Raw trajectories stay in `data/simulated/m3/`; Parquet tables, labels, feature
dictionary and splits stay in `data/processed/m3/`. Both directories are ignored
by Git. Only compact checksum manifests, reports and selected figures are
published. See [dataset design/reproduction](docs/M3_DATASET.md),
[labeling protocol](docs/M3_LABELING_PROTOCOL.md), [quality report](docs/M3_QUALITY_REPORT.md)
and [lightweight results](docs/results/m3/). The strict validation/test sets each
contain only one event-bearing run; this release supports data-pipeline research,
not strong claims about predictive performance.

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
│   ├── inspect_reference.py
│   ├── run_hopper.py
│   └── validate_m1.py
├── src/pharmaflow/
│   ├── __init__.py
│   ├── config.py
│   ├── dataio.py
│   ├── dem.py                     # State, contact assembly, integration, outlet
│   ├── contact.py                 # History friction and normal contact
│   ├── geometry.py                # Finite walls and wall-crossing detection
│   ├── neighbors.py               # Uniform cells / Verlet skin
│   ├── taichi_backend.py          # Optional f64 CPU/CUDA contact kernel
│   ├── diagnostics.py             # Finite-window arch observation
│   ├── run.py                     # Reproducible NPZ / JSON metadata
│   └── visualize.py               # Headless solver trajectory GIF
└── tests/                         # Configuration and physical validation
```

The DEM solver, M2 experiment runner, M3 dataset/label/feature pipeline and
headless visualizers are implemented. Reference calibration, model training,
interactive dashboards and optimization remain future work.

## Planned milestones

1. **M0 — Setup:** environment, repeatable downloads, checksum validation, format inspection, smoke tests.
2. **M1 — Physical DEM:** explicit timestep integrator; gravity; normal/tangential damping; Coulomb friction; particle rotation; wall/particle contacts; hopper geometry; save particle trajectories. Unit/integration tests must pass.
3. **M2 — Validation:** reference data schema audit; dimensional consistency; particle conservation; contact stability; discharge-rate and velocity comparisons where valid. Record any non-comparable reference variables.
4. **M3 — Scientific synthetic dataset:** numerical preparation, budgeted generation, first-event labels, censoring, causal features, grouped splits and QA. Implemented without training.
5. **M4 — Future modeling:** only under a separate request; fit preprocessing on training groups, use independent-event evaluation and document small-sample limitations before an interactive prediction demo.

## Research integrity

- **This is not internal Kalbe data** and does not claim to solve a verified problem at Kalbe.
- The simulator is not a validated commercial pharmaceutical process model.
- Avoid random frame-level train/test splits (temporal leakage).
- A reconstruction from published aggregate data is **not** a reproduced paper model.
- Report both successful and failed runs, conditions, computational cost, and limits.
- Do not label the reference experimental videos/positions as DEM simulations.

## Next step for Codex

Preserve M1/M2/M3 tests, source hashes and frozen splits. Resolve calibration and
expand independent event/configuration/censoring coverage only under an explicit
new experiment budget. Do not begin ML training without a separate request.
