# M5 interactive DEM research dashboard

M5 provides actual-state replay, bounded explicit CPU DEM jobs and descriptive
operational monitoring. It performs no training, optimization, policy tuning or
new research campaign. Source starts at
`f639f6e3389767a69643bea3f9b2c6abe72fa203` on `main`.

## Launch locally or in the existing JupyterHub environment

```bash
cd ~/adit/PharmaFlow-2D
conda activate pharmaflow-2d
# Existing node: preserve the audited numerical/ML stack.
python -m pip install -c configs/m5/existing_node_constraints.txt -e '.[dashboard]'
python -m streamlit run app/streamlit_app.py \
  --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

On a local workstation, open `http://127.0.0.1:8501`. Use Python 3.11 and the
project environment. The optional dashboard extra pins Streamlit 1.67.0 and
Plotly 5.24.1. Installation needs no sudo, container daemon or CUDA changes.
The existing environment retains Taichi 1.7.3 and all eleven audited core
dependency versions; `python -m pip check` passes. An earlier incompatible
Streamlit 1.45.1 install was rejected by the resolver before mutation because
it required an older Pillow. No numerical dependency was downgraded.

Inside JupyterHub, localhost is inside the container. A Hub administrator may
already provide an authenticated `jupyter-server-proxy` route, typically under
the current user URL followed by `proxy/8501/`. Use that existing route only if
supported by the Hub. This project does not assume that proxy package, public
ports, root privileges or host networking. Do not expose the dashboard publicly.
Where an authenticated proxy is unavailable, use the offline notebook viewer:

```python
from pharmaflow.dashboard_data import historical_registry, load_bundle
from pharmaflow.notebook_viewer import notebook_replay
records = historical_registry()
bundle = load_bundle(records[0])
display(notebook_replay(bundle))
```

The fallback is a self-contained HTML canvas with actual positions, radii,
walls, speed colors, chronological rule/ML traces, contacts, controls and PNG
export. It needs neither ipywidgets nor a web port/CDN. Notebook trust/CSP may
block embedded scripts; download the exported HTML from JupyterLab and open it
locally in that case. `python scripts/export_m5.py` generates standalone
`outputs/dashboard/m5/exports/{continuous,startup,resumed}.html`.

## Required local assets

The private node retains complete historical trajectories under
`data/simulated/m3/` and `data/simulated/m4b/`, frozen model artifacts under
`outputs/checkpoints/m4b/`, and saved evaluation outputs under
`outputs/metrics/m4b/`. A fresh Git clone deliberately excludes these files.
Restore a separately retained local release to audit every historical run; do
not regenerate simulations or retrain to populate the UI.

For a lightweight workstation replay, copy these ignored folders from the node:

```text
outputs/dashboard/m5/portfolio/          # catalog + 3 original NPZ/JSON scenes
outputs/dashboard/m5/monitor_cache/      # frozen ML scores with provenance
```

`audit_m5.py` builds them from existing release data. The portable catalog stores
original configuration, run ID, membership and NPZ checksum. The loader checks
the NPZ, embedded configuration/run ID, chronology and cached specification /
timestamps / trajectory SHA before rendering. Inference from a restored model
requires its original SHA-256. When no verified model/cache is available, ML is
explicitly unavailable; the rule still runs. Never substitute invented scores.
The app clearly marks retrospective training/development/locked membership and
unevaluated demos. Replay of training cases is not independent validation.

## Controls and causal monitoring

Trajectory replay provides run selection, play/pause, previous/next frame,
scrubbing, playback stride, speed-colored physical disks and real hopper walls,
optional near-outlet contact paths, instantaneous spanning-path diagnostics,
physical timestamps, retained/discharged counts, trailing 50 ms flow, approximate
local occupancy and mean speed, score traces and past warning logs. The camera
uses the known initial fill only and crops the wall geometry around it; equal
physical axes preserve actual particle radius. The speed scale is fixed at
0–1 m/s and saturates above 1. No trajectory interpolation or decorative motion
is used. Playback is intentionally slower than physical time.

Only traces at or before the current cursor are shown. A pause is an observed
state, never itself a confirmed clog. Occupancy is the M3 center-assigned disk
area estimator, not an exact physical packing fraction. The contact overlay is
the near-outlet geometric network at the saved frame, not contact forces or the
future-persistent arch label.

The unchanged M4A rule is `.45 stationary + .35 span + .20 exp(−speed/.02)` when
at least two near and retained grains exist. Its threshold is **.85**, two-frame
debounce, one-frame clearing below threshold, 50 ms cooldown, no periodic refresh.
The frozen M4B comparator is `m4b_h100_D_full_xgboost`, threshold **.5**, two high
frames, two clearing frames below `.65 × threshold`, 50 ms cooldown and refresh,
at most two reminders per latched episode. Both use the original gate/empty and
missing-interval behavior. This differs intentionally from replacing the
original rule with the M4B development-informed rule policy. All outputs are
raw scores, not calibrated risk probabilities.

The research page alone shows future-confirmed onset/confirmation annotations.
They never enter online monitoring or suppress post-onset alerts. It displays
the original locked M4B results without promoting another model after testing:

| Frozen comparator, H=0.10s | Useful warnings ≥20ms | False first-event forecasts | Late post-onset subset | Mean valid lead |
|---|---:|---:|---:|---:|
| Original M4A rule | 7/7 | 0 | 0 | 57.86ms |
| Selected M4B ML | 7/7 | 12 | 6 | 77.14ms |
| Development-informed M4B rule policy | 7/7 | 8 | 5 | 62.86ms |

