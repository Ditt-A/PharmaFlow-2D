from dataclasses import asdict
import numpy as np
import pytest
from pharmaflow.config import HopperConfig
from pharmaflow.m3_packing import physical_config,make_packing
from pharmaflow.m3_events import detect_events,label_frames,spans
from pharmaflow.m3_features import extract_features,FRAME_FIELDS,observations
from pharmaflow.m3_campaign import M3Monitor,simulate_task,run_task,tasks_from_plan
from pharmaflow.dem import DEMSystem,ParticleState


def toy(end=1.,start=.2):
    time=np.round(np.arange(0,end+.005,.01),8)
    graph=np.zeros((len(time),4,4),bool)
    for i,t in enumerate(time):
        if t>=start:
            for a,b in ((0,2),(0,1),(1,3)):graph[i,a,b]=graph[i,b,a]=True
    speed=np.where(time>=start,.001,.1)
    return dict(time_s=time,contact_graph=graph,interval_common_contacts=graph.copy(),near_max_speed_m_s=speed,
                interval_max_near_speed_m_s=speed.copy(),remaining_count=np.full(len(time),2),interval_min_remaining=np.full(len(time),2),
                discharged_count=np.zeros(len(time),int))


def label_at(rows,t,h=.05):
    return next(r for r in rows if abs(r['time_s']-t)<1e-9 and abs(r['horizon_s']-h)<1e-9)


def test_onset_confirmation_and_exclusive_prediction_origin():
    a=toy();events=detect_events(a,.05)
    assert len(events)==1
    assert events[0]['onset_time_s']==pytest.approx(.2)
    assert events[0]['confirmation_time_s']==pytest.approx(.6)
    labels=label_frames(a,events)
    assert label_at(labels,.15)['target']==1
    assert label_at(labels,.1)['target']==0
    assert label_at(labels,.2)['label_status']=='post_onset'
    assert all(r['target'] is None for r in labels if r['time_s']>=.2)


def test_resumed_flow_and_temporary_bridge_are_not_confirmed_events():
    a=toy();mask=a['time_s']>=.4
    a['contact_graph'][mask]=False;a['interval_common_contacts'][mask]=False
    a['discharged_count'][mask]=1
    assert detect_events(a,.05)==[]


def test_confirmed_finite_arch_can_later_resume_without_permanence_claim():
    a=toy(1.2);mask=a['time_s']>=.8
    a['contact_graph'][mask]=False;a['interval_common_contacts'][mask]=False
    a['discharged_count'][a['time_s']>=.9]=1
    events=detect_events(a,.05)
    assert len(events)==1 and events[0]['resumed_crossing_after_event']
    assert not events[0]['permanent_clogging']
    rows=label_frames(a,events)
    assert label_at(rows,.9)['label_status']=='post_onset'


def test_zero_crossings_without_bridge_or_stationarity_are_insufficient():
    a=toy();a['contact_graph'][:]=False
    assert not detect_events(a,.05)
    a=toy();a['interval_max_near_speed_m_s'][:]=1
    assert not detect_events(a,.05)


def test_truncated_future_is_censored_even_when_arch_looks_stationary():
    a=toy(.55);events=detect_events(a,.05)
    assert events==[]
    labels=label_frames(a,events)
    assert label_at(labels,.15)['label_status']=='right_censored'
    assert label_at(labels,.15)['target'] is None
    assert label_at(labels,.05)['target']==0


def test_empty_hopper_has_no_clog_labels():
    a=toy();mask=a['time_s']>=.2
    a['remaining_count'][mask]=0;a['interval_min_remaining'][mask]=0
    a['contact_graph'][mask]=False;a['interval_common_contacts'][mask]=False
    a['discharged_count'][mask]=2
    assert detect_events(a,.05)==[]
    labels=label_frames(a,[])
    assert label_at(labels,.25)['label_status']=='empty'
    assert label_at(labels,.15)['target']==0


def test_break_between_saved_frames_prevents_false_persistence():
    a=toy(.7);a['interval_common_contacts'][35]=False
    assert detect_events(a,.05)==[]


def test_duration_sensitivity_is_explicit():
    a=toy(.55)
    assert len(detect_events(a,.05,{'persistence_s':.2}))==1
    assert not detect_events(a,.05,{'persistence_s':.4})


@pytest.mark.parametrize('ratio',[2.,3.,4.,6.])
def test_outlet_changes_preserve_requested_wall_inclination(ratio):
    c=physical_config({'outlet_ratio':ratio,'wall_angle_deg':35,'n_particles':20},{},101)
    angle=np.degrees(np.arctan((c.width_m-c.outlet_width_m)/(2*c.funnel_height_m)))
    assert angle==pytest.approx(35)


def test_packing_families_are_reproducible_and_nonoverlapping():
    c=physical_config({'outlet_ratio':3,'wall_angle_deg':35,'n_particles':30},{},101)
    hashes=[]
    for family in ('staggered','hexagonal','random_sequential'):
        s,h=make_packing(c,family);again,h2=make_packing(c,family)
        np.testing.assert_array_equal(s.position,again.position);assert h==h2
        d=np.linalg.norm(s.position[:,None]-s.position[None,:],axis=2);np.fill_diagonal(d,np.inf)
        assert d.min()>2*c.particle_radius_m
        hashes.append(h)
    assert len(set(hashes))==3


