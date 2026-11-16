"""Read the frozen M3 release without rebuilding, relabeling or simulating it."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEYS = ['run_id', 'frame_index', 'time_s']
CURRENT = ['active_count', 'remaining_count', 'near_count', 'near_occupancy_estimate',
           'speed_mean_m_s', 'speed_p50_m_s', 'speed_p95_m_s', 'near_vx_mean_m_s',
           'near_vy_mean_m_s', 'near_speed_mean_m_s', 'near_max_speed_m_s',
           'near_stationary_fraction', 'near_coordination_mean', 'near_coordination_p95',
           'spanning_arch_now', 'near_missing', 'active_missing']
ARCH_PROXIES = ['spanning_arch_now', 'near_stationary_fraction', 'near_max_speed_m_s',
                'near_coordination_mean', 'near_coordination_p95']
CUMULATIVE_PROXIES = ['time_s', 'discharged_fraction', 'active_count', 'remaining_count',
                      'has_observed_crossing', 'since_last_crossing_s',
                      'history_coverage_50ms_s', 'history_coverage_100ms_s']
FORBIDDEN = {'run_id', 'configuration_id', 'physical_group_id', 'frame_index', 'seed',
             'target', 'label_status', 'onset_time_s', 'confirmation_time_s', 'flow_state'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def feature_sets(dictionary):
    """Whitelist solely from the released dictionary; metadata is never a predictor."""
    full = [k for k, v in dictionary.items() if v['role'] == 'predictor']
    static = [k for k in full if dictionary[k]['availability'] == 'static experiment configuration']
    temporal = [k for k in full if dictionary[k]['window_s'] > 0 or
                k in ('since_last_crossing_s', 'has_observed_crossing')]
    sets = dict(A_static=static, B_current=CURRENT,
                C_temporal=temporal + ['near_count', 'remaining_count', 'near_missing', 'active_missing'],
                D_full=full, E_without_arch=[k for k in full if k not in ARCH_PROXIES],
                F_without_time_discharge=[k for k in full if k not in CUMULATIVE_PROXIES])
    for name, cols in sets.items():
        if len(set(cols)) != len(cols) or set(cols) - set(full) or set(cols) & FORBIDDEN:
            raise ValueError('Unsafe feature whitelist: ' + name)
    return sets


def exact_join(features, labels, horizon):
    """A separate one-to-one join per H, using exact stored timestamps (no rounding)."""
    sub = labels.loc[labels.horizon_s == horizon].copy()
    if sub.empty or features.duplicated(KEYS).any() or sub.duplicated(KEYS).any():
        raise ValueError('Missing horizon or duplicate run/frame/time key')
    shared = ['configuration_id', 'physical_group_id']
    result = features.merge(sub, on=KEYS, how='outer', validate='one_to_one',
                            suffixes=('', '_label'), indicator=True)
    if len(result) != len(features) or not (result['_merge'] == 'both').all():
        raise ValueError('Feature/label keys do not match exactly')
    for col in shared:
        if not (result[col] == result[col + '_label']).all():
            raise ValueError('Inconsistent identity: ' + col)
    eligible = result.loc[result.label_status == 'eligible'].drop(columns=['_merge']).copy()
    if not eligible.target.isin([0, 1]).all():
        raise ValueError('Eligible target must be binary and observed')
    eligible['target'] = eligible.target.astype(int)
    return eligible.sort_values(KEYS[:2]).reset_index(drop=True)


def load_release(root='data/processed/m3', verify_raw=True):
    root = Path(root)
    manifest = json.loads((root / 'dataset_manifest.json').read_text())
    for name, info in manifest['files'].items():
        p = root / name
        if digest(p) != info['sha256'] or p.stat().st_size != info['bytes']:
            raise ValueError('M3 checksum mismatch: ' + name)
    if verify_raw:
        for item in manifest['raw_trajectories']:
            if digest(item['path']) != item['sha256']:
                raise ValueError('Raw trajectory checksum mismatch: ' + item['run_id'])
    dictionary = json.loads((root / 'feature_dictionary.json').read_text())
    splits = json.loads((root / 'split_manifest.json').read_text())
    published = Path('docs/results/m3/split_manifest.json')
    if published.exists() and splits != json.loads(published.read_text()):
        raise ValueError('Published split changed')
    meta = pd.read_parquet(root / 'run_metadata.parquet')
    features = pd.read_parquet(root / 'temporal_features.parquet')
    labels = pd.read_parquet(root / 'event_labels.parquet')
    if (len(meta), int(meta.confirmed_event_count.sum()), len(features), len(labels)) != (30, 11, 9030, 18060):
        raise ValueError('Not the frozen 30-run M3 release')
    if set(labels.horizon_s) != {.05, .10} or meta.run_id.duplicated().any():
        raise ValueError('Invalid horizons or duplicate run metadata')
    if features.isna().any().any() or not np.isfinite(features.select_dtypes('number')).all().all():
        raise ValueError('Missing/nonfinite features')
    if set(features.columns) != set(dictionary):
        raise ValueError('Feature dictionary/schema mismatch')
    sets = feature_sets(dictionary)
    expected = {'run_grouped': [18, 6, 6], 'configuration_holdout': [20, 5, 5]}
    for name, spec in splits['benchmarks'].items():
        assigned = meta.run_id.map(spec['run_assignments'])
        if assigned.isna().any() or set(spec['run_assignments']) != set(meta.run_id):
            raise ValueError('Incomplete split')
        if [(assigned == s).sum() for s in ('train', 'validation', 'test')] != expected[name]:
            raise ValueError('Split run counts changed')
        if pd.DataFrame({'group': meta[spec['group_key']], 'split': assigned}).groupby('group').split.nunique().max() != 1:
            raise ValueError('Group leakage')
    joined = {h: exact_join(features, labels, h) for h in (.1, .05)}
    for h, df in joined.items():
        if (len(df), int(df.target.sum())) != (1676, 220 if h == .1 else 110):
            raise ValueError('Eligible cohort changed')
    return dict(metadata=meta, features=features, labels=labels, joined=joined, sets=sets,
                dictionary=dictionary, splits=splits, manifest=manifest,
                snapshot={p.name: digest(p) for p in sorted(root.iterdir()) if p.is_file()})


def subset(release, benchmark, horizon, split):
    spec = release['splits']['benchmarks'][benchmark]
    df = release['joined'][horizon]
    return df.loc[df.run_id.map(spec['run_assignments']) == split].copy().reset_index(drop=True)


def run_weights(df, balance_classes=False):
    """Each run initially has equal total weight; class multipliers use this fold only."""
    weights = 1.0 / df.groupby('run_id').run_id.transform('size').to_numpy(float)
    prevalence = float(np.average(df.target, weights=weights))
    if balance_classes:
        if not 0 < prevalence < 1:
            raise ValueError('Training fold must contain both classes')
        weights *= np.where(df.target.to_numpy() == 1, .5 / prevalence, .5 / (1 - prevalence))
    return weights / weights.mean(), prevalence
