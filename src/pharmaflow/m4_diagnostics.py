"""Posthoc descriptions from frozen scores and real M3 DEM histories; no tuning."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, precision_recall_curve
from .m4_data import load_release, subset, run_weights, write_json
from .m4_models import predict
from .m4_alerts import event_metrics
from .m4_evaluation import load_freeze


def grouped_permutation(artifact, df, columns, dictionary, repeats, seed):
    """Validation-only AP loss: permute static values across runs; circular-shift dynamics.

    Dynamic shifts are at least H=.10s where the sequence is long enough.
    This is a dependence-aware perturbation diagnostic, not causal importance.
    """
    rng = np.random.default_rng(seed)
    weights, _ = run_weights(df)
    baseline = average_precision_score(df.target, predict(artifact, df), sample_weight=weights)
    rows = []
    ids = sorted(df.run_id.unique())
    for column in columns:
        losses = []
        static = dictionary[column]['availability'] == 'static experiment configuration'
        for _ in range(repeats):
            changed = df.copy()
            if static:
                shuffled = rng.permutation(ids)
                first = df.groupby('run_id')[column].first()
                mapping = {a: first[b] for a, b in zip(ids, shuffled)}
                changed[column] = changed.run_id.map(mapping)
            else:
                for _, group in df.groupby('run_id'):
                    n = len(group)
                    low = min(20, max(1, n // 3))
                    shift = int(rng.integers(low, max(low + 1, n - low + 1)))
                    changed.loc[group.index, column] = np.roll(group[column].to_numpy(), shift)
            losses.append(baseline - average_precision_score(df.target, predict(artifact, changed), sample_weight=weights))
        rows.append(dict(feature=column, validation_equal_run_ap_loss_mean=float(np.mean(losses)),
                         std=float(np.std(losses)), perturbation='between-run static' if static else 'within-run circular shift'))
    return rows


def diagnostics(output='outputs/metrics/m4', root='data/processed/m3', report='docs/results/m4'):
    output, report = Path(output), Path(report)
    release = load_release(root)
    frozen = load_freeze(output, release)
    scores = pd.read_parquet(output / 'heldout_predictions.parquet')
    runs = pd.read_parquet(output / 'event_run_metrics.parquet')
    metrics = pd.read_csv(report / 'metrics.csv')
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.dpi': 110, 'savefig.dpi': 140})
    chosen = [c for c in frozen['candidates'] if c['candidate_id'] in
              [v for h in frozen['selected'].values() for v in h.values()]]
    fig, axes = plt.subplots(2, 4, figsize=(13, 6), constrained_layout=True)
    calibration_rows, subgroup_rows, permutation_rows, builtin_rows, pause_rows = [], [], [], [], []
    timeline_fig, timeline_axes = plt.subplots(4, 2, figsize=(11, 11), constrained_layout=True)
    for index, c in enumerate(chosen):
        identifier, benchmark, horizon = c['candidate_id'], c['benchmark'], c['horizon_s']
        for split, color in [('validation', '#2878b5'), ('test', '#d65f37')]:
            s = scores.loc[(scores.candidate_id == identifier) & (scores.split == split)]
            precision, recall, _ = precision_recall_curve(s.target, s.probability)
            axes[0, index].plot(recall, precision, color=color, label=split)
            for b in range(10):
                bin_rows = s.loc[np.minimum((s.probability * 10).astype(int), 9) == b]
                if len(bin_rows):
                    calibration_rows.append(dict(candidate_id=identifier, split=split, bin=b, rows=len(bin_rows),
                                                 mean_score=float(bin_rows.probability.mean()),
                                                 observed_fraction=float(bin_rows.target.mean())))
            curve = pd.DataFrame([r for r in calibration_rows if r['candidate_id'] == identifier and r['split'] == split])
            axes[1, index].plot(curve.mean_score, curve.observed_fraction, 'o-', color=color, label=split)
            subset_runs = runs.loc[(runs.candidate_id == identifier) & (runs.split == split)]
            for variable in ('outlet_ratio', 'packing_family', 'friction', 'wall_friction'):
                for value, group in subset_runs.groupby(variable):
                    subgroup_rows.append(dict(candidate_id=identifier, split=split, variable=variable, value=value,
                                              **event_metrics(group)))
            for _, row in subset_runs.iterrows():
                full = release['features'].loc[release['features'].run_id == row.run_id].sort_values('time_s')
                metadata = release['metadata'].set_index('run_id').loc[row.run_id]
                raw = np.load(metadata.trajectory_path, allow_pickle=False)
                crossing = np.sort(raw['crossing_time_s'][np.isfinite(raw['crossing_time_s'])])
                # An interior gap has a later observed crossing: retrospective error analysis only.
                gaps = [(a, b) for a, b in zip(crossing[:-1], crossing[1:]) if b - a >= .05]
                alerts = json.loads(row.false_alert_times_json)
                in_pause = sum(any(a + .025 <= t < b for a, b in gaps) for t in alerts)
                pause_rows.append(dict(candidate_id=identifier, split=split, run_id=row.run_id,
                                       event=bool(row.event), temporary_gap_count=len(gaps),
                                       false_alerts=int(row.false_alerts), false_alerts_in_later_resumed_gaps=in_pause))
                raw.close()
        axes[0, index].set(title=f'{benchmark}\nH={horizon:.2f}s', xlabel='Recall', ylabel='Precision', xlim=(0, 1), ylim=(0, 1.03))
        axes[0, index].legend(fontsize=7)
        axes[1, index].plot([0, 1], [0, 1], ':', color='.5')
        axes[1, index].set(xlabel='Mean warning score', ylabel='Observed positive fraction', xlim=(0, 1), ylim=(0, 1))
        artifact = joblib.load(c['artifact_path'])
        val = subset(release, benchmark, horizon, 'validation')
        if c['model'] not in ('constant', 'rule'):
            permutation_rows.extend(dict(candidate_id=identifier, **r) for r in grouped_permutation(
                artifact, val, c['columns'], release['dictionary'], frozen['config']['permutation_repeats'], frozen['config']['seed']))
            names = artifact['pipeline']['preprocess'].get_feature_names_out()
            model = artifact['pipeline']['model']
            imp = model.coef_[0] if hasattr(model, 'coef_') else model.feature_importances_
            builtin_rows.extend(dict(candidate_id=identifier, feature=name, importance=float(value),
                                     meaning='signed standardized coefficient' if hasattr(model, 'coef_') else 'tree impurity/gain importance')
                                for name, value in zip(names, imp))
        # Fixed representative policy: earliest sorted held-out test event and non-event.
        event_rows = runs.loc[(runs.candidate_id == identifier) & (runs.split == 'test')].sort_values('run_id')
        reps = [event_rows.loc[event_rows.event].iloc[0], event_rows.loc[~event_rows.event].iloc[0]]
        for col, row in enumerate(reps):
            ax = timeline_axes[index, col]
            s = scores.loc[(scores.candidate_id == identifier) & (scores.split == 'test') & (scores.run_id == row.run_id)]
            full = release['features'].loc[release['features'].run_id == row.run_id].sort_values('time_s')
            ax.plot(s.time_s, s.probability, color='#5a4098', label='Frozen score')
            ax.axhline(c['threshold'], color='#5a4098', ls=':', lw=1, label='OOF threshold')
            ax.scatter(json.loads(row.alerts_json), [c['threshold']] * row.alert_count, marker='v', color='#d65f37', zorder=5, label='Warning episode')
            if row.event:
                ax.axvline(row.onset_s, color='#d65f37', ls='--', label='Onset')
                ax.axvline(row.confirmation_s, color='#2b8c62', ls='-.', label='Confirmation')
            twin = ax.twinx()
            twin.plot(full.time_s, full.flow_rate_50ms_particles_s, color='.65', alpha=.6, lw=1, label='DEM trailing flux')
            twin.set_ylabel('Particles/s', color='.4', fontsize=7)
            ax.set(xlabel='Simulation time [s]', ylabel='Score', ylim=(0, 1.08), xlim=(.04, min(1.5, max(.5, float(row.confirmation_s) + .04) if row.event else .8)),
                   title=f'{benchmark}, H={horizon:.2f}s: {"event" if row.event else "completed discharge"}\n{row.run_id}')
            ax.title.set_fontsize(7)
            ax.legend(fontsize=5, loc='upper right')
    fig.savefig(report / 'calibration_pr.png')
    plt.close(fig)
    timeline_fig.savefig(report / 'event_timelines.png')
    plt.close(timeline_fig)
    pd.DataFrame(calibration_rows).to_csv(report / 'calibration.csv', index=False, lineterminator='\n')
    pd.DataFrame(subgroup_rows).to_csv(report / 'subgroup_metrics.csv', index=False, lineterminator='\n')
    pd.DataFrame(permutation_rows).to_csv(report / 'permutation_importance.csv', index=False, lineterminator='\n')
    pd.DataFrame(builtin_rows).to_csv(report / 'model_importance.csv', index=False, lineterminator='\n')
    pd.DataFrame(pause_rows).to_csv(report / 'temporary_interruptions.csv', index=False, lineterminator='\n')
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for i, (benchmark, horizon) in enumerate((b, h) for b in frozen['config']['benchmarks'] for h in frozen['config']['horizons_s']):
        m = metrics.loc[(metrics.benchmark == benchmark) & (metrics.horizon_s == horizon) & (metrics.split == 'test') & (metrics.model != 'rule') & (metrics.model != 'constant')]
        pivot = m.pivot(index='feature_set', columns='model', values='average_precision')
        pivot.plot.bar(ax=axes.flat[i], ylim=(0, 1), rot=25)
        axes.flat[i].set(title=f'{benchmark}, H={horizon:.2f}s', ylabel='Test AP (descriptive)', xlabel='Prespecified feature set')
        axes.flat[i].legend(fontsize=6)
        axes.flat[i].tick_params(axis='x', labelsize=6)
    fig.savefig(report / 'feature_ablations.png')
    plt.close(fig)
    fig, axes = plt.subplots(2, 4, figsize=(12, 6), constrained_layout=True)
    for i, c in enumerate(chosen):
        for j, split in enumerate(('validation', 'test')):
            m = metrics.loc[(metrics.candidate_id == c['candidate_id']) & (metrics.split == split)].iloc[0]
            matrix = np.array([[m.tn, m.fp], [m.fn, m.tp]], dtype=int)
            ax = axes[j, i]
            ax.imshow(matrix, cmap='Blues')
            for (r, col), value in np.ndenumerate(matrix):
                ax.text(col, r, str(value), ha='center', va='center', color='#7b1d26')
            ax.set(xticks=[0, 1], yticks=[0, 1], xlabel='Predicted frame class', ylabel='True frame class',
                   title=f'{c["benchmark"]}\nH={c["horizon_s"]:.2f}s {split}')
            ax.title.set_fontsize(8)
    fig.savefig(report / 'confusion_matrices.png')
    plt.close(fig)
    print('M4 diagnostics written to', report)
