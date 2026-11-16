"""Training-only grouped OOF selection and immutable artifact freeze before evaluation."""
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from .m4_data import load_release, subset, run_weights, write_json, digest, KEYS
from .m4_models import fit_baseline, predict, RULE_FEATURES
from .m4_alerts import choose_threshold
from .m4_metrics import frame_metrics


def source_snapshot():
    return {p.name: digest(p) for p in sorted(Path(__file__).parent.glob('m4_*.py'))}


def grouped_folds(train, key, config):
    cv = StratifiedGroupKFold(n_splits=config['cv_folds'], shuffle=True, random_state=config['seed'])
    folds = list(cv.split(train, train.target, train[key]))
    seen = np.zeros(len(train), dtype=int)
    for fit, held in folds:
        if set(train.iloc[fit][key]) & set(train.iloc[held][key]):
            raise ValueError('OOF group leak')
        if set(train.iloc[fit].target) != {0, 1}:
            raise ValueError('OOF training fold has no positive or negative class')
        seen[held] += 1
    if not np.all(seen == 1):
        raise ValueError('Every training row must be held out exactly once')
    return folds


def train(config_path='configs/m4/baselines.json', output='outputs/metrics/m4', models='outputs/checkpoints/m4', root='data/processed/m3'):
    start = time.perf_counter()
    output, models = Path(output), Path(models)
    output.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    freeze_path = output / 'frozen_selection.json'
    if freeze_path.exists():
        raise FileExistsError('Frozen experiment exists; audit/evaluate it or use a distinct output directory. Never silently retune.')
    config = json.loads(Path(config_path).read_text())
    release = load_release(root)
    candidates, oof_tables, thresholds, fold_records, selections = [], [], [], [], {}
    for benchmark in config['benchmarks']:
        selections[benchmark] = {}
        key = release['splits']['benchmarks'][benchmark]['group_key']
        for horizon in config['horizons_s']:
            train_df = subset(release, benchmark, horizon, 'train')
            folds = grouped_folds(train_df, key, config)
            for i, (fit, held) in enumerate(folds):
                fold_records.append(dict(benchmark=benchmark, horizon_s=horizon, fold=i, group_key=key,
                                         fit_runs=sorted(train_df.iloc[fit].run_id.unique()),
                                         held_runs=sorted(train_df.iloc[held].run_id.unique()),
                                         fit_groups=sorted(train_df.iloc[fit][key].unique()),
                                         held_groups=sorted(train_df.iloc[held][key].unique())))
            specs = [('constant', 'baseline', []), ('rule', 'baseline', RULE_FEATURES)]
            specs += [(model, name, columns) for name, columns in release['sets'].items()
                      for model in config['models']]
            cohort = []
            for model, feature_set, columns in specs:
                identifier = f'{benchmark}_h{round(horizon * 1000):03d}_{feature_set}_{model}'
                probs, fold_no = np.full(len(train_df), np.nan), np.full(len(train_df), -1)
                for i, (fit, held) in enumerate(folds):
                    artifact = fit_baseline(model, train_df.iloc[fit], columns, config)
                    probs[held] = predict(artifact, train_df.iloc[held])
                    fold_no[held] = i
                if not np.isfinite(probs).all():
                    raise ValueError('Incomplete OOF predictions')
                oof = train_df[KEYS + ['physical_group_id', 'target']].copy()
                oof['probability'], oof['fold'], oof['candidate_id'] = probs, fold_no, identifier
                best, trace = choose_threshold(oof, release['metadata'], horizon, config)
                weights, _ = run_weights(oof)
                fm = frame_metrics(oof, best['threshold'], weights)
                artifact = fit_baseline(model, train_df, columns, config)
                artifact.update(candidate_id=identifier, train_runs=sorted(train_df.run_id.unique()),
                                benchmark=benchmark, horizon_s=horizon, feature_set=feature_set)
                path = models / (identifier + '.joblib')
                joblib.dump(artifact, path, compress=3)
                record = dict(candidate_id=identifier, benchmark=benchmark, horizon_s=horizon,
                              model=model, feature_set=feature_set, columns=columns,
                              artifact_path=str(path), artifact_sha256=digest(path),
                              threshold=best['threshold'], oof_utility=best['utility'],
                              oof_event=best, oof_frame_equal_run=fm)
                cohort.append(record)
                candidates.append(record)
                oof_tables.append(oof)
                thresholds.extend(dict(candidate_id=identifier, **r) for r in trace)
                print(identifier, 'OOF useful recall', best['useful_event_recall'], 'utility', round(best['utility'], 4), flush=True)
            # Prespecified: utility, then equal-run AP, then fewer features and simpler model.
            simplicity = {'constant': 4, 'rule': 3, 'logistic': 2, 'forest': 1, 'xgboost': 0}
            selected = max(cohort, key=lambda r: (r['oof_utility'], r['oof_frame_equal_run']['average_precision'] or 0,
                                                   -len(r['columns']), simplicity[r['model']], r['candidate_id']))
            selections[benchmark][str(horizon)] = selected['candidate_id']
    pd.concat(oof_tables, ignore_index=True).to_parquet(output / 'oof_predictions.parquet', index=False)
    pd.DataFrame(thresholds).to_csv(output / 'threshold_search.csv', index=False, lineterminator='\n')
    freeze = dict(protocol=config['protocol'], config=config, config_sha256=digest(config_path),
                  git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  source_sha256=source_snapshot(), m3_snapshot=release['snapshot'],
                  selection_inputs='training grouped out-of-fold predictions only; no validation or test metrics',
                  selected=selections, candidates=candidates, cv_folds=fold_records,
                  oof_sha256=digest(output / 'oof_predictions.parquet'),
                  versions={p: importlib.metadata.version(p) for p in
                            ('scikit-learn', 'xgboost-cpu', 'joblib', 'numpy', 'pandas', 'pyarrow', 'taichi')},
                  training_wall_s=time.perf_counter() - start)
    write_json(freeze_path, freeze)  # written last: only a complete experiment can be evaluated
    print('FROZEN', digest(freeze_path), json.dumps(selections), flush=True)
    return freeze
