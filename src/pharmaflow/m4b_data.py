"""Versioned M4B releases; copy only historically permitted M3 training runs."""
from dataclasses import asdict
from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
from .config import HopperConfig
from .run import load_run
from .m3_dataset import physical_group
from .m3_features import extract_features
from .m3_events import detect_events, label_frames
from .m4_data import write_json, digest, exact_join, feature_sets
from .m4b_campaign import locked_gate


def historical_training_ids(split_manifest):
    """Never promote ANY published M3 validation/test run into new training."""
    return sorted(set.intersection(*[{r for r, s in spec['run_assignments'].items() if s == 'train'}
                                    for spec in split_manifest['benchmarks'].values()]))


def assign_development(meta, validation_cases):
    assignments = {r.run_id: ('validation' if r.case_name in validation_cases else 'train')
                   for r in meta.itertuples()}
    groups = pd.DataFrame({'group': meta.physical_group_id, 'split': meta.run_id.map(assignments)})
    if groups.groupby('group').split.nunique().max() > 1:
        raise ValueError('Physical configuration crosses development splits')
    return assignments


def read_records(root, phases):
    records = []
    for phase in phases:
        path = Path(root) / 'manifests' / (phase + '_campaign.json')
        report = json.loads(path.read_text())
        if report['state'] != 'complete':
            raise ValueError('Incomplete campaign')
        records.extend(report['records'])
    return records


