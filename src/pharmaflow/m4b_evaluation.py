"""Exactly-once unseen-configuration evaluation after model AND online-policy freeze."""
from pathlib import Path
import json
import time
import joblib
import numpy as np
import pandas as pd
from .m4_data import digest, write_json, exact_join, KEYS
from .m4b_models import predict
from .m4_metrics import frame_metrics
from .m4b_data import build_release, load_tables, verify_release
from .m4b_campaign import locked_gate
from .m4b_online import summarize_runs, summary
from .m4b_training import source_hashes


def verify_freeze(root='data/simulated/m4b', output='outputs/metrics/m4b'):
    path = Path(output)/'model_and_policy_freeze.json'
    frozen = locked_gate(root, path)
    if frozen['source_sha256'] != source_hashes():
        raise ValueError('Frozen M4B source changed')
    if frozen['development_manifest_sha256'] != digest('data/processed/m4b/development/dataset_manifest.json'):
        raise ValueError('Frozen development release changed')
    if frozen['oof_sha256'] != digest(Path(output)/'oof_full_predictions.parquet'):
        raise ValueError('OOF scores changed')
    if frozen['policy_search_sha256'] != digest(Path(output)/'policy_search.csv'):
        raise ValueError('Training policy search changed')
    return frozen


def evaluate_tables(candidates, tables, scope, config):
    scores_all, runs_all, metrics = [], [], []
    features, labels, meta = (tables[n] for n in ('temporal_features', 'event_labels', 'run_metadata'))
    features = features.sort_values(KEYS[:2]).reset_index(drop=True)
    for c in candidates:
        horizon, identifier = c['horizon_s'], c['candidate_id']
        artifact = joblib.load(c['artifact_path'])
        scores = features[KEYS+['physical_group_id']].assign(probability=predict(artifact, features))
        eligible = exact_join(features, labels, horizon).merge(scores[KEYS+['probability']], on=KEYS, validate='one_to_one')
        fm = frame_metrics(eligible, c['threshold'])
        for mode in ('online', 'eligible'):
            run_rows = summarize_runs(scores, features, labels, meta, horizon, c['threshold'], c['policy'], mode,
                                      config['minimum_useful_lead_s'])
            common = dict(candidate_id=identifier, scope=scope, horizon_s=horizon, replay=mode,
                          model=c['model'], feature_set=c['feature_set'], origin=c['origin'],
                          threshold=c['threshold'], policy=c['policy']['name'])
            metrics.append(dict(**common, **fm, **summary(run_rows)))
            for key,value in common.items():
                run_rows[key] = value
            runs_all.append(run_rows)
        scores_all.append(scores.assign(candidate_id=identifier, scope=scope, horizon_s=horizon))
    return pd.concat(scores_all, ignore_index=True), pd.concat(runs_all, ignore_index=True), pd.DataFrame(metrics)


def bootstrap_comparison(scores, runs, candidate, rule_id, labels, repeats, seed):
    """Paired configuration resampling, preserving every run and frame in each cluster."""
    selected = runs.loc[(runs.candidate_id == candidate['candidate_id']) & (runs.replay == 'online')].copy()
    rule = runs.loc[(runs.candidate_id == rule_id) & (runs.replay == 'online')].set_index('run_id').loc[selected.run_id].reset_index()
    groups = sorted(selected.physical_group_id.unique())
    rng = np.random.default_rng(seed)
    p = scores.loc[scores.candidate_id == candidate['candidate_id']].merge(
        labels.loc[(labels.horizon_s == candidate['horizon_s']) & (labels.label_status == 'eligible'), KEYS+['target']],
        on=KEYS, validate='one_to_one')
    p['target'] = p.target.astype(int)
    values = {'ap':[], 'useful_recall':[], 'paired_useful_recall_gain':[], 'false_per_operating_s':[]}
    for _ in range(repeats):
        sampled = rng.choice(groups, len(groups), replace=True)
        counts = {g:int((sampled == g).sum()) for g in groups}
        weights = selected.physical_group_id.map(counts)
        a, b = summary(selected, weights), summary(rule, weights)
        if a['useful_event_recall'] is not None:
            values['useful_recall'].append(a['useful_event_recall'])
            values['paired_useful_recall_gain'].append(a['useful_event_recall']-b['useful_event_recall'])
        values['false_per_operating_s'].append(a['false_per_operating_s'])
        frame_w = p.physical_group_id.map(counts).to_numpy(float)
        if np.dot(frame_w, p.target) > 0:
            fm = frame_metrics(p.loc[frame_w>0], candidate['threshold'], frame_w[frame_w>0])
            values['ap'].append(fm['average_precision'])
    return dict(physical_clusters=len(groups), replicates=repeats,
                intervals={k:dict(lower=float(np.quantile(v,.025)), upper=float(np.quantile(v,.975)),
                                  defined_replicates=len(v)) if v else None for k,v in values.items()},
                limitation='Four test configurations give descriptive, potentially degenerate cluster intervals, not industrial validation.')


def readiness(ml, rule, event_configs, interval, config):
    criterion = config['decision']
    if ml['events'] < criterion['minimum_locked_events'] or event_configs < criterion['minimum_event_configurations']:
        return 'M4B_INSUFFICIENT_INDEPENDENT_EVENT_EVIDENCE'
    gain = ml['useful_event_recall']-rule['useful_event_recall']
    added_false = ml['false_per_operating_s']-rule['false_per_operating_s']
    lower = interval['intervals']['paired_useful_recall_gain']
    if (gain >= criterion['minimum_ml_recall_gain'] and added_false <= criterion['maximum_added_false_per_operating_s']
            and lower is not None and lower['lower'] > 0):
        return 'M4B_EVIDENCE_SUPPORTS_FURTHER_TEMPORAL_MODELING'
    return 'M4B_RULE_BASELINE_REMAINS_COMPETITIVE'


