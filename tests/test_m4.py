"""Scientific failure modes: unsafe joins, group leakage and backdated/false event alerts."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
pytest.importorskip('sklearn')
from pharmaflow.m4_data import exact_join, feature_sets, run_weights, FORBIDDEN, ARCH_PROXIES, CUMULATIVE_PROXIES
from pharmaflow.m4_alerts import warning_times, score_runs, event_metrics, choose_threshold
from pharmaflow.m4_models import fit_baseline, predict
from pharmaflow.m4_training import grouped_folds, train
from pharmaflow.m4_metrics import frame_metrics, cluster_bootstrap
from pharmaflow.m4_audit import verify_prediction_replay

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'configs/m4/baselines.json').read_text())


def toy_tables():
    f = pd.DataFrame(dict(run_id=['a'] * 4, frame_index=range(4), time_s=[.05, .055, .06, .065],
                          configuration_id=['c'] * 4, physical_group_id=['p'] * 4, near_count=[3] * 4))
    labels = pd.concat([f.drop(columns='near_count').assign(horizon_s=h, target=pd.array([0, 1, None, None], dtype='Int8'),
                                                          label_status=['eligible', 'eligible', 'post_onset', 'right_censored']) for h in (.05, .1)])
    return f, labels


def test_exact_join_eligible_only_and_no_cross_horizon_duplication():
    f, labels = toy_tables()
    result = exact_join(f, labels, .1)
    assert len(result) == 2 and list(result.target) == [0, 1]
    assert set(result.horizon_s) == {.1}


@pytest.mark.parametrize('fault', ['duplicate_feature', 'duplicate_label', 'timestamp', 'identity', 'missing_binary'])
def test_join_rejects_ambiguous_or_inconsistent_rows(fault):
    f, labels = toy_tables()
    if fault == 'duplicate_feature':
        f = pd.concat([f, f.iloc[:1]])
    if fault == 'duplicate_label':
        labels = pd.concat([labels, labels.iloc[:1]])
    if fault == 'timestamp':
        f.loc[0, 'time_s'] += 1e-10
    if fault == 'identity':
        f.loc[0, 'configuration_id'] = 'wrong'
    if fault == 'missing_binary':
        labels.loc[labels.frame_index == 0, 'target'] = None
    with pytest.raises(ValueError):
        exact_join(f, labels, .05)


def test_official_whitelist_and_proxy_ablations():
    dictionary = json.loads((Path(__file__).resolve().parents[1] / 'docs/results/m3/feature_dictionary.json').read_text())
    sets = feature_sets(dictionary)
    assert len(sets['D_full']) == 41
    assert not set.union(*(set(v) for v in sets.values())) & FORBIDDEN
    assert not set(sets['E_without_arch']) & set(ARCH_PROXIES)
    assert not set(sets['F_without_time_discharge']) & set(CUMULATIVE_PROXIES)
    assert 'time_s' in sets['D_full'] and 'spanning_arch_now' in sets['B_current']
    assert all(dictionary[c]['availability'].startswith('static') for c in sets['A_static'])


def test_correlated_dense_run_does_not_change_training_prevalence():
    df = pd.DataFrame(dict(run_id=['a', 'a', 'b'], target=[0, 1, 0]))
    weights, prevalence = run_weights(df)
    assert prevalence == .25
    dense = pd.concat([df, df.loc[df.run_id == 'a']] * 2, ignore_index=True)
    assert run_weights(dense)[1] == prevalence
    balanced, _ = run_weights(df, True)
    assert np.isclose(balanced[df.target == 1].sum(), balanced[df.target == 0].sum())


def training_rows():
    return pd.DataFrame([dict(run_id=f'r{i}', physical_group_id=f'g{i // 2}', target=j % 2,
                              outlet_ratio=2 + i / 10, packing_family='a' if i % 2 else 'b')
                         for i in range(12) for j in range(4)])


def test_group_folds_never_share_physical_configurations():
    df = training_rows()
    folds = grouped_folds(df, 'physical_group_id', CONFIG)
    assert len(folds) == 3
    for fit, held in folds:
        assert not set(df.iloc[fit].physical_group_id) & set(df.iloc[held].physical_group_id)


@pytest.mark.parametrize('name', ['logistic', 'forest', 'xgboost'])
def test_preprocessing_and_models_fit_only_training_and_ignore_unknown_packing(name):
    if name == 'xgboost':
        pytest.importorskip('xgboost')
    df = training_rows()
    artifact = fit_baseline(name, df, ['outlet_ratio', 'packing_family'], CONFIG)
    scaler = artifact['pipeline']['preprocess'].named_transformers_['numeric']
    mean = scaler.mean_.copy()
    held = df.iloc[:3].copy()
    held['outlet_ratio'], held['packing_family'] = 1000, 'unseen'
    assert np.isfinite(predict(artifact, held)).all()
    np.testing.assert_array_equal(mean, scaler.mean_)
    np.testing.assert_allclose(mean, [df.outlet_ratio.mean()])
    assert 'unseen' not in artifact['pipeline']['preprocess'].named_transformers_['packing'].categories_[0]


def test_alert_is_emitted_on_confirmation_frame_and_latched():
    times = np.arange(8) * .005
    assert warning_times(times, [1] * 8, .5) == [.005]
    alerts = warning_times(times, [1, 1, 0, 1, 1, 0, 1, 1], .5, cooldown_s=.01)
    np.testing.assert_allclose(alerts, [.005, .02, .035])


def test_alert_gaps_reset_consecutive_frame_counter():
    assert warning_times([.01, .1], [.9, .9], .5) == []
    with pytest.raises(ValueError):
        warning_times([.1, .1], [.9, .9], .5)


def metadata(event=True):
    return pd.DataFrame([dict(run_id='a', physical_group_id='p', event_onsets_json=json.dumps([.1] if event else []),
                             event_confirmations_json=json.dumps([.5] if event else []), outlet_ratio=2.5,
                             packing_family='random_sequential', friction=.4, wall_friction=.4)])


@pytest.mark.parametrize('last,any_hit,useful', [(.075, True, True), (.085, True, False), (.1, False, False), (.105, False, False)])
def test_event_success_requires_strict_preonset_and_useful_lead(last, any_hit, useful):
    s = pd.DataFrame(dict(run_id=['a', 'a'], time_s=[last - .005, last], probability=[1., 1.]))
    r = score_runs(s, metadata(), .05, .5, CONFIG['alerts'])
    assert bool(r.hit_any.iloc[0]) == any_hit and bool(r.hit_useful.iloc[0]) == useful
    if any_hit:
        assert np.isclose(r.first_valid_warning_s.iloc[0], last)


def test_too_early_and_empty_or_non_event_alerts_are_false():
    s = pd.DataFrame(dict(run_id=['a', 'a'], time_s=[.01, .015], probability=[1., 1.]))
    for meta in (metadata(True), metadata(False)):
        m = event_metrics(score_runs(s, meta, .05, .5, CONFIG['alerts']))
        assert m['false_alerts'] == 1 and m['alerted_events'] == 0
    assert m['event_recall'] is None  # completed discharge has no clog event


def test_constant_baseline_uses_train_run_weighted_prevalence():
    df = training_rows()
    constant = fit_baseline('constant', df, [], CONFIG)
    np.testing.assert_array_equal(predict(constant, df), np.full(len(df), .5))
    scores = df.assign(probability=.5)
    m = frame_metrics(scores, .6)
    assert m['average_precision'] == .5 and m['roc_auc'] == .5 and m['brier'] == .25
    assert frame_metrics(scores.loc[scores.target == 0], .6)['roc_auc'] is None


def test_training_freeze_is_not_silently_overwritten(tmp_path):
    (tmp_path / 'frozen_selection.json').write_text('{}')
    with pytest.raises(FileExistsError):
        train(output=tmp_path, models=tmp_path / 'models')


def test_future_outcomes_and_identifiers_cannot_affect_predictions():
    df = training_rows()
    artifact = fit_baseline('logistic', df, ['outlet_ratio', 'packing_family'], CONFIG)
    contaminated = df.assign(run_id='other', target=1, event_onset_time_s=-999,
                             confirmation_time_s=1000, label_status='post_onset', seed=77)
    np.testing.assert_array_equal(predict(artifact, df), predict(artifact, contaminated))


def test_threshold_selection_uses_episodes_not_positive_frame_counts():
    # A permanently high score fires too early, then stays latched: no valid warning.
    s = pd.DataFrame(dict(run_id=['a'] * 19, time_s=np.arange(19) * .005,
                          probability=np.ones(19), target=[0] * 9 + [1] * 10))
    best, _ = choose_threshold(s, metadata(), .05, CONFIG)
    assert best['threshold'] == 1.01 and best['alerted_events'] == 0


def test_cluster_resampling_reports_degenerate_event_replicates():
    df = pd.DataFrame(dict(run_id=['a', 'a', 'b', 'b'], physical_group_id=['p', 'p', 'q', 'q'],
                           target=[0, 1, 0, 0], probability=[.1, .9, .2, .1]))
    rows = pd.DataFrame(dict(run_id=['a', 'b'], physical_group_id=['p', 'q'], event=[True, False],
                             hit_any=[True, False], hit_useful=[True, False], false_alerts=[0, 0],
                             exposure_s=[.01, .01], lead_s=[.03, None]))
    result = cluster_bootstrap(df, rows, .5, 'physical_group_id', repeats=100, seed=5)
    assert result['independent_clusters'] == 2
    assert result['intervals']['event_recall']['defined_replicates'] < 100
    assert result['intervals']['event_recall']['lower'] == 1  # conditional degeneracy is explicitly exposed


def test_prediction_replay_roundoff_is_allowed_but_alert_changes_are_not():
    assert verify_prediction_replay([.4], [.4 + 2e-16], .5) < 1e-12
    with pytest.raises(AssertionError):
        verify_prediction_replay([.4], [.41], .5)
    with pytest.raises(AssertionError):
        verify_prediction_replay([.5 - 1e-15], [.5 + 1e-15], .5)