def test_features_are_unchanged_when_future_observations_change():
    a=toy()
    for key in FRAME_FIELDS:
        if key not in a:a[key]=np.linspace(0,1,len(a['time_s']))
    before=extract_features(a,HopperConfig(),'staggered')
    b={k:v.copy() for k,v in a.items()}
    for key in FRAME_FIELDS:b[key][60:]+=1000
    b['discharged_count'][60:]+=10
    after=extract_features(b,HopperConfig(),'staggered')
    assert before[:60]==after[:60]


def test_m3_monitor_preserves_forces_and_trajectory():
    c=HopperConfig(gravity_m_s2=0)
    systems=[]
    for monitored in (False,True):
        state=ParticleState.create([[-.00195,0],[.00195,0]],c.particle_radius_m,c.particle_mass_kg,[[.03,.08],[-.03,-.02]])
        s=DEMSystem(c,state,walls=(),track_outlet=False)
        if monitored:s.monitor=M3Monitor(c)
        s.advance(200);systems.append(s)
    np.testing.assert_array_equal(systems[0].state.position,systems[1].state.position)
    np.testing.assert_array_equal(systems[0].state.omega,systems[1].state.omega)


def task():
    return dict(run_id='tiny',configuration_id='test',phase='pilot',physical={'outlet_ratio':6,'wall_angle_deg':35,'n_particles':2},
                numerical={},seed=1,packing_family='staggered',duration_s=.002,max_duration_s=.002,sample_interval_s=.001,
                protocol={'persistence_s':.4})


def test_checksum_resume_and_tampering_detection(tmp_path):
    a=run_task(task(),tmp_path);b=run_task(task(),tmp_path)
    assert a['status']=='ok';assert a['npz_sha256']==b['npz_sha256']
    path=tmp_path/'pilot/tiny/trajectory.npz';path.write_bytes(b'corrupt')
    with pytest.raises(RuntimeError,match='checksum'):run_task(task(),tmp_path)


def test_numerical_failures_remain_auditable(tmp_path):
    t=task();t['numerical']={'dt_s':.1}
    a=run_task(t,tmp_path)
    assert a['status']=='failed'
    assert (tmp_path/'failures/tiny.json').exists()
    assert 'unstable dt' in a['error']


def test_campaign_budgets_are_enforced():
    p=dict(phase='pilot',cases=[{'name':'a','physical':{'outlet_ratio':3,'wall_angle_deg':35}}],replicates=[{'packing_family':'hexagonal','seed':1}],
           numerical={},duration_s=2,sample_interval_s=.005,max_attempts=0,max_simulated_seconds=2)
    with pytest.raises(ValueError,match='budget'):tasks_from_plan(p)
    p['max_attempts']=1;p['max_simulated_seconds']=1
    with pytest.raises(ValueError,match='budget'):tasks_from_plan(p)


def test_absorbing_empty_fast_forward_matches_existing_dem():
    from pharmaflow.run import simulate
    t=task();t.update(duration_s=.3,max_duration_s=.3,sample_interval_s=.01)
    t['physical']['n_particles']=1
    a,m=simulate_task(t)
    c=physical_config(t['physical'],t['numerical'],t['seed'])
    baseline,_=simulate(c,.3,round(.01/c.dt_s))
    for key in ('position_m','velocity_m_s','angle_rad','omega_rad_s','active','discharged_count'):
        np.testing.assert_array_equal(a[key],baseline[key])
    assert m['absorbing_empty_fast_forward_steps']>0


def test_ambiguous_continuation_preserves_state_and_history():
    t=task();t.update(duration_s=.04,max_duration_s=.06,sample_interval_s=.01)
    t['physical']['n_particles']=10
    continued,meta=simulate_task(t)
    direct=task();direct.update(duration_s=.06,max_duration_s=.06,sample_interval_s=.01)
    direct['physical']['n_particles']=10
    reference,_=simulate_task(direct)
    assert meta['continued'] and meta['observation_duration_s']==pytest.approx(.06)
    assert np.max(continued['diag_tangent_spring_j'][:5])>0
    for key in ('position_m','velocity_m_s','omega_rad_s','contact_graph'):
        np.testing.assert_array_equal(continued[key],reference[key])


def test_configuration_splits_are_grouped_and_repeatable():
    from pharmaflow.m3_dataset import grouped_assignment
    rows=[dict(run_id=str(i),physical_group_id=str(i//3),confirmed_event_count=int(i%2==0)) for i in range(18)]
    a=grouped_assignment(rows,'physical_group_id');b=grouped_assignment(rows[::-1],'physical_group_id')
    assert a==b
    assert set(a.values())=={'train','validation','test'}


@pytest.mark.parametrize('duplicate',[False,True])
def test_build_and_audit_parquet_without_missing_or_leaky_features(tmp_path,duplicate):
    from pharmaflow.m3_dataset import build_dataset
    from pharmaflow.m3_audit import audit_dataset
    t=task();run_task(t,tmp_path/'raw')
    second=task();second.update(run_id='tiny2',seed=1 if duplicate else 2)
    run_task(second,tmp_path/'raw')
    manifest=build_dataset(tmp_path/'raw',tmp_path/'processed')
    assert manifest['successful_runs']==2
    if duplicate:
        with pytest.raises(RuntimeError,match='Duplicate trajectories'):audit_dataset(tmp_path/'raw',tmp_path/'processed')
        return
    report=audit_dataset(tmp_path/'raw',tmp_path/'processed')
    assert report['passed'] and report['feature_missing_values']==0
    assert (tmp_path/'processed/event_labels.parquet').exists()
