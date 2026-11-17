"""M4B budget and outcome-blind holdout protections; no campaign solver calls."""
import json
from pathlib import Path
import pytest
pytest.importorskip('sklearn')
from pharmaflow.m4b_campaign import tasks, reserve, locked_gate, group_for_task
import numpy as np
import pandas as pd
from pharmaflow.m4b_online import online_warnings, summarize_runs, summary
from pharmaflow.m4b_data import historical_training_ids, assign_development
from pharmaflow.m4b_data import load_development
from pharmaflow.m4b_evaluation import readiness, evaluate_locked
from pharmaflow.m4_alerts import warning_times
from pharmaflow.m3_packing import physical_config, make_packing

DESIGN = json.loads((Path(__file__).resolve().parents[1] / 'configs/m4b/design.json').read_text())
CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'configs/m4b/baselines.json').read_text())


def test_m4b_design_budget_and_independent_seeds():
    p, t = tasks(DESIGN['pilot_cases'], 'pilot', DESIGN), tasks(DESIGN['locked_cases'], 'locked', DESIGN)
    assert len(p) == len(t) == 12
    assert len({r['seed'] for r in p+t}) == 24
    assert len({group_for_task(r) for r in t}) == 4
    assert not {group_for_task(r) for r in p} & {group_for_task(r) for r in t}
    assert all(r['numerical']['max_overlap_ratio'] == .15 for r in p+t)


def test_failed_and_reserved_attempts_still_consume_budget():
    ledger = {}
    base = tasks(DESIGN['pilot_cases'], 'pilot', DESIGN)
    assert len(reserve(ledger, base, DESIGN['allocation'])) == 12
    ledger['attempts'][base[0]['run_id']]['state'] = 'failed'
    assert reserve(ledger, base, DESIGN['allocation']) == []
    extra = dict(base[0], run_id='another_attempt')
    with pytest.raises(ValueError):
        reserve(ledger, [extra], DESIGN['allocation'])
    with pytest.raises(ValueError):
        reserve(ledger, [dict(base[0], seed=999)], DESIGN['allocation'])


def test_global_budget_cannot_be_bypassed_by_new_phase():
    ledger = {'attempts': {str(i): {'task': {'phase': 'adaptive'}} for i in range(48)}}
    with pytest.raises(ValueError):
        reserve(ledger, [{'run_id': 'extra', 'phase': 'locked'}], {'adaptive': 48, 'locked': 12})


def test_locked_generation_rejects_missing_model_freeze(tmp_path):
    with pytest.raises(ValueError, match='before model/policy freeze'):
        locked_gate(tmp_path, tmp_path/'missing.json')


@pytest.mark.parametrize('policy', CONFIG['policies'])
def test_chronological_warnings_are_prefix_invariant(policy):
    time = np.arange(101)*.005
    score = np.clip(np.sin(time*70)*.6+.5, 0, 1)
    remaining = np.full(101, 30)
    whole = online_warnings(time, score, remaining, .6, policy)
    cut = 57
    prefix = online_warnings(time[:cut], score[:cut], remaining[:cut], .6, policy)
    assert prefix == [t for t in whole if t <= time[cut-1]]
    # Changing any unobserved future cannot change earlier episode starts.
    score[cut:], remaining[cut:] = 1, 0
    assert prefix == [t for t in online_warnings(time, score, remaining, .6, policy) if t <= time[cut-1]]


def test_chronological_replay_never_warns_before_gate_or_after_observed_empty():
    time = np.arange(50)*.005
    remaining = np.where(time < .15, 3, 0)
    alerts = online_warnings(time, np.ones(50), remaining, .5, CONFIG['policies'][2])
    assert all(.05 <= t < .15 for t in alerts)
    assert alerts[0] == pytest.approx(.055)


