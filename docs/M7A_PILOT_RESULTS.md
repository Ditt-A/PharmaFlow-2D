# M7A fixed-grain pilot results

**Decision:** `M7A_NUMERICAL_ANALOGUE_FEASIBLE`, limited to the numerical contact/geometry implementation. The pilot did **not** reproduce the Cornerstones fixed-grain discharge enhancement or confirm any arch.

## Frozen design and execution

The 12-attempt plan was frozen before outcomes (`design_sha256=e42de488e0a79b920e6360ae19b104e8ee107e6bf13c55693506962b10999ac2`). It used three paired independent seeds (77001–77003), each at a no-obstacle control and fixed-grain distances q=x/dFG of 0.30, 0.66 and 1.14. The distance conditions were selected after viewing the published curve, including its reported maximum bin at q=0.66; they are exploratory locations, not an independent test or discovered optimum. Wall angle/geometry, fill, material assumptions, observation duration and solver settings were held fixed.

The profile control completed 1.0 s without filling the hopper completely (29 crossings and 31 particles remaining), so the frozen remaining eleven cases were dispatched. The observation window stayed at 1.0 s; it was not extended after seeing the outcomes. All trajectories are actual solver states. No new DEM execution is needed to render figures or use the M7 dashboard.

| Measure | Observed |
|---|---:|
| Attempts / successful / failed / unattempted | 12 / 12 / 0 / 0 |
| Physical duration per attempt | 1.0 s |
| Aggregate worker wall time | 4,763.308 s (1.323 h) |
| Aggregate solver CPU time | 4,755.775 s (1.321 h) |
| Longest worker wall time | 452.876 s (below 1,800 s cap) |
| Confirmed finite arches / startup blockages / completed discharges | 0 / 0 / 0 |
| Right-censored for a first confirmed arch | 12 / 12 |
| Maximum overlap / smaller-radius ratio | 0.04034 (guard 0.15) |
| Boundary-center leak samples | 0 in every run |

All runs retained finite states, monotonic timestamps, particle/mass accounting and checksum-verified trajectory receipts. The maximum overlap remained below the unchanged guard. The overlap histogram's 95th-percentile upper bin was at most 0.001 radius; it is a binned upper bound, not an exact percentile. The smallest species' timestep limit was 2.96714 microseconds; dt=2.5 microseconds. The largest observed normal contact force was 0.6112 N. These numerical checks establish neither material calibration nor physical agreement. The 930-file historical snapshot, 86 frozen M4B candidates and the M5 demo ledger (2 charged attempts) remained unchanged.

## Finite-horizon mass outcome

Disk masses use the declared nominal cylindrical mass, rho*pi*R^2*h, at rho=940 kg/m3 and h=3.18 mm. The reported outcome is cumulative mass crossing the numerical outlet plane during the fixed 1.0 s finite-fill window. It is not the source's avalanche mass, a steady flow rate, or dimensionless experimental mass. Ratios divide each condition's three-run mean by the three-run control mean (3.45004 g).

| Fixed-grain q=x/dFG | Ejected count, mean | 1.0 s ejected mass, mean +/- sample SD | Ratio to control mass |
|---:|---:|---:|---:|
| No fixed grain | 27.00 | 3.450 +/- 0.373 g | 1.000 |
| 0.30 | 21.67 | 2.792 +/- 0.486 g | 0.809 |
| 0.66 | 23.67 | 3.006 +/- 0.496 g | 0.871 |
| 1.14 | 23.00 | 2.905 +/- 0.506 g | 0.842 |

All three fixed-grain group means were below the pilot control mean, and the small-sample response was nonmonotonic across the tested positions. With only three paired seeds, this is descriptive variability, not evidence that an obstacle reduces discharge or that q=0.66 is beneficial/harmful. It does not reproduce the external maximum normalized mean of 1.70468. No fit, agreement score, uncertainty claim, friction adjustment or design recommendation was made.

Each run discharged 19–29 particles and left mobile particles in the hopper. No trajectory met the separate M7A finite-arch confirmation protocol (0.4 s); no run emptied. Thus “no confirmed arch during the observation” is right-censored, not a negative clog outcome and not evidence of permanent clogging. The runs do not estimate avalanche mass conditional on clogging.

The near-obstacle particle-speed diagnostic ranged from about 0.049 to 0.098 m/s across fixed-grain runs. It describes saved states in the declared local region; contact-step counts are highly serially dependent and are not independent observations. The final-frame near-outlet speed means ranged from 0.0061 to 0.0745 m/s, and none of the 12 final instantaneous contact graphs spanned both floor supports; these endpoint diagnostics do not replace the persistence/event criterion. No confirmed arch geometry was available to characterize. Discharge histories, energy terms and actual contact networks are included in the diagnostic outputs; mechanical energy loss also includes physical damping, friction and particle export.

## Figures and actual-state animations

`separate_observables.png` intentionally places the numerical finite-horizon masses and the 17 source aggregate bins in separate panels. It states that their stopping, boundary and forcing differ; it is not an overlay or validation score. `pilot_diagnostics.png` retains all seed outcomes, the unchanged overlap guard, actual cumulative mass histories and retained mechanical-energy diagnostics.

The following short GIFs and PNG snapshots use stored DEM frames only, with original physical frame timestamps recorded in `animation_provenance.json`:

- [No fixed grain, seed 77001](results/m7a/control.gif) and [PNG](results/m7a/control.png)
- [Fixed grain at q=0.30, seed 77001](results/m7a/near.gif) and [PNG](results/m7a/near.png)
- [Fixed grain at q=1.14, seed 77001](results/m7a/far.gif) and [PNG](results/m7a/far.png)
- [Separate observables](results/m7a/separate_observables.png)
- [Pilot diagnostics](results/m7a/pilot_diagnostics.png)

The M7A dashboard replays these local trajectories and separately displays the genuine Cornerstones source curve. It does not start runs or combine those data as matched observations.

## Reproduction and audit

Use the pinned `pharmaflow-2d` conda environment. The historical pilot ledger is exhausted: the committed M7A SQLite ledger records all 12 attempts, so the runner will not dispatch more cases. The trajectory NPZs and per-run receipts remain in the ignored local `data/simulated/m7a/trajectories/` directory and are required for a full independent audit/animation regeneration.

```bash
conda activate pharmaflow-2d
python -m pytest -q
PHARMAFLOW_TEST_TAICHI=1 python -m pytest tests/test_m7a.py -q
python scripts/audit_m7a.py
```

Recreate figures only when the ignored trajectory files and their receipts are present:

```bash
python -c "from pathlib import Path; from pharmaflow.m7a_visuals import result_figures; result_figures(Path('.'))"
```

The exact frozen parameters, run IDs, seeds, timestamps, checksums and outcomes are in `configs/m7a/pilot.json`, `docs/results/m7a/design_freeze.json`, `docs/results/m7a/attempt_ledger.json` and `docs/results/m7a/pilot_runs.csv`. Full NPZ trajectories are never committed.
