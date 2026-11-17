"""M5 causal monitoring, immutable replay, bounded jobs and UI interactions."""
from dataclasses import asdict
from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
import pytest
from pharmaflow.operational_events import OperationalDefinition,OperationalMonitor,observe_history,annotate_outcomes
from pharmaflow.monitoring import AlertMonitor,physics_score,frozen_specs,monitor_features
from pharmaflow.m4b_online import online_warnings
from pharmaflow.dashboard_data import load_bundle,ReplayBundle
from pharmaflow.demo_jobs import limits,validate_request,reserve_demo,set_status,jobs,integrate_demo
from pharmaflow.config import HopperConfig
from pharmaflow.m3_features import FRAME_FIELDS,extract_features
from pharmaflow.m4_data import digest
from pharmaflow.run import save_run

ROOT=Path(__file__).resolve().parents[1]
REQUEST=dict(outlet_ratio=5.,friction=.3,wall_friction=.3,wall_angle_deg=35.,n_particles=30,
             packing_family='staggered',seed=57001,duration_s=.12)


def test_operational_prefix_invariance_and_no_oracle_fields():
    times=np.arange(81)*.005;counts=np.zeros(81,dtype=int)
    for i in (12,16,20,24,28,60):counts[i:]+=2
    rows,pauses=observe_history(times,counts,30-counts)
    for stop in (10,30,45,61):
        short,observed_pauses=observe_history(times[:stop],counts[:stop],(30-counts)[:stop])
        assert short==rows[:stop]
        assert observed_pauses==[p for p in pauses if p['resume_observed_s']<=times[stop-1]]
    assert not any('onset' in k or 'confirmation' in k or 'target' in k for k in rows[0])


def test_one_crossing_does_not_establish_flow():
    config=json.loads((ROOT/'configs/m5/operational_events.json').read_text())
    assert asdict(OperationalDefinition())=={k:config[k] for k in asdict(OperationalDefinition())}
    rows,_=observe_history([0,.05,.08,.15,.3],[0,0,1,1,1],[30,30,29,29,29])
    assert not any(r['flow_established_now'] for r in rows)
    a=annotate_outcomes(rows,[dict(onset_time_s=.15,confirmation_time_s=.3)])
    assert a['post_discharge_arch']==1 and a['established_flow_arch']==0


def test_startup_post_discharge_and_established_are_distinct():
    t=np.arange(101)*.005;c=np.zeros(101,dtype=int)
    for i in (14,18,22,26,30,34):c[i:]+=1
    rows,_=observe_history(t,c,30-c)
    a=annotate_outcomes(rows,[dict(onset_time_s=.06,confirmation_time_s=.46)])
    assert a['startup_blockage']==1 and a['post_discharge_arch']==0
    a=annotate_outcomes(rows,[dict(onset_time_s=.20,confirmation_time_s=.5)])
    assert a['post_discharge_arch']==a['established_flow_arch']==1
    assert a['arches'][0]['prior_observed_crossings']==6


def test_pause_only_becomes_temporary_after_observed_resume():
    m=OperationalMonitor();out=[m.observe(t,c,30-c) for t,c in [(0,0),(.06,1),(.12,1),(.15,1)]]
    assert out[-1]['pause_observed'] and m.resumptions==[]
    assert annotate_outcomes(out,[])['unresolved_or_censored']
    assert m.observe(.16,2,28)['resumed_now']
    assert len(m.resumptions)==1 and m.resumptions[0]['resume_observed_s']==.16
    assert annotate_outcomes(out,[])['post_discharge_arch']==0


def test_empty_is_separate_from_clog_and_pause():
    rows,p=observe_history([0,.06,.12,.3],[0,1,2,2],[2,1,0,0])
    a=annotate_outcomes(rows,[])
    assert a['completed_discharge'] and not a['unresolved_or_censored'] and not a['post_discharge_arch']
    assert rows[-1]['observed_state']=='no_particle_remaining' and not rows[-1]['pause_observed']


@pytest.mark.parametrize('bad',[(.1,1,29),(.2,0,30),(.2,1.5,28.5),(.2,np.nan,20)])
def test_invalid_observed_history_rejected(bad):
    m=OperationalMonitor();m.observe(.1,1,29)
    with pytest.raises(ValueError):m.observe(*bad)


