"""Evaluate an immutable training freeze; never select against validation/test."""
import json
from pathlib import Path
import time
import joblib
import pandas as pd
from .m4_data import load_release, subset, digest, write_json, KEYS
from .m4_models import predict
from .m4_alerts import score_runs, event_metrics
from .m4_metrics import describe, cluster_bootstrap


def load_freeze(output, release):
    freeze_path = Path(output) / 'frozen_selection.json'
    frozen = json.loads(freeze_path.read_text())
    if release['snapshot'] != frozen['m3_snapshot']:
        raise ValueError('M3 release changed since training')
    from .m4_training import source_snapshot
    current = source_snapshot()
    if current != frozen['source_sha256']:
        # A documented audit-only correction may never change fitting, features,
        # metrics, warning semantics or selection. Keep the original freeze intact.
        correction_path = Path('configs/m4/audit_correction.json')
        changes = {name for name in set(current) | set(frozen['source_sha256'])
                   if current.get(name) != frozen['source_sha256'].get(name)}
        if not correction_path.exists() or not changes <= {'m4_audit.py', 'm4_evaluation.py'}:
            raise ValueError('Training/evaluation protocol source changed since freeze')
        correction = json.loads(correction_path.read_text())
        for name in changes:
            record = correction['files'].get(name, {})
            if record.get('before') != frozen['source_sha256'].get(name) or record.get('after') != current.get(name):
                raise ValueError('Unregistered post-freeze source correction: ' + name)
    if digest(Path(output) / 'oof_predictions.parquet') != frozen['oof_sha256']:
        raise ValueError('OOF predictions changed')
    for item in frozen['candidates']:
        if digest(item['artifact_path']) != item['artifact_sha256']:
            raise ValueError('Model artifact changed: ' + item['candidate_id'])
    return frozen


def evaluate(output='outputs/metrics/m4', root='data/processed/m3', report='docs/results/m4'):
    start = time.perf_counter()
    output, report = Path(output), Path(report)
    report.mkdir(parents=True, exist_ok=True)
    receipt = output / 'evaluation_receipt.json'
    if receipt.exists():
        raise FileExistsError('Evaluation already exists; audit it instead of silently overwriting test results.')
    release = load_release(root)
    frozen = load_freeze(output, release)
    config = frozen['config']
    tables, run_tables, metric_rows, uncertainty, selected_summary = [], [], [], {}, []
    for candidate in frozen['candidates']:
        bench, horizon, identifier = candidate['benchmark'], candidate['horizon_s'], candidate['candidate_id']
        selected = frozen['selected'][bench][str(horizon)] == identifier
        artifact = joblib.load(candidate['artifact_path'])
        for split in ('validation', 'test'):
            df = subset(release, bench, horizon, split)
            prediction = df[KEYS + ['physical_group_id', 'target']].copy()
            prediction['probability'] = predict(artifact, df)
            run_rows = score_runs(prediction, release['metadata'], horizon, candidate['threshold'], config['alerts'])
            events = event_metrics(run_rows)
            frames = describe(prediction, candidate['threshold'])
            common = dict(candidate_id=identifier, benchmark=bench, horizon_s=horizon, split=split,
                          model=candidate['model'], feature_set=candidate['feature_set'],
                          selected=selected, threshold=candidate['threshold'])
            metric_rows.append(dict(**common, **frames['raw'],
                                    equal_run_ap=frames['equal_run']['average_precision'],
                                    equal_run_brier=frames['equal_run']['brier'], **events))
            if selected:
                key = identifier + '_' + split
                uncertainty[key] = cluster_bootstrap(prediction, run_rows, candidate['threshold'],
                                                      release['splits']['benchmarks'][bench]['group_key'],
                                                      config['bootstrap_repeats'], config['seed'])
                selected_summary.append(dict(**common, frame=frames, events=events, uncertainty_key=key))
            for key, value in common.items():
                prediction[key] = value
                run_rows[key] = value
            tables.append(prediction)
            run_tables.append(run_rows)
    predictions, runs = pd.concat(tables, ignore_index=True), pd.concat(run_tables, ignore_index=True)
    predictions.to_parquet(output / 'heldout_predictions.parquet', index=False)
    runs.to_parquet(output / 'event_run_metrics.parquet', index=False)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(report / 'metrics.csv', index=False, lineterminator='\n')
    metrics.loc[metrics.selected].to_csv(report / 'selected_metrics.csv', index=False, lineterminator='\n')
    runs.loc[runs.selected].to_csv(report / 'selected_event_runs.csv', index=False, lineterminator='\n')
    # OOF table is explicitly training selection evidence, never a held-out estimate.
    pd.DataFrame([dict(candidate_id=c['candidate_id'], benchmark=c['benchmark'], horizon_s=c['horizon_s'],
                       model=c['model'], feature_set=c['feature_set'], threshold=c['threshold'],
                       utility=c['oof_utility'], **c['oof_frame_equal_run']) for c in frozen['candidates']]).to_csv(
                           report / 'oof_selection.csv', index=False, lineterminator='\n')
    write_json(report / 'feature_sets.json', dict(ablations=release['sets'],
               rule_features=['near_stationary_fraction', 'spanning_arch_now', 'near_speed_mean_m_s', 'near_count', 'remaining_count']))
    write_json(report / 'uncertainty.json', uncertainty)
    # Compact, reviewable freeze preserves selections, exact columns, thresholds and model digests.
    write_json(report / 'frozen_protocol.json', frozen)
    write_json(report / 'summary.json', dict(status='M4A_BASELINE_COMPLETE_BUT_DATA_INSUFFICIENT_FOR_GENERALIZATION',
               selected=selected_summary, model_candidates=len(frozen['candidates']),
               independent_runs=30, independent_events=11,
               freeze_sha256=digest(output / 'frozen_selection.json'),
               training_wall_s=frozen['training_wall_s'], evaluation_wall_s=time.perf_counter() - start,
               test_selection=False, m3_modified=False))
    write_json(receipt, dict(freeze_sha256=digest(output / 'frozen_selection.json'),
               source_sha256=frozen['source_sha256'],
               predictions_sha256=digest(output / 'heldout_predictions.parquet'),
               run_metrics_sha256=digest(output / 'event_run_metrics.parquet'),
               metrics_sha256=digest(report / 'metrics.csv'),
               selection='Complete before validation/test evaluation; no model/threshold changes during evaluation.'))
    print(metrics.loc[metrics.selected, ['benchmark', 'horizon_s', 'split', 'model', 'feature_set',
          'average_precision', 'useful_event_recall', 'false_alerts', 'mean_lead_s']].to_string(index=False))
    return metrics