These are 12 locked runs / four configurations / seven first events, including
startup blockage. The new taxonomy finds only two established-flow arches there.
Zero false forecasts for the original rule is a specific observation on this
cohort, not evidence of perfect generalization. Late alerts are a separately
reported subset of the conservative false first-event forecast count; they
must not be added a second time. Lead distributions and records are displayed
from an exact compact copy of the original event records in
`docs/results/m5/frozen_locked_event_runs.csv`, without new evaluation or tuning.

## Explicit bounded simulations

Only **Run DEM simulation** submits a job; editing the form, replay sliders or
page selection cannot integrate physics. Inputs are D/d (2–6), particle/wall
friction (.15–.65), angle (28–42° from vertical), 30–100 disks, three packing
families, seed and physical duration (.10–.80s, 5ms grid). Geometry preserves wall
angle when outlet width changes. Large fills/packings can fail placement or a
physical guard; failures remain charged and are never silently retried.

`configs/m5/demo_limits.json` limits each workspace to **six attempts**, three
cumulative requested simulated seconds, one concurrent job, 180s timeout and
`steps × N² ≤ 400,000,000` (100 disks allow at most .20s). The SQLite reservation
is atomic and includes failed attempts. Unique worker claims prevent duplicate
integration. The reservation snapshots the numerical limits; changes during a
job are rejected. There is no UI budget reset. An interrupted/crashed supervisor
may leave a reserved job: inspect its worker log and ledger rather than retrying
or deleting its charged attempt.

The CPU runner uses kn=4000 N/m, kt=1000 N/m, dt=5µs and the unchanged .15R
overlap guard, plus existing stability, finite-state and wall checks. Runs are
stored under `outputs/demos/m5/<run_id>/`, with request, ledger, worker log, original
NPZ states and numerical diagnostics. They are marked unevaluated and are never
included by the M3/M4B campaign, dataset builder or historical taxonomy audit.
Model scores on custom demos, especially larger fills, may be out of domain.
Short demo observation windows are often censored; they cannot establish a
0.4s persistent arch and are not new first-event evaluation evidence.

One charged Run-button validation used N=30, D/d=5, μpp=μwall=.3, 35°, staggered
packing, seed 57001 and .12s. It completed 25 sampled frames and 18 crossings in
16.14 CPU seconds. All guards remained enabled; see
[demo_validation.json](results/m5/demo_validation.json). Five attempts remain in
this node's local demo budget. This is engineering validation, not a campaign.

## Portfolio and exports

| Scene | Genuine historical run | Export |
|---|---|---|
| Continuous discharge | `pilot_0151aedb5166ad43_hexagonal_s202` | [PNG](results/m5/continuous.png), [GIF](results/m5/continuous.gif) |
| Startup blockage | `pilot_4fb2421c2854241d_hexagonal_s202` | [PNG](results/m5/startup.png), [GIF](results/m5/startup.gif) |
| Pause followed by resumed discharge | `production_a1d8150e7f3d0517_hexagonal_s404` | [PNG](results/m5/resumed.png), [GIF](results/m5/resumed.gif) |

The resumed scene has a 55ms crossing gap, observed as a pause at .240s and
resumption at .245s; it eventually empties. It is not a persistent arch breaking.
Each animation synchronizes exact stored states and chronological traces.
Playback subsamples at most 60 frames without altering physical timestamps.
PNG download exports the current frame; **Export short GIF** renders up to .8s
from the cursor into ignored `outputs/dashboard/m5/exports/` with a frame/time
manifest. Short clips are deliberately bounded and require an explicit click.
The CLI exports provide three compact committed GIFs and PNGs; full trajectories
and offline HTML remain local. [visualization_manifest.json](results/m5/visualization_manifest.json)
records source checksums and original frame indices.

## Verification and remaining limitations

```bash
python scripts/audit_m5.py             # existing trajectories/models only
python scripts/export_m5.py            # actual-state PNG/GIF/offline viewers
PHARMAFLOW_TEST_TAICHI=1 python -m pytest -q
python -m pip check
```

The suite has 149 passing tests (116 historical + 33 M5), including CPU/CUDA
contact parity. M5 checks online prefix invariance, event distinction, absence
of future-label dependence, frozen controller equivalence, geometry/parameter
limits, charged failure/concurrency behavior, immutable replay/checksums,
offline states and UI interactions without automatic integration. Browser
checks cover playback, pause, scrub and the offline viewer. Preservation auditing
verified 700 historical files unchanged, 86 frozen candidate artifacts/source
checks, all 11 original core versions and the original 48-attempt M4B ledger.

The UI renders saved frames rather than a streaming industrial process.
Notebook embedding depends on browser trust/CSP, and large user exports may be
slow. No natural censored historical runs exist; censoring logic is covered by
earlier toy tests, not independent observed censoring evidence. The operational
flow criterion and sampled pause cutoff are research definitions and require
external justification. Read [operational audit](M5_OPERATIONAL_EVENTS.md) and
[calibration gaps](M5_CALIBRATION_GAPS.md) for physical/scientific limits.

Streamlit fragment and testing APIs follow its official
[fragment documentation](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
and [AppTest documentation](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