@pytest.mark.parametrize('policy',json.loads((ROOT/'configs/m4b/baselines.json').read_text())['policies'])
def test_incremental_warning_matches_frozen_replay(policy):
    rng=np.random.default_rng(14);t=np.r_[np.arange(100)*.005,np.arange(100,200)*.005+.03]
    score=rng.choice([.2,.49,.64,.9],len(t));score[25:55]=.9;remaining=np.full(len(t),30);remaining[-9:]=0
    expected=online_warnings(t,score,remaining,.5,policy)
    monitor=AlertMonitor(.5,policy)
    states=[monitor.observe(*values) for values in zip(t,score,remaining)]
    assert [x['time_s'] for x in monitor.log]==expected
    short=AlertMonitor(.5,policy)
    assert [short.observe(*v) for v in zip(t[:81],score[:81],remaining[:81])]==states[:81]
    assert not states[-1]['alert_active']


def test_monitoring_ignores_future_outcome_metadata():
    specs=frozen_specs(ROOT);f=pd.DataFrame([dict(time_s=i*.005,remaining_count=30,near_count=5,
        near_stationary_fraction=1.,spanning_arch_now=1,near_speed_mean_m_s=0.) for i in range(100)])
    rows,logs=monitor_features(f,np.zeros(100),specs,np.ones(100))
    polluted=f.assign(event_onset_time_s=.01,confirmation_time_s=.42,target=1,label_status='post_onset',final_outcome='clog')
    assert monitor_features(polluted,np.zeros(100),specs,np.ones(100))==(rows,logs)
    assert monitor_features(f.iloc[:50],np.zeros(50),specs,np.ones(50))[0]==rows[:50]
    assert physics_score(f.iloc[0])==1.
    assert specs['rule']['threshold']==.85 and specs['rule']['policy']['cooldown_s']==.05


@pytest.mark.parametrize('change',[dict(outlet_ratio=0),dict(wall_angle_deg=80),dict(friction=-1),dict(n_particles=29),
    dict(n_particles=31.5),dict(seed=-1),dict(seed=True),dict(duration_s=.123),dict(duration_s=2),dict(wall_friction=np.inf),
    dict(packing_family='invented'),dict(n_particles=100,duration_s=.8)])
def test_demo_rejects_invalid_or_excessive_requests(change):
    with pytest.raises(ValueError):validate_request(dict(REQUEST,**change),limits(ROOT))


def test_demo_stiffness_guard_and_geometry():
    cap=limits(ROOT)
    from pharmaflow.m3_packing import physical_config
    valid=validate_request(REQUEST,cap)
    angles=[]
    for ratio in (2.,6.):
        p={k:valid[k] for k in ('friction','wall_friction','wall_angle_deg','n_particles')};p['outlet_ratio']=ratio
        c=physical_config(p,cap['numerical'],valid['seed'])
        angles.append(np.degrees(np.arctan((c.width_m-c.outlet_width_m)/(2*c.funnel_height_m))))
        assert c.max_overlap_ratio==.15 and c.dt_s==5e-6
    np.testing.assert_allclose(angles,[35,35])
    cap['numerical']['dt_s']=.1
    with pytest.raises(ValueError):validate_request(REQUEST,cap)


def test_failed_demos_are_charged_and_concurrency_reserved(tmp_path):
    (tmp_path/'configs/m5').mkdir(parents=True);shutil.copyfile(ROOT/'configs/m5/demo_limits.json',tmp_path/'configs/m5/demo_limits.json')
    first=reserve_demo(REQUEST,tmp_path)
    with pytest.raises(ValueError,match='already running'):reserve_demo(REQUEST,tmp_path)
    set_status(tmp_path,first,'failed','synthetic failure')
    for _ in range(5):
        run=reserve_demo(REQUEST,tmp_path);set_status(tmp_path,run,'failed','synthetic failure')
    with pytest.raises(ValueError,match='exhausted'):reserve_demo(REQUEST,tmp_path)
    assert len(jobs(tmp_path))==6 and all(r['status']=='failed' for r in jobs(tmp_path))
    assert not (tmp_path/'data').exists()


