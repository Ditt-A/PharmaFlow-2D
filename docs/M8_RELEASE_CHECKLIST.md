# M8 release checklist

Release scope: documentation, reproducibility guidance, architecture illustration, and portfolio presentation. Starting revision: `625c9d1734398d145ee3d0649c180e115d1b2e71` on `main`.

## Scientific audit

- [x] M1–M7A reports reviewed; historical claims summarized with their original scope.
- [x] M2 numerical convergence reported separately from physical calibration.
- [x] M3/M4B grouped splits and frozen M4B locked evaluation preserved.
- [x] M5 startup/post-discharge/established-flow/temporary-pause/empty/censored categories kept distinct.
- [x] M6 source compatibility and calibration limitations stated.
- [x] M7A reported as 12 valid, 12 right-censored, zero confirmed arches, and no experimental reproduction.
- [x] No raw dataset, full trajectory, prediction, model, or checkpoint added to Git.
- [x] Taichi remains pinned to 1.7.3.
- [x] No M5 demo attempt, research simulation, ML fit, parameter tune, or calibration was run for M8.

## Presentation and reproducibility

- [x] English portfolio README includes the core demo, methods, evidence, limitations, setup, artifact requirements, documentation links, and references.
- [x] Editable Mermaid and lightweight SVG architecture diagrams distinguish simulation, training, inference, visualization, and external-data audit paths.
- [x] Visual gallery points to existing actual solver outputs and source reports; animations were reused without resampling.
- [x] Fresh-clone behavior documents missing trajectory/model artifacts and the app's explicit missing-data messages.
- [x] Technical report and CV-oriented portfolio case study created.
- [x] Release notes and this checklist created.
- [x] Markdown relative links and referenced figure files checked.
- [x] Dashboard launch command passed a loopback Streamlit health check; no demo Run button was submitted. JupyterHub proxy behavior is documented separately.

## Verification

- [x] Starting Git state was clean on `main` at the requested SHA; remote is `https://github.com/Ditt-A/PharmaFlow-2D.git`.
- [x] Full strict suite command: `PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q`.
- [x] Result: **237 passed in 112.62 s**, with one existing Taichi locale deprecation warning (M1–M7A baseline; no tests added or removed by M8).
- [x] All 36 manifest-listed M7A release files other than the intentionally edited README/AGENTS matched the historical SHA-256 entries; M7A outputs, model freezes, labels, and data manifests were not edited.
- [x] Existing M5 ledger remains at two charged attempts of its six-attempt cap per the M7A integrity audit; M8 consumed none.
- [x] No public GitHub release or tag created.
- [x] Documentation and tests were pushed to `main`; the final commit SHA is reported in the completion message.

The M7A checksum list is a release-time snapshot and contains the then-current README and AGENTS files. Their M8 documentation updates are intentional; the historical result files and other frozen evidence remain unchanged.

## Remaining release limitations

- Research trajectories, Parquet releases, and model files are not bundled. A clean clone cannot replay historical runs or display frozen model scores until authorized local artifacts are restored.
- External physical calibration, pharmaceutical validation, and industrial readiness have not been established.