def evaluate_locked(root='data/simulated/m4b', data='data/processed/m4b', output='outputs/metrics/m4b', report='docs/results/m4b'):
    start = time.perf_counter()
    output, report, data = Path(output), Path(report), Path(data)
    receipt = output/'locked_evaluation_receipt.json'
    if receipt.exists():
        raise FileExistsError('Locked evaluation already consumed; audit saved results instead')
    frozen = verify_freeze(root, output)
    access = json.loads((Path(root)/'manifests/locked_access_receipt.json').read_text())
    if access['model_freeze_sha256'] != digest(output/'model_and_policy_freeze.json'):
        raise ValueError('Models/policies changed after opening locked generation')
    build_release('locked', root, data, output/'model_and_policy_freeze.json')
    verify_release(data/'development')
    locked = load_tables(data/'locked')
    dev = load_tables(data/'development')
    split = json.loads((data/'development/split_manifest.json').read_text())
    validation_ids = {r for r,s in split['assignments'].items() if s == 'validation'}
    validation = {name:table.loc[table.run_id.isin(validation_ids)].copy() for name,table in dev.items()}
    valid_locked = set(locked['run_metadata'].loc[locked['run_metadata'].status == 'ok'].run_id)
    locked = {name:table.loc[table.run_id.isin(valid_locked)].copy() for name,table in locked.items()}
    tables = [evaluate_tables(frozen['candidates'], table, scope, frozen['config']) for scope,table in
              [('development_validation', validation), ('locked', locked)]]
    scores, runs, metrics = [pd.concat([t[i] for t in tables], ignore_index=True) for i in range(3)]
    selected_ids = {v for selection in frozen['selected'].values() for v in selection.values()}
    metrics['selected'] = metrics.candidate_id.isin(selected_ids)
    report.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(output/'predictions.parquet', index=False)
    runs.to_parquet(output/'event_run_metrics.parquet', index=False)
    metrics.to_csv(report/'metrics.csv', index=False, lineterminator='\n')
    metrics.loc[metrics.selected].to_csv(report/'selected_metrics.csv', index=False, lineterminator='\n')
    runs.loc[runs.candidate_id.isin(selected_ids)].to_csv(report/'selected_event_runs.csv', index=False, lineterminator='\n')
    uncertainty = {}
    locked_runs = runs.loc[runs.scope == 'locked']
    locked_scores = scores.loc[scores.scope == 'locked']
    for h, selection in frozen['selected'].items():
        c = next(c for c in frozen['candidates'] if c['candidate_id'] == selection['ml'])
        uncertainty[h] = bootstrap_comparison(locked_scores, locked_runs, c, selection['physics_rule'],
                                              locked['event_labels'], frozen['config']['bootstrap_repeats'], frozen['config']['seed'])
    main = frozen['selected']['0.1']
    ml = summary(locked_runs.loc[(locked_runs.candidate_id == main['ml']) & (locked_runs.replay == 'online')])
    rule = summary(locked_runs.loc[(locked_runs.candidate_id == main['physics_rule']) & (locked_runs.replay == 'online')])
    event_configs = locked['run_metadata'].loc[locked['run_metadata'].confirmed_event_count>0, 'physical_group_id'].nunique()
    decision = readiness(ml, rule, event_configs, uncertainty['0.1'], frozen['config'])
    subgroup = []
    for identifier in sorted(selected_ids):
        rows = locked_runs.loc[(locked_runs.candidate_id == identifier) & (locked_runs.replay == 'online')]
        for variable in ('physical_group_id', 'outlet_ratio', 'friction', 'wall_friction', 'wall_angle_deg', 'packing_family'):
            for value, group in rows.groupby(variable):
                subgroup.append(dict(candidate_id=identifier, variable=variable, value=value, **summary(group)))
        resumed = rows.loc[rows.temporary_gap_count > 0]
        if len(resumed):
            subgroup.append(dict(candidate_id=identifier, variable='later_resumed_gap', value=True, **summary(resumed)))
    pd.DataFrame(subgroup).to_csv(report/'subgroup_metrics.csv', index=False, lineterminator='\n')
    write_json(report/'uncertainty.json', uncertainty)
    write_json(report/'model_and_policy_freeze.json', frozen)
    write_json(report/'summary.json', dict(decision=decision, selected=frozen['selected'],
               locked_event_configurations=int(event_configs), primary_ml=ml, primary_rule=rule,
               training_wall_s=frozen['training_wall_s'], evaluation_wall_s=time.perf_counter()-start,
               locked_manifest=verify_release(data/'locked'), test_used_for_selection=False))
    write_json(receipt, dict(model_freeze_sha256=digest(output/'model_and_policy_freeze.json'),
               predictions_sha256=digest(output/'predictions.parquet'), runs_sha256=digest(output/'event_run_metrics.parquet'),
               metrics_sha256=digest(report/'metrics.csv'), completed=True))
    print(decision)
    print(metrics.loc[metrics.selected & (metrics.replay == 'online'), ['scope','horizon_s','model','feature_set',
          'average_precision','useful_hits','events','false_forecasts','post_onset_alerts','false_per_operating_s']].to_string(index=False))
    return decision
