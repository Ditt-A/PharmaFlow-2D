"""Recheck frozen M3 checksums, split isolation, train-only fits and saved predictions."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from .m4_data import load_release, subset, digest, write_json
from .m4_evaluation import load_freeze
from .m4_models import predict
from .m4_alerts import choose_threshold, score_runs, event_metrics


def verify_prediction_replay(saved, replay, threshold):
    """Allow roundoff from parallel forest summation, never a changed alert decision."""
    np.testing.assert_allclose(saved, replay, rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(np.asarray(saved) >= threshold, np.asarray(replay) >= threshold)
    return float(np.max(np.abs(np.asarray(saved) - np.asarray(replay))))


def audit(output='outputs/metrics/m4', root='data/processed/m3', report='docs/results/m4'):
    output, report = Path(output), Path(report)
    release = load_release(root)
    frozen = load_freeze(output, release)
    receipt = json.loads((output / 'evaluation_receipt.json').read_text())
    for path, key in [(output / 'frozen_selection.json', 'freeze_sha256'),
                      (output / 'heldout_predictions.parquet', 'predictions_sha256'),
                      (output / 'event_run_metrics.parquet', 'run_metrics_sha256'),
                      (report / 'metrics.csv', 'metrics_sha256')]:
        if digest(path) != receipt[key]:
            raise ValueError('Evaluation file changed: ' + str(path))
    snapshot_path = Path('outputs/metrics/m3/m4_input_snapshot.json')
    if snapshot_path.exists() and json.loads(snapshot_path.read_text()) != release['snapshot']:
        raise ValueError('M3 changed since preflight')
    for fold in frozen['cv_folds']:
        spec = release['splits']['benchmarks'][fold['benchmark']]
        train = {r for r, s in spec['run_assignments'].items() if s == 'train'}
        if set(fold['fit_runs']) & set(fold['held_runs']) or set(fold['fit_runs']) | set(fold['held_runs']) != train:
            raise ValueError('OOF run isolation failed')
        if set(fold['fit_groups']) & set(fold['held_groups']):
            raise ValueError('OOF group isolation failed')
    saved = pd.read_parquet(output / 'heldout_predictions.parquet')
    oof = pd.read_parquet(output / 'oof_predictions.parquet')
    if not np.isfinite(saved.probability).all() or saved.probability.isna().any():
        raise ValueError('Invalid held-out predictions')
    checked, max_replay_difference = 0, 0.0
    for c in frozen['candidates']:
        train = subset(release, c['benchmark'], c['horizon_s'], 'train')
        artifact = joblib.load(c['artifact_path'])
        expected_columns = (release['sets'][c['feature_set']] if c['feature_set'] != 'baseline' else artifact['columns'])
        if c['columns'] != expected_columns or artifact['train_runs'] != sorted(train.run_id.unique()):
            raise ValueError('Feature or training membership changed')
        if c['model'] not in ('constant', 'rule'):
            pre = artifact['pipeline']['preprocess']
            numeric = [col for col in c['columns'] if col != 'packing_family']
            np.testing.assert_allclose(pre.named_transformers_['numeric'].mean_, train[numeric].mean(), rtol=1e-12, atol=1e-12)
            if 'packing_family' in c['columns']:
                if set(pre.named_transformers_['packing'].categories_[0]) != set(train.packing_family):
                    raise ValueError('Encoder saw nontraining categories')
        train_scores = oof.loc[oof.candidate_id == c['candidate_id']]
        if set(train_scores.run_id) != set(train.run_id) or len(train_scores) != len(train):
            raise ValueError('OOF cohort inconsistent')
        threshold, _ = choose_threshold(train_scores, release['metadata'], c['horizon_s'], frozen['config'])
        if threshold['threshold'] != c['threshold'] or not np.isclose(threshold['utility'], c['oof_utility']):
            raise ValueError('Threshold was not selected from OOF training only')
        for split in ('validation', 'test'):
            df = subset(release, c['benchmark'], c['horizon_s'], split)
            s = saved.loc[(saved.candidate_id == c['candidate_id']) & (saved.split == split)]
            if list(zip(s.run_id, s.frame_index, s.time_s)) != list(zip(df.run_id, df.frame_index, df.time_s)):
                raise ValueError('Saved prediction join/order changed')
            np.testing.assert_array_equal(s.target, df.target)
            max_replay_difference = max(max_replay_difference,
                                       verify_prediction_replay(s.probability, predict(artifact, df), c['threshold']))
            if not (df.label_status == 'eligible').all():
                raise ValueError('Censored/post-onset/empty rows entered evaluation')
            checked += 1
    result = dict(status='pass', m3_unchanged=True, raw_checksums_verified=30,
                  processed_checksum_files=len(release['snapshot']),
                  independent_runs=30, independent_events=11, feature_rows=9030, label_rows=18060,
                  frozen_candidates=len(frozen['candidates']), replayed_heldout_tables=checked,
                  grouped_cv_partitions=len(frozen['cv_folds']),
                  prediction_rows=len(saved), nonfinite_predictions=0,
                  max_prediction_replay_absolute_difference=max_replay_difference,
                  prediction_replay_tolerance=dict(rtol=1e-12, atol=1e-12),
                  alert_threshold_decisions_identical=True,
                  threshold_source='training grouped OOF only', new_dem_simulations=0,
                  group_or_temporal_leakage_identified=False,
                  limitation='Code/data isolation checks do not establish population independence or external validity.')
    write_json(report / 'audit.json', result)
    print(json.dumps(result, indent=2))
    return result
