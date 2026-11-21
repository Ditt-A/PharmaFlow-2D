# M8 release notes

**Date:** 2026-11-21  
**Starting revision:** `625c9d1734398d145ee3d0649c180e115d1b2e71`  
**Release type:** research portfolio and reproducibility documentation. No public tag or GitHub release was created.

## Included

- Reorganized the English README around the engineering problem, physical solver, numerical verification, data design, baseline evaluation, dashboard, setup, artifact availability, and references.
- Added an editable Mermaid system diagram and an exported lightweight SVG.
- Added a technical report, portfolio case study, curated gallery, release checklist, and these notes.
- Updated `AGENTS.md` to make the current release scope and preserved experiment limits explicit.
- Reused existing solver-generated GIFs and figures; no trajectory was regenerated or altered.

## Scientific evidence preserved

- The M4B result remains a small seven-event locked-cohort observation: the original frozen physics rule produced 7/7 useful warnings with zero false first-event forecasts; the selected XGBoost produced 7/7 useful warnings with 12 false first-event forecasts. This does not establish generalization or universal rule superiority.
- The M6 external-data audit still finds no currently quantitatively eligible physical comparison.
- M7A remains 12/12 valid one-second runs, 12 right-censored, zero confirmed arches, and no reproduction of the external fixed-grain phenomenon.
- The numerical solver, M3/M4 labels and splits, model freezes, experimental manifests, historical trajectories and dashboard assets were not modified.

## Verification and deployment limits

The complete release verification command is `PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q`; M8 verified 237 passing tests in 112.62 s with one existing Taichi locale deprecation warning. A loopback Streamlit health check passed without submitting the Run button. Taichi remains pinned to 1.7.3. The existing M5 ledger remains at two charged attempts of six and was not used or reset. Full trajectory/model replays still require local artifacts ignored by Git; missing assets are reported by the dashboard.

This repository release does not claim external calibration, pharmaceutical deployment, industrial validation, or design optimization.