def test_bounded_refresh_and_hysteresis_do_not_backdate():
    t = np.arange(101)*.005
    alerts = online_warnings(t, np.ones(101), np.full(101, 3), .5, CONFIG['policies'][2])
    np.testing.assert_allclose(alerts, [.055, .105, .155])
    legacy = online_warnings(t, np.ones(101), np.full(101, 3), .5, CONFIG['policies'][0])
    assert legacy == [.055]


def replay_toy(status='post_onset', event=True):
    t = np.arange(101)*.005
    f = pd.DataFrame(dict(run_id='a', frame_index=np.arange(101), time_s=t, remaining_count=3))
    labels = f[['run_id', 'frame_index', 'time_s']].assign(horizon_s=.1, label_status='eligible')
    labels.loc[t >= .2, 'label_status'] = status
    meta = pd.DataFrame([dict(run_id='a', physical_group_id='g', event_onsets_json='[0.2]' if event else '[]',
                              censored_run=not event, gate_open_s=.05, sample_interval_s=.005, outlet_ratio=2.5,
                              packing_family='hexagonal', friction=.4, wall_friction=.4, wall_angle_deg=35)])
    score = np.where(t >= .3, 1., 0.)
    pred = f[['run_id', 'frame_index', 'time_s']].assign(probability=score)
    return f, labels, meta, pred


def test_no_oracle_post_onset_gate_and_late_alerts_are_accounted():
    f, lab, meta, pred = replay_toy()
    r = summarize_runs(pred, f, lab, meta, .1, .5, CONFIG['policies'][0])
    assert r.alert_count.iloc[0] == 1 and r.post_onset_alerts.iloc[0] == 1
    assert summary(r)['useful_hits'] == 0 and summary(r)['false_forecasts'] == 1
    # The retrospective metric excludes those frames; the online controller does not.
    retrospective = summarize_runs(pred, f, lab, meta, .1, .5, CONFIG['policies'][0], 'eligible')
    assert retrospective.alert_count.iloc[0] == 0


def test_censored_future_is_unscorable_not_a_false_negative_or_false_alarm():
    f, lab, meta, pred = replay_toy('right_censored', False)
    r = summarize_runs(pred, f, lab, meta, .1, .5, CONFIG['policies'][0])
    assert r.unscorable_alerts.iloc[0] == 1 and r.false_forecasts.iloc[0] == 0
    assert summary(r)['useful_event_recall'] is None


def test_original_m3_validation_and_test_are_never_promoted():
    s = {'benchmarks': {'a': {'run_assignments': {'r1':'train','r2':'test','r3':'train'}},
                        'b': {'run_assignments': {'r1':'train','r2':'train','r3':'validation'}}}}
    assert historical_training_ids(s) == ['r1']


def test_physical_group_split_rejects_seed_only_separation():
    meta = pd.DataFrame(dict(run_id=['a','b'], case_name=['validation','train'], physical_group_id=['g','g']))
    with pytest.raises(ValueError):
        assign_development(meta, ['validation'])


def test_frozen_locked_groups_are_new_and_excluded_from_adaptive_cases():
    root = Path(__file__).resolve().parents[1]
    old = json.loads((root/'docs/results/m3/split_manifest.json').read_text())
    old_groups = set(old['benchmarks']['configuration_holdout']['assignments'])
    locked = {group_for_task(t) for t in tasks(DESIGN['locked_cases'], 'locked', DESIGN)}
    adaptive = json.loads((root/'configs/m4b/adaptive.json').read_text())
    assert not locked & old_groups
    assert not locked & {group_for_task(t) for t in tasks(adaptive['cases'], 'adaptive', DESIGN)}


@pytest.mark.parametrize('family', DESIGN['packing_families'])
def test_initial_packing_reproducibility_without_extra_solver_attempts(family):
    task = tasks(DESIGN['pilot_cases'], 'pilot', DESIGN)[0]
    c = physical_config(task['physical'], task['numerical'], task['seed'])
    a, sha_a = make_packing(c, family)
    b, sha_b = make_packing(c, family)
    assert sha_a == sha_b
    np.testing.assert_array_equal(a.position, b.position)