def record_tables(records):
    metadata, features, labels, events, sensitivity, raw_files = [], [], [], [], [], []
    for r in records:
        base = {k:r.get(k) for k in ('run_id', 'configuration_id', 'case_name', 'phase', 'seed',
                'packing_family', 'packing_id', 'initial_state_sha256', 'solver_version',
                'solver_source_sha256', 'status', 'numerical_valid', 'runtime_s', 'continued')}
        base.update(cohort='m4b', physical_parameters_json=json.dumps(r['physical'], sort_keys=True),
                    numerical_parameters_json=json.dumps(r['numerical'], sort_keys=True), error=r.get('error'),
                    sample_interval_s=r['sample_interval_s'], planned_duration_s=r['duration_s'],
                    maximum_duration_s=r['max_duration_s'])
        if r['status'] != 'ok':
            base.update(confirmed_event_count=0, censored_run=False, flow_state='numerical_failure',
                        event_onsets_json='[]', event_confirmations_json='[]')
            metadata.append(base)
            continue
        path = Path(r['trajectory_path'])
        if digest(path) != r['npz_sha256']:
            raise ValueError('Trajectory checksum changed')
        arrays, _ = load_run(path)
        c = HopperConfig(**r['config'])
        ev = detect_events(arrays, c.gate_open_time_s, r['protocol'])
        if ev != r['events']:
            raise ValueError('Cached event result differs from unchanged M3 protocol')
        identity = {k:r[k] for k in ('run_id', 'configuration_id')}
        identity['physical_group_id'] = physical_group(r['config'])
        crossings = np.sort(arrays['crossing_time_s'][np.isfinite(arrays['crossing_time_s'])])
        gaps = np.diff(crossings)
        base.update(**{k:v for k,v in identity.items() if k == 'physical_group_id'}, config_json=json.dumps(r['config'], sort_keys=True),
                    trajectory_path=str(path), npz_sha256=r['npz_sha256'], trajectory_sha256=r['trajectory_sha256'],
                    observation_duration_s=float(arrays['time_s'][-1]), gate_open_s=c.gate_open_time_s,
                    confirmed_event_count=len(ev), censored_run=bool(not ev and arrays['remaining_count'][-1] > 0),
                    flow_state=r['flow_state'], event_onsets_json=json.dumps([e['onset_time_s'] for e in ev]),
                    event_confirmations_json=json.dumps([e['confirmation_time_s'] for e in ev]),
                    resumed_after_first_event=bool(ev and ev[0]['resumed_crossing_after_event']),
                    temporary_gap_count=int((gaps >= .05).sum()), maximum_resumed_gap_s=float(gaps.max()) if len(gaps) else 0.,
                    outlet_ratio=c.outlet_width_m/(2*c.particle_radius_m), friction=c.friction,
                    wall_friction=c.wall_friction, initial_particle_count=c.n_particles, dt_s=c.dt_s,
                    wall_angle_deg=float(np.degrees(np.arctan((c.width_m-c.outlet_width_m)/(2*c.funnel_height_m)))),
                    max_overlap_over_radius=r['checks']['max_overlap_over_radius'])
        metadata.append(base)
        feat = extract_features(arrays, c, r['packing_family'])
        # Causal-prefix QA uses the identical M3 function on a genuine saved prefix.
        cut = max(2, len(arrays['time_s']) // 3)
        prefix = {k:(v[:cut] if np.ndim(v) and len(v) == len(arrays['time_s']) else v) for k,v in arrays.items()}
        if feat[:cut] != extract_features(prefix, c, r['packing_family']):
            raise ValueError('Feature prefix is not causal')
        features.extend(dict(f, **identity) for f in feat)
        labels.extend(dict(l, **identity) for l in label_frames(arrays, ev, gate_open_s=c.gate_open_time_s, protocol=r['protocol']))
        events.extend(dict(e, **identity) for e in ev)
        for p in (.2, .4, .6):
            found = detect_events(arrays, c.gate_open_time_s, dict(r['protocol'], persistence_s=p))
            sensitivity.append(dict(run_id=r['run_id'], physical_group_id=identity['physical_group_id'],
                                    persistence_s=p, event_count=len(found),
                                    onset_s=found[0]['onset_time_s'] if found else None))
        raw_files.append(dict(run_id=r['run_id'], path=str(path), sha256=digest(path), initial_sha256=r['initial_state_sha256']))
        if not np.isclose(np.diff(arrays['time_s']), r['sample_interval_s'], rtol=0, atol=1e-10).all():
            raise ValueError('Nonuniform timestamps')
        expected = np.array([np.sum(np.isfinite(arrays['crossing_time_s']) &
                                     (arrays['crossing_time_s'] <= t+1e-12)) for t in arrays['time_s']])
        if (np.any(np.diff(arrays['active'].astype(int), axis=0) > 0)
                or not np.array_equal(expected, arrays['discharged_count'])
                or np.any((~arrays['active']) & ~np.isfinite(arrays['crossing_time_s'])[None, :])):
            raise ValueError('Particle conservation failure')
        if r['checks']['max_overlap_over_radius'] > .15:
            raise ValueError('Overlap guard violation')
    return metadata, features, labels, events, sensitivity, raw_files


def verify_release(path):
    path = Path(path)
    m = json.loads((path/'dataset_manifest.json').read_text())
    for name, sha in m['files'].items():
        if digest(path/name) != sha:
            raise ValueError('M4B release checksum mismatch: '+name)
    return m


def build_release(scope='development', root='data/simulated/m4b', output='data/processed/m4b',
                  model_freeze='outputs/metrics/m4b/model_and_policy_freeze.json'):
    root, target = Path(root), Path(output)/scope
    if (target/'dataset_manifest.json').exists():
        return verify_release(target)
    design = json.loads((root/'manifests/design_freeze.json').read_text())
    if scope == 'locked':
        locked_gate(root, model_freeze)
        receipt = json.loads((root/'manifests/locked_access_receipt.json').read_text())
        if receipt['model_freeze_sha256'] != digest(model_freeze):
            raise ValueError('Model/policy freeze changed after locked dispatch')
        phases = ['locked']
    elif scope in ('pilot', 'development'):
        phases = ['pilot'] if scope == 'pilot' else ['pilot', 'adaptive']
    else:
        raise ValueError(scope)
    records = read_records(root, phases)
    metadata, features, labels, events, sensitivity, raw = record_tables(records)
    meta, feat, lab = pd.DataFrame(metadata), pd.DataFrame(features), pd.DataFrame(labels)
    dictionary = json.loads(Path('data/processed/m3/feature_dictionary.json').read_text())
    validation = design['design']['pilot_validation_cases'][:]
    allowed_old = []
    if scope == 'development':
        adaptive = json.loads(Path('configs/m4b/adaptive.json').read_text())
        validation += adaptive['validation_cases']
        split = json.loads(Path('data/processed/m3/split_manifest.json').read_text())
        allowed_old = historical_training_ids(split)
        old_meta = pd.read_parquet('data/processed/m3/run_metadata.parquet')
        old_meta = old_meta.loc[old_meta.run_id.isin(allowed_old)].assign(cohort='m3_permitted_train', case_name='historical_training', gate_open_s=.05)
        meta = pd.concat([meta, old_meta], ignore_index=True)
        for name, table in [('temporal_features', feat), ('event_labels', lab)]:
            old = pd.read_parquet('data/processed/m3/'+name+'.parquet')
            combined = pd.concat([table, old.loc[old.run_id.isin(allowed_old)]], ignore_index=True)
            if name == 'temporal_features': feat = combined
            else: lab = combined
    lab['target'] = pd.array(lab.target, dtype='Int8')
    valid = meta.loc[meta.status == 'ok']
    assignment = {r:'locked' for r in valid.run_id} if scope == 'locked' else assign_development(valid, validation)
    if feat.isna().any().any() or not np.isfinite(feat.select_dtypes('number')).all().all():
        raise ValueError('Missing/nonfinite causal predictors')
    if set(feat.columns) != set(dictionary):
        raise ValueError('Feature dictionary changed')
    if len(set(valid.initial_state_sha256)) != len(valid):
        raise ValueError('Duplicate initial state')
    for h in (.1, .05):
        exact_join(feat, lab, h)
    target.mkdir(parents=True, exist_ok=True)
    for name, table in [('run_metadata', meta), ('temporal_features', feat), ('event_labels', lab),
                        ('events', pd.DataFrame(events)), ('persistence_sensitivity', pd.DataFrame(sensitivity))]:
        table.to_parquet(target/(name+'.parquet'), index=False)
    shutil.copyfile('data/processed/m3/feature_dictionary.json', target/'feature_dictionary.json')
    write_json(target/'split_manifest.json', dict(assignments=assignment, group_key='physical_group_id',
               allowed_m3_train_runs=allowed_old, validation_cases=validation, locked_outcomes_used=False))
    manifest = dict(scope=scope, new_attempts=len(records), new_successful=sum(r['status']=='ok' for r in records),
                    new_failed=sum(r['status']!='ok' for r in records), rows=len(feat), label_rows=len(lab),
                    events=int(valid.confirmed_event_count.sum()), censored_runs=int(valid.censored_run.fillna(False).sum()),
                    raw=raw, design_freeze_sha256=digest(root/'manifests/design_freeze.json'),
                    features_unchanged_from_m3=True,
                    files={p.name:digest(p) for p in sorted(target.iterdir()) if p.is_file()})
    write_json(target/'dataset_manifest.json', manifest)
    return manifest


def load_development(path='data/processed/m4b/development'):
    path = Path(path)
    manifest = verify_release(path)
    if manifest['scope'] != 'development':
        raise ValueError('Training loader rejects locked data')
    split = json.loads((path/'split_manifest.json').read_text())
    return load_tables(path), split, manifest


def load_tables(path):
    path = Path(path)
    return {name:pd.read_parquet(path/(name+'.parquet')) for name in
            ('run_metadata', 'temporal_features', 'event_labels')}
