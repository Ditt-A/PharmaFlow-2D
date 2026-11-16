# Node680 M1 verification — 2026-11-16 UTC

Repository: `/home/adityaakbar/adit/PharmaFlow-2D`.
Environment: `/home/adityaakbar/.conda/envs/pharmaflow-2d/bin/python`.
Original checkout was clean; changes remain uncommitted in the working tree.
README.md, AGENTS.md and RESEARCH_PLAN.md were read completely before changes.

## Environment and initial checks

Python 3.11.18, 256 visible CPU cores, approximately 4 TB free workspace,
Ubuntu GLIBC 2.31. NVIDIA A100-SXM4-80GB, driver 580.126.20 is exposed to the
notebook and project process. Other workloads were already occupying the GPU;
availability is not a claim that all GPU capacity was free.

Initial tests: 2 passed. `download_reference.py --list` succeeded. The original
Taichi 1.7.4 installation failed importing `taichi_python` because it required
GLIBC_2.32. Installed and pinned Taichi 1.7.3 only in `pharmaflow-2d`.
Real compiled array kernels passed on both Taichi CPU and strict CUDA with
fallback disabled. No system GLIBC, system Python, CUDA driver or other
environment was replaced. PyTorch remains absent and is unnecessary for M1.

Registered and verified the user-owned Jupyter kernelspec
`pharmaflow-2d` / **Python (PharmaFlow-2D)**. Select this kernel in notebooks;
the existing default `python3` kernel belongs to `/opt/conda`, not this project
environment.

Installed project version 0.1.0 as editable. `pip check` passed after the
compatibility fix; final dependency validation is repeated with the final checks.
NumPy 1.26.4, Taichi 1.7.3, matplotlib 3.11.2, requests 2.34.2,
numbers-parser 4.22.2, pytest 9.2.0, Pillow 12.3.0.

## Reference integrity and schema

Ran the requested `download_reference.py --subset sim` and `inspect_reference.py`.
Simulation file: 10,938,165 bytes; published MD5 matched; all 445 ZIP entries
passed CRC inspection. The Numbers parser read four tables. See
[REFERENCE_SCHEMA.md](REFERENCE_SCHEMA.md). No time/particle ID columns were
found in their headers. Raw data is not used as a particle trajectory source.

## Physics tests

`PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q --color=no`:
**29 passed**, including both optional Taichi CPU and CUDA contact/trajectory
parity tests. One upstream Taichi `locale.getdefaultlocale` deprecation warning
remains; it does not affect kernel execution.

Tests cover analytic free fall and timestep convergence, isolated contact,
approach damping, Coulomb friction/history, spin and dissipation, elastic pair
momentum/energy, angular momentum with tangential forces, wall support/rebound,
finite endpoints, outlet gap, cell search completeness, fail-fast guards,
deterministic interacting runs, trajectory export, crossing accounting,
headless animation, unavailable-CUDA fallback and rejection of zero-flux-only
clogging interpretations. The first test pass exposed two test-fixture errors
(torque sign and an endpoint position beyond the permitted overlap); these
were corrected against the force geometry without relaxing solver guards.

## Full solver runs

| Quantity | Wide hopper | Narrow hopper |
| --- | --- | --- |
| Backend | NumPy CPU | NumPy CPU |
| Seed | 42 | 42 |
| Particles | 100 | 80 |
| Radius / diameter | 0.002 / 0.004 m | 0.002 / 0.004 m |
| Outlet | 0.030 m (7.5 diameters) | 0.005 m (1.25 diameters) |
| Particle/wall friction | 0.4 / 0.4 | 0.65 / 0.65 |
| Gate opens | 0.05 s | 0.10 s |
| Integrated time | 0.60 s | 0.80 s |
| Steps at dt=1e-5 s | 60000 | 80000 |
| Discharged / initial | 100 / 100 | 0 / 80 |
| Active / removed at end | 0 / 100 | 80 / 0 |
| Maximum overlap / radius | 0.0882872 | 0.1141785 |
| Permitted overlap / radius | 0.15 | 0.15 |
| Maximum step displacement / radius | 0.00563379 | 0.00256049 |
| NaN / wall crossing | None / none | None / none |

Both runs passed particle accounting and downstream-removal crossing checks.
The narrow run's final 0.2 s had no crossings, retained 80 disks, and maintained
a contact chain between both lower walls at every one of 41 sampled frames.
Maximum near-outlet particle speed during this window was 0.0010111 m/s,
below the illustrative 0.003 m/s stationarity threshold. This supports a
finite-window arch observation, not proof of permanent clogging. The empty
wide hopper also has zero late flux and correctly fails the arch criteria.

Both complete CPU trajectories were then regenerated independently and their
array fingerprints matched exactly. The regenerated JSON/NPZ metadata includes
`reproduced_previous_full_run_sha256` and solver source SHA256
`0aba5cd330720a41ee8ca1b80b315c3c59d0ddd1855cd0fcf906ea5d517e9c41`.
Repeated integration took approximately 30 s and 57 s respectively on node680,
excluding GIF rendering. These are observations, not performance guarantees.
Both GIFs have 150 frames and were visually inspected.

A bounded CLI smoke run also initialized strict `taichi-cuda` and exported a
50-particle, 200-step (0.002 s) trajectory. That short fill has no collisions;
actual CUDA contact/spin verification is provided by the interacting-pair parity
tests, not inferred from the empty-contact smoke run. A longer GPU test was
slow under the observed shared GPU load and hybrid transfer overhead, so the
documented quick CUDA smoke is deliberately short. Full demos use NumPy CPU;
GPU speedups and full-GPU integration are not claimed.

Trajectory SHA256 fingerprints (array data, not timestamped metadata):

- Wide: `d4af0cef5d1ac87f19c02f606ee9c35bde9cbda515ffec54f8fb7436c79d19ae`
- Narrow: `c712e61e254c8c82b639570a98f3dc8b5f919fcd9b166b604ca037762182a511`

Run-level metadata, accuracy results and headless animations are local ignored
artifacts, not repository assets:

- `outputs/rollouts/m1_hopper.npz` and `.json`
- `outputs/rollouts/m1_narrow.npz` and `.json`
- `outputs/animations/m1_hopper.gif`
- `outputs/animations/m1_narrow.gif`
- `outputs/metrics/m1_validation.json`
- `outputs/metrics/reference_schema.json`

These demonstrate M1 contacts, stability, real discharge and qualitative
arching. Bulk many-body convergence, parameter calibration, reference units,
quantitative reference comparisons and statistical robustness remain M2.
No AI training, prediction or optimization has been implemented.