def test_legacy_policy_matches_m4a_when_given_same_observable_operation():
    time = np.arange(121)*.005
    scores = np.clip(np.sin(time*90)*.6+.5, 0, 1)
    remaining = np.ones(len(time))*3
    expected = warning_times(time[time>=.05], scores[time>=.05], .5)
    assert online_warnings(time,scores,remaining,.5,CONFIG['policies'][0]) == expected


def test_training_loader_rejects_locked_release(tmp_path):
    (tmp_path/'dataset_manifest.json').write_text(json.dumps({'scope':'locked','files':{}}))
    with pytest.raises(ValueError,match='rejects locked'):
        load_development(tmp_path)


def test_completed_locked_evaluation_cannot_be_overwritten(tmp_path):
    (tmp_path/'locked_evaluation_receipt.json').write_text('{}')
    with pytest.raises(FileExistsError):
        evaluate_locked(output=tmp_path)


@pytest.mark.parametrize('events,groups,lower,expected', [
    (5,3,.1,'M4B_INSUFFICIENT_INDEPENDENT_EVENT_EVIDENCE'),
    (6,2,.1,'M4B_INSUFFICIENT_INDEPENDENT_EVENT_EVIDENCE'),
    (6,3,-.1,'M4B_RULE_BASELINE_REMAINS_COMPETITIVE'),
    (6,3,.1,'M4B_EVIDENCE_SUPPORTS_FURTHER_TEMPORAL_MODELING')])
def test_prespecified_readiness_never_turns_sparse_events_into_success(events,groups,lower,expected):
    ml={'events':events,'useful_event_recall':.9,'false_per_operating_s':.1}
    rule={'events':events,'useful_event_recall':.6,'false_per_operating_s':.1}
    interval={'intervals':{'paired_useful_recall_gain':{'lower':lower}}}
    assert readiness(ml,rule,groups,interval,CONFIG) == expected


def test_completed_campaign_resume_verifies_cache_without_dispatch(tmp_path,monkeypatch):
    pytest.importorskip('fcntl')
    import pharmaflow.m4b_campaign as campaign
    from pharmaflow.m4_data import digest
    path=tmp_path/'cached.npz';path.write_bytes(b'checksum fixture, not a simulation')
    task={'run_id':'r','phase':'pilot'}
    previous={'tasks':[task],'records':[{'status':'ok','trajectory_path':str(path),'npz_sha256':digest(path)}],
              'state':'complete','phase_wall_s':42.}
    manifest=tmp_path/'manifests/pilot_campaign.json';manifest.parent.mkdir()
    manifest.write_text(json.dumps(previous))
    monkeypatch.setattr(campaign,'freeze_design',lambda *a,**kw:{'design':DESIGN,'pilot_tasks':[task]})
    assert campaign.run_phase('pilot',tmp_path) == previous
    assert not (tmp_path/'manifests/attempts.json').exists()
    path.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='Cached trajectory changed'):
        campaign.run_phase('pilot',tmp_path)


def test_serial_forest_inference_preserves_artifact_and_numerical_predictions():
    from pharmaflow.m4_models import fit_baseline,predict as old_predict
    from pharmaflow.m4b_models import predict
    f=pd.DataFrame(dict(run_id=['a']*4+['b']*4,target=[0,1,0,1]*2,outlet_ratio=[2,3,2.5,3.5]*2))
    artifact=fit_baseline('forest',f,['outlet_ratio'],CONFIG)
    params=artifact['pipeline']['model'].get_params().copy()
    first=predict(artifact,f)
    np.testing.assert_array_equal(first,predict(artifact,f))
    np.testing.assert_allclose(first,old_predict(artifact,f),rtol=1e-12,atol=1e-12)
    assert artifact['pipeline']['model'].get_params()==params
