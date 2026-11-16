"""Posthoc error evidence only: no fitting, selection, label changes or simulations."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pharmaflow.m4_data import load_release, write_json, digest
from pharmaflow.m4_evaluation import load_freeze


def analyze(output, root, report):
    output, report = Path(output), Path(report)
    release = load_release(root)
    frozen = load_freeze(output, release)
    predictions = pd.read_parquet(output / 'heldout_predictions.parquet')
    runs = pd.read_parquet(output / 'event_run_metrics.parquet')
    meta = release['metadata'].set_index('run_id')
    examples = []
    for _, row in runs.loc[runs.selected & (runs.false_alerts > 0)].iterrows():
        raw = np.load(meta.loc[row.run_id, 'trajectory_path'], allow_pickle=False)
        crossings = np.sort(raw['crossing_time_s'][np.isfinite(raw['crossing_time_s'])])
        for alert in json.loads(row.false_alert_times_json):
            f = release['features'].loc[(release['features'].run_id == row.run_id) &
                                       (release['features'].time_s == alert)].iloc[0]
            before, after = crossings[crossings <= alert], crossings[crossings > alert]
            examples.append(dict(candidate_id=row.candidate_id, split=row.split, run_id=row.run_id,
                                 alert_s=alert, event=bool(row.event),
                                 eventual_outcome=meta.loc[row.run_id, 'flow_state'],
                                 onset_s=float(row.onset_s) if row.event else None,
                                 future_lead_s=float(row.onset_s - alert) if row.event else None,
                                 last_crossing_s=float(before[-1]) if len(before) else None,
                                 next_crossing_s=float(after[0]) if len(after) else None,
                                 last_run_crossing_s=float(crossings[-1]) if len(crossings) else None,
                                 **{k:float(f[k]) for k in ('spanning_arch_now', 'near_max_speed_m_s',
                                     'near_stationary_fraction', 'flow_rate_50ms_particles_s', 'remaining_count')}))
        raw.close()
    write_json(report / 'error_examples.json', dict(scope='Posthoc scoring only; future crossings/outcomes are never model inputs',
               freeze_sha256=digest(output / 'frozen_selection.json'), examples=examples))
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), constrained_layout=True)
    identifiers = [('configuration_holdout_h100_B_current_xgboost', 'validation', False),
                   ('configuration_holdout_h050_baseline_rule', 'test', True)]
    for ax, (identifier, split, event) in zip(axes, identifiers):
        row = runs.loc[(runs.candidate_id == identifier) & (runs.split == split) &
                       (runs.event == event) & (runs.false_alerts > 0)].sort_values('run_id').iloc[0]
        scores = predictions.loc[(predictions.candidate_id == identifier) & (predictions.split == split) &
                                  (predictions.run_id == row.run_id)]
        full = release['features'].loc[release['features'].run_id == row.run_id].sort_values('time_s')
        ax.plot(scores.time_s, scores.probability, color='#68439c', label='Frozen warning score')
        ax.axhline(row.threshold, color='#68439c', ls=':', label='OOF threshold')
        for n, t in enumerate(json.loads(row.alerts_json)):
            ax.axvline(t, color='#c14c2d', ls='--', label='Episode start (false)' if n == 0 else None)
        if event:
            ax.axvline(row.onset_s, color='black', label='Onset')
            ax.axvspan(row.onset_s - row.horizon_s, row.onset_s - .02, color='#80b788', alpha=.25, label='Useful warning window')
        twin = ax.twinx()
        twin.plot(full.time_s, full.flow_rate_50ms_particles_s, color='#286f94', alpha=.6, label='Actual DEM trailing flux')
        twin.set_ylim(0, max(1, float(full.flow_rate_50ms_particles_s.max()) * 1.1))
        twin.set_ylabel('Trailing flux [particles/s]', color='#286f94')
        ax.set(xlim=(.05, .42 if not event else .24), ylim=(0, 1.05), xlabel='Simulation time [s]', ylabel='Warning score',
               title=('Transient spanning path while flow continues' if not event else 'H=0.05s: latched warning starts 0.075s before onset'))
        ax.legend(loc='upper right', fontsize=7)
    fig.savefig(report / 'false_alarm_diagnostics.png', dpi=140)
    plt.close(fig)
    print('Posthoc false-alert examples:', len(examples))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='outputs/metrics/m4')
    p.add_argument('--data', default='data/processed/m3')
    p.add_argument('--report', default='docs/results/m4')
    a = p.parse_args()
    analyze(a.output, a.data, a.report)