def test_duplicate_integrator_does_not_execute_solver(tmp_path):
    (tmp_path/'configs/m5').mkdir(parents=True);shutil.copyfile(ROOT/'configs/m5/demo_limits.json',tmp_path/'configs/m5/demo_limits.json')
    run=reserve_demo(REQUEST,tmp_path);set_status(tmp_path,run,'integrating')
    with pytest.raises(ValueError,match='unique claimed'):integrate_demo(tmp_path,run)


@pytest.fixture
def stored_replay(tmp_path):
    c=HopperConfig(n_particles=2);t=np.arange(5)*.005
    a={k:np.zeros(5) for k in FRAME_FIELDS};a.update(time_s=t,discharged_count=np.zeros(5,dtype=int),remaining_count=np.full(5,2),
        position_m=np.tile([[-.003,.02],[.003,.02]],(5,1,1)),velocity_m_s=np.zeros((5,2,2)),
        radius_m=np.full(2,c.particle_radius_m),active=np.ones((5,2),dtype=bool),contact_graph=np.zeros((5,4,4),dtype=bool))
    a['active_count'][:]=2;a['near_count'][:]=2
    meta=dict(run_id='toy',config=asdict(c),packing_family='staggered',sample_interval_s=.005,events=[])
    save_run(tmp_path/'trajectory.npz',a,meta)
    record=dict(meta,trajectory_path='trajectory.npz',npz_sha256=digest(tmp_path/'trajectory.npz'))
    (tmp_path/'docs/results/m4b').mkdir(parents=True)
    shutil.copyfile(ROOT/'docs/results/m4b/model_and_policy_freeze.json',tmp_path/'docs/results/m4b/model_and_policy_freeze.json')
    return tmp_path,record,a


def test_replay_exact_stored_positions_and_timestamps(stored_replay):
    root,record,arrays=stored_replay;b=load_bundle(record,root)
    f=b.frame(3);assert f['time_s']==.015
    np.testing.assert_array_equal(f['positions'],arrays['position_m'][3])
    with pytest.raises(ValueError):f['positions'][0,0]=99
    with pytest.raises(ValueError):b.frame(5)
    for stop in (2,4):
        prefix={k:(v[:stop] if k not in ('radius_m',) else v) for k,v in arrays.items()}
        assert extract_features(prefix,b.config,'staggered')==b.features.iloc[:stop].to_dict('records')


def test_replay_checksum_and_metadata_mismatch_rejected(stored_replay):
    root,r,a=stored_replay
    with pytest.raises(ValueError,match='checksum'):load_bundle(dict(r,npz_sha256='wrong'),root)
    with pytest.raises(ValueError,match='metadata'):load_bundle(dict(r,run_id='wrong'),root)


def test_offline_view_contains_real_states_without_event_truth(stored_replay):
    from pharmaflow.notebook_viewer import export_html
    root,r,a=stored_replay;b=load_bundle(r,root);path=export_html(b,root/'view.html')
    text=path.read_text();assert 'const D=' in text and '[-0.003,0.02]' in text
    assert 'onset_time_s' not in text and 'confirmation_time_s' not in text


def test_dashboard_page_and_sliders_do_not_invoke_solver(monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    from pharmaflow.dem import DEMSystem
    def prohibited(*args,**kwargs):raise AssertionError('A view interaction must not launch or run a simulation')
    monkeypatch.setattr(DEMSystem,'step',prohibited)
    import pharmaflow.demo_jobs as demo
    monkeypatch.setattr(demo,'launch_demo',prohibited)
    at=AppTest.from_file(str(ROOT/'app/streamlit_app.py'),default_timeout=60).run()
    assert not at.exception
    if any(b.label=='Play' for b in at.button):
        next(b for b in at.button if b.label=='Play').click().run();assert not at.exception
        initial=at.session_state['frame'];at.run();assert not at.exception
        assert at.session_state['frame']>initial
        next(b for b in at.button if b.label=='Pause').click().run()
        paused=at.session_state['frame'];at.run();assert at.session_state['frame']==paused
        next(b for b in at.button if b.label=='Next').click().run()
        assert at.session_state['frame']==paused+1 and not at.exception
    at.sidebar.radio[0].set_value('Run a DEM demo').run();assert not at.exception
    at.slider[0].set_value(4.).run();assert not at.exception
    at.sidebar.radio[0].set_value('Research analysis').run();assert not at.exception
    at.sidebar.radio[0].set_value('Calibration gaps').run();assert not at.exception
