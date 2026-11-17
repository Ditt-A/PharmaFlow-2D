"""Expanded-development fits and policy selection, with no locked outcomes on disk."""
from pathlib import Path
import json
import time
import importlib.metadata
import joblib
import numpy as np
import pandas as pd
from .m4_data import digest, write_json, exact_join, feature_sets, run_weights, KEYS
from .m4_models import fit_baseline, RULE_FEATURES
from .m4b_models import predict
from .m4_metrics import frame_metrics
from .m4_training import grouped_folds
from .m4b_data import load_development
from .m4b_online import select_policy
from .m4b_campaign import now


def source_hashes():
    return {p.name:digest(p) for p in sorted(Path(__file__).parent.glob('m4b_*.py'))}


def freeze_train(config_path='configs/m4b/baselines.json', root='data/simulated/m4b',
                 data='data/processed/m4b/development', output='outputs/metrics/m4b',
                 models='outputs/checkpoints/m4b'):
    start = time.perf_counter()
    root, output, models = Path(root), Path(output), Path(models)
    output.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    freeze_path = output/'model_and_policy_freeze.json'
    if freeze_path.exists() or any((root/'locked').glob('*/run.json')):
        raise ValueError('Never refit/retune after freeze or locked generation')
    tables, split, manifest = load_development(data)
    config = json.loads(Path(config_path).read_text())
    dictionary = json.loads((Path(data)/'feature_dictionary.json').read_text())
    sets = feature_sets(dictionary)
    candidates, searches, oof_all, folds_all = [], [], [], []
    selected = {}
    for horizon in config['horizons_s']:
        eligible = exact_join(tables['temporal_features'], tables['event_labels'], horizon)
        train_df = eligible.loc[eligible.run_id.map(split['assignments']) == 'train'].reset_index(drop=True)
        train_ids = set(train_df.run_id)
        full_train = tables['temporal_features'].loc[tables['temporal_features'].run_id.isin(train_ids)].sort_values(KEYS[:2]).reset_index(drop=True)
        train_tables = {name:table.loc[table.run_id.isin(train_ids)].copy() for name,table in tables.items()}
        folds = grouped_folds(train_df, 'physical_group_id', config)
        for i, (fit, held) in enumerate(folds):
            folds_all.append(dict(horizon_s=horizon, fold=i,
                                  fit_runs=sorted(train_df.iloc[fit].run_id.unique()),
                                  held_runs=sorted(train_df.iloc[held].run_id.unique()),
                                  fit_groups=sorted(train_df.iloc[fit].physical_group_id.unique()),
                                  held_groups=sorted(train_df.iloc[held].physical_group_id.unique())))
        cohort = []
        specs = [(model, name, sets[name]) for name in config['feature_sets'] for model in config['models']]
        specs.append(('rule', 'physics_rule', RULE_FEATURES))
        for model, name, columns in specs:
            identifier = f'm4b_h{round(horizon*1000):03d}_{name}_{model}'
            probs = np.full(len(full_train), np.nan)
            for i, (fit, held) in enumerate(folds):
                artifact = fit_baseline(model, train_df.iloc[fit], columns, config)
                held_ids = set(train_df.iloc[held].run_id)
                mask = full_train.run_id.isin(held_ids)
                probs[mask] = predict(artifact, full_train.loc[mask])
            if not np.isfinite(probs).all():
                raise ValueError('OOF chronological coverage incomplete')
            oof = full_train[KEYS+['physical_group_id']].assign(probability=probs)
            best, trace = select_policy(oof, train_tables, horizon, config)
            eligible_scores = train_df.merge(oof[KEYS+['probability']], on=KEYS, validate='one_to_one')
            weights, _ = run_weights(eligible_scores)
            fm = frame_metrics(eligible_scores, best['threshold'], weights)
            artifact = fit_baseline(model, train_df, columns, config)
            path = models/(identifier+'.joblib')
            artifact.update(candidate_id=identifier, train_runs=sorted(train_ids), horizon_s=horizon,
                            feature_set=name, source_sha256=source_hashes())
            joblib.dump(artifact, path, compress=3)
            record = dict(candidate_id=identifier, horizon_s=horizon, model=model, feature_set=name, columns=columns,
                          artifact_path=str(path), artifact_sha256=digest(path), threshold=best['threshold'],
                          policy=best['policy'], origin='m4b_refit' if model != 'rule' else 'm4a_rule_score_reselected_policy',
                          oof_utility=best['utility'], oof_online=best, oof_equal_run_frame=fm)
            cohort.append(record)
            candidates.append(record)
            legacy_best = max([r for r in trace if r['policy']['name'] == 'legacy_m4a'],
                              key=lambda r:(r['utility'], r['threshold']))
            candidates.append(dict(record, candidate_id=identifier+'_legacy_policy',
                                   threshold=legacy_best['threshold'], policy=legacy_best['policy'],
                                   oof_utility=legacy_best['utility'], oof_online=legacy_best,
                                   oof_equal_run_frame=frame_metrics(eligible_scores, legacy_best['threshold'], weights),
                                   origin=record['origin']+'_legacy_policy_comparison'))
            oof_all.append(oof.assign(candidate_id=identifier))
            searches.extend(dict(candidate_id=identifier, **r) for r in trace)
            print(identifier, 'OOF useful', best['useful_event_recall'], 'false', best['false_forecasts'],
                  'policy', best['policy']['name'], 'threshold', best['threshold'], flush=True)
        ml = [r for r in cohort if r['model'] != 'rule']
        best_ml = max(ml, key=lambda r:(r['oof_utility'], r['oof_equal_run_frame']['average_precision'] or 0,
                                       -len(r['columns']), {'logistic':2, 'forest':1, 'xgboost':0}[r['model']]))
        selected[str(horizon)] = dict(ml=best_ml['candidate_id'], physics_rule=cohort[-1]['candidate_id'])
    # Preserve exact old model artifacts and thresholds, with no fitting on new data.
    old = json.loads(Path('outputs/metrics/m4/frozen_selection.json').read_text())
    legacy = config['policies'][0]
    for c in old['candidates']:
        include = ((c['benchmark'] == 'configuration_holdout' and c['feature_set'] == 'B_current') or
                   (c['benchmark'] == 'configuration_holdout' and c['model'] == 'rule') or
                   (c['benchmark'] == 'run_grouped' and c['feature_set'] == 'B_current' and c['model'] == 'forest'))
        if include:
            if digest(c['artifact_path']) != c['artifact_sha256']:
                raise ValueError('Historical model modified')
            candidates.append(dict(candidate_id='frozen_'+c['candidate_id'], horizon_s=c['horizon_s'], model=c['model'],
                                   feature_set=c['feature_set'], columns=c['columns'], artifact_path=c['artifact_path'],
                                   artifact_sha256=c['artifact_sha256'], threshold=c['threshold'], policy=legacy,
                                   origin='frozen_m4a_'+c['benchmark']))
    pd.concat(oof_all, ignore_index=True).to_parquet(output/'oof_full_predictions.parquet', index=False)
    pd.DataFrame([dict(r, policy=json.dumps(r['policy'], sort_keys=True)) for r in searches]).to_csv(
        output/'policy_search.csv', index=False, lineterminator='\n')
    result = dict(protocol=config['protocol'], config=config, config_sha256=digest(config_path),
                  source_sha256=source_hashes(), candidates=candidates, selected=selected, cv_folds=folds_all,
                  design_freeze_sha256=digest(root/'manifests/design_freeze.json'),
                  development_manifest_sha256=digest(Path(data)/'dataset_manifest.json'),
                  m4a_freeze_sha256=digest('outputs/metrics/m4/frozen_selection.json'),
                  locked_outcomes_seen=False, selection_inputs='training-only grouped OOF full chronological replay',
                  frozen_utc=now(), versions={p:importlib.metadata.version(p) for p in
                    ('scikit-learn','xgboost-cpu','numpy','pandas','pyarrow','joblib','taichi')},
                  oof_sha256=digest(output/'oof_full_predictions.parquet'),
                  policy_search_sha256=digest(output/'policy_search.csv'),
                  training_wall_s=time.perf_counter()-start)
    write_json(freeze_path, result)
    print('MODEL_POLICY_FROZEN', digest(freeze_path), json.dumps(selected), flush=True)
    return result
