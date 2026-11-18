"""Fixed support mechanics, polydisperse guard, geometry, history and pilot budget."""
from dataclasses import FrozenInstanceError,replace,asdict
from copy import deepcopy
import json
import os
from pathlib import Path
import numpy as np
import pytest
from pharmaflow.config import HopperConfig
from pharmaflow.dem import DEMSystem,ParticleState,initial_state
from pharmaflow.fixed_grain import FixedGrain,FixedGrainSystem,flat_floor_walls,obstacle_at_outlet,mixture_packing,elastic_collision_metrics
from pharmaflow.m7a_simulation import contact_graph,FixedGrainMonitor,simulate_fixed_grain
from pharmaflow.m7a_campaign import tasks,connect_ledger,reserve

ROOT=Path(__file__).resolve().parents[1]


def isolated(v=(0.,0.),spin=0.,**changes):
    c=replace(HopperConfig(),n_particles=1,gravity_m_s2=0,gate_open_time_s=0,
        normal_damping_kg_s=0,tangential_damping_kg_s=0,**changes)
    s=ParticleState.create([[.0039,0]],.002,c.particle_mass_kg,[v],[spin])
    return FixedGrainSystem(c,s,FixedGrain((0,0),.002,.4),walls=(),track_outlet=False)


def test_fixed_obstacle_force_and_external_reaction():
    s=isolated();f,t=s.forces()
    np.testing.assert_allclose(f,[[.1,0]],atol=2e-15)
    np.testing.assert_allclose(f.sum(axis=0)+s.obstacle_reaction_force_n,0,atol=1e-15)
    assert t[0]==0
    with pytest.raises(FrozenInstanceError):s.obstacle.radius_m=.003
    center=s.obstacle.center_m;s.advance(500)
    assert s.obstacle.center_m==center and s.state.velocity[0,0]>0


def test_friction_history_coulomb_limit_torque_and_reset():
    s=isolated(v=(0,100));f,t=s.forces()
    assert f[0,1]==pytest.approx(-.4*f[0,0]) and t[0]>0
    assert t[0]==pytest.approx(-(.002-.0001/2)*f[0,1])
    s.state.velocity[:]=0
    remembered=s.forces()[0];assert remembered[0,1]<0
    s.state.position[0,0]=.01;s.forces();assert s.obstacle_history=={}
    s.state.position[0,0]=.0039
    assert s.forces()[0][0,1]==0


def test_spin_contact_opposes_rotation():
    s=isolated(spin=20);_,t=s.forces()
    assert t[0]<0 and t[0]*s.state.omega[0]<0


def test_fixed_contact_approach_damping_is_nonadhesive():
    a=isolated(v=(-.1,0));a.config=replace(a.config,normal_damping_kg_s=.15)
    b=isolated(v=(.1,0));b.config=replace(b.config,normal_damping_kg_s=.15)
    assert a.forces()[0][0,0]>b.forces()[0][0,0]>0


@pytest.mark.parametrize('position',[(0,0),(.003,0)])
def test_coincidence_and_penetration_guard(position):
    s=isolated();s.state.position[0]=position
    with pytest.raises(RuntimeError):s.forces()


def test_post_step_and_displacement_guards_are_not_relaxed():
    s=isolated(v=(-1,0));s.state.position[0]=(.003701,0)
    with pytest.raises(RuntimeError,match='overlap'):s.step()
    s=isolated(v=(-1000,0));s.state.position[0]=(.0041,0)
    with pytest.raises(RuntimeError,match='0.25'):s.step()


def test_elastic_impact_energy_convergence_and_support_impulse():
    rows=elastic_collision_metrics()
    errors=[r['maximum_relative_energy_error'] for r in rows]
    assert errors[1]<.52*errors[0] and errors[2]<.52*errors[1]
    assert all(abs(r['final_velocity_x_m_s']-.1)<.001 for r in rows)
    assert max(r['mobile_plus_obstacle_impulse_residual_kg_m_s'] for r in rows)<1e-15


def test_polydisperse_actual_minimum_mass_timestep_guard():
    c=HopperConfig(dt_s=5e-6,n_particles=2)
    state=ParticleState.create([[-.02,.05],[.02,.05]],[.003,.0043],[1e-6,c.particle_mass_kg])
    with pytest.raises(ValueError,match='actual particle masses'):FixedGrainSystem(c,state)


def test_mixture_physical_masses_and_paired_initial_states():
    d=json.loads((ROOT/'configs/m7a/pilot.json').read_text());p=d['common'];c=HopperConfig(**p['config'])
    a=mixture_packing(c);b=mixture_packing(c);other=mixture_packing(replace(c,seed=c.seed+1))
    np.testing.assert_array_equal(a.position,b.position);np.testing.assert_array_equal(a.radius,b.radius)
    assert not np.array_equal(a.radius,other.radius)
    np.testing.assert_allclose(a.mass,940*.00318*np.pi*a.radius**2)
    assert dict(zip(*np.unique(a.radius,return_counts=True)))=={.003:20,.0037:20,.0043:20}
    assert c.dt_s<c.timestep_limit_s(float(a.mass.min()))
    delta=np.linalg.norm(a.position[:,None]-a.position[None,:],axis=2)
    i,j=np.triu_indices(c.n_particles,1);assert np.all(delta[i,j]>a.radius[i]+a.radius[j])


def test_flat_floor_and_obstacle_edge_reference():
    c=HopperConfig();o=c.outlet_width_m/2
    a=obstacle_at_outlet(c,.3,.002);b=obstacle_at_outlet(c,1.14,.002)
    assert a.center_m==(-o-.3*.004,.002)
    assert b.center_m[0]<a.center_m[0]
    assert len(flat_floor_walls(c,0))==5 and len(flat_floor_walls(c,.05))==4
    np.testing.assert_array_equal(flat_floor_walls(c,.05),flat_floor_walls(c,1.))


@pytest.mark.parametrize('q',[-1,np.inf,np.nan,100])
def test_invalid_obstacle_position_rejected(q):
    with pytest.raises(ValueError):obstacle_at_outlet(HopperConfig(),q)


def test_wall_outlet_conservation_and_actual_crossing_mass():
    c=HopperConfig(n_particles=2,gate_open_time_s=0)
    s=ParticleState.create([[0,.003],[-.04,.005]],.002,[c.particle_mass_kg,2*c.particle_mass_kg])
    system=FixedGrainSystem(c,s);system.advance(10000)
    assert np.isfinite(system.crossing_time).sum()==1 and not s.active[0] and s.active[1]
    assert np.sum(s.mass[np.isfinite(system.crossing_time)])/s.mass.sum()==pytest.approx(1/3)
    assert s.active.sum()+(~s.active).sum()==2
    assert s.position[1,1]>=.002*(1-c.max_overlap_ratio)
    assert system.max_overlap_ratio<c.max_overlap_ratio  # rebound need not have settled at 0.1s


def test_legacy_wedge_bitwise_preserved():
    c=HopperConfig(n_particles=5)
    a=DEMSystem(c,initial_state(c));b=FixedGrainSystem(c,initial_state(c),geometry='wedge')
    a.advance(4000);b.advance(4000)
    assert a.history and set(a.history)==set(b.history)
    for key in ('position','velocity','angle','omega'):np.testing.assert_array_equal(getattr(a.state,key),getattr(b.state,key))


def test_passive_graph_does_not_advance_friction_memory():
    s=isolated(v=(0,.1));s.forces();before=deepcopy(s.obstacle_history)
    for _ in range(4):contact_graph(s)
    assert all(np.array_equal(v,s.obstacle_history[k]) for k,v in before.items())


def test_short_solver_trajectory_deterministic_and_geometry_exported():
    p=json.loads((ROOT/'configs/m7a/pilot.json').read_text())['common']
    p=dict(p,config=dict(p['config'],n_particles=6),duration_s=.001,sample_every=100,position_over_dFG=.3)
    a,ma=simulate_fixed_grain(p);b,mb=simulate_fixed_grain(p)
    for key in a:np.testing.assert_array_equal(a[key],b[key])
    assert ma['obstacle']==mb['obstacle'] and ma['initial_state_sha256']==mb['initial_state_sha256']
    assert ma['source_five_second_protocol_matched'] is False


@pytest.mark.parametrize('backend',['taichi-cpu','cuda'])
def test_fixed_grain_taichi_contact_parity(backend):
    if os.environ.get('PHARMAFLOW_TEST_TAICHI')!='1':pytest.skip('Strict Taichi CPU/CUDA opt-in')
    a=isolated(v=(-.01,.03),spin=1)
    b=FixedGrainSystem(a.config,deepcopy(a.state),a.obstacle,walls=(),track_outlet=False,backend=backend)
    a.advance(80);b.advance(80)
    np.testing.assert_allclose(a.state.position,b.state.position,atol=1e-13)
    np.testing.assert_allclose(a.state.omega,b.state.omega,atol=1e-9)


def test_frozen_design_budget_unique_and_no_failed_retry(tmp_path):
    d=json.loads((ROOT/'configs/m7a/pilot.json').read_text());entries=tasks(d)
    assert len(entries)==12 and len({r['run_id'] for r in entries})==12
    (tmp_path/'data/simulated/m7a').mkdir(parents=True);con=connect_ledger(tmp_path)
    for e in entries:assert reserve(con,e)
    con.execute('UPDATE attempts SET status="failed"');con.commit()
    assert not reserve(con,entries[0])
    with pytest.raises(ValueError,match='budget'):reserve(con,dict(entries[0],run_id='extra'))
    assert con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==12
    con.close()


def test_obstacle_can_anchor_a_real_contact_chain():
    from pharmaflow.m3_events import spans
    c=HopperConfig(n_particles=3,width_m=.1,outlet_width_m=.008,gate_open_time_s=0,gravity_m_s2=0)
    state=ParticleState.create([[-.0013,.002],[.0026,.002],[.0065,.00195]],.002,c.particle_mass_kg)
    system=FixedGrainSystem(c,state,FixedGrain((-.0052,.002),.002))
    assert spans(contact_graph(system))
    system.obstacle=None
    assert not spans(contact_graph(system))


def test_freeze_cannot_silently_change_design(tmp_path):
    import shutil
    from pharmaflow.m7a_campaign import freeze,source_hashes
    for name in source_hashes(ROOT):
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    for folder in ('configs/m7a','docs/results/m7a'):(tmp_path/folder).mkdir(parents=True,exist_ok=True)
    design=json.loads((ROOT/'configs/m7a/pilot.json').read_text())
    config=tmp_path/'configs/m7a/pilot.json';config.write_text(json.dumps(design))
    (tmp_path/'docs/results/m7a/prepilot_verification.json').write_text('{"status":"PASS"}')
    (tmp_path/'docs/results/m7a/geometry_gate.json').write_text('{"numerical_geometry_representable":true}')
    first=freeze(tmp_path);assert freeze(tmp_path)==first
    design['common']['duration_s']=1.1;config.write_text(json.dumps(design))
    with pytest.raises(ValueError,match='Frozen'):freeze(tmp_path)


def test_failed_async_dispatch_is_charged_and_never_retried(tmp_path,monkeypatch):
    from pharmaflow import m7a_campaign as campaign
    (tmp_path/'data/simulated/m7a/failures').mkdir(parents=True)
    (tmp_path/'outputs/metrics/m7a').mkdir(parents=True)
    entry=dict(run_id='transport_failure_test',parameters={});calls=[]
    monkeypatch.setattr(campaign,'freeze',lambda root:dict(entries=[entry]))
    class Failed:
        returncode=1
        async def wait(self):return 1
    async def create(*args,**kwargs):calls.append(args);return Failed()
    monkeypatch.setattr(campaign.asyncio,'create_subprocess_exec',create)
    campaign.dispatch(tmp_path,profile_only=True);campaign.dispatch(tmp_path,profile_only=True)
    con=connect_ledger(tmp_path)
    assert con.execute('SELECT status FROM attempts').fetchall()==[('failed',)]
    assert len(calls)==1
    assert (tmp_path/'data/simulated/m7a/failures/transport_failure_test.json').exists()
    con.close()


def test_async_dispatch_never_exceeds_three_single_thread_workers(tmp_path,monkeypatch):
    from pharmaflow import m7a_campaign as campaign
    base=tmp_path/'data/simulated/m7a';(base/'failures').mkdir(parents=True)
    (base/'trajectories').mkdir();(tmp_path/'outputs/metrics/m7a').mkdir(parents=True)
    entries=[dict(run_id='budget_only_'+str(i),parameters={}) for i in range(12)]
    con=connect_ledger(tmp_path);reserve(con,entries[0]);con.execute('UPDATE attempts SET status="success"');con.commit();con.close()
    (base/'trajectories/budget_only_0.json').write_text(json.dumps(dict(wall_time_s=.1,completed_discharge=False,duration_actual_s=1.)))
    monkeypatch.setattr(campaign,'freeze',lambda root:dict(entries=entries))
    active=0;peak=0
    class Failed:
        returncode=1
        async def wait(self):
            nonlocal active
            await campaign.asyncio.sleep(.005);active-=1;return 1
    async def create(*args,**kwargs):
        nonlocal active,peak
        active+=1;peak=max(peak,active)
        assert kwargs['env']['OPENBLAS_NUM_THREADS']=='1'
        return Failed()
    monkeypatch.setattr(campaign.asyncio,'create_subprocess_exec',create)
    campaign.dispatch(tmp_path)
    con=connect_ledger(tmp_path);assert con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==12;con.close()
    assert peak==3


def test_visual_export_preserves_actual_solver_frames(tmp_path,monkeypatch):
    from pharmaflow.m7a_visuals import frame_data,png_bytes,export_gif
    from pharmaflow.fixed_grain import FixedGrainSystem
    p=json.loads((ROOT/'configs/m7a/pilot.json').read_text())['common']
    p=dict(p,config=dict(p['config'],n_particles=6),duration_s=.001,sample_every=100,position_over_dFG=.3)
    arrays,metadata=simulate_fixed_grain(p)
    frame=frame_data(arrays,2)
    assert frame['time_s']==arrays['time_s'][2]
    np.testing.assert_array_equal(frame['positions'],arrays['position_m'][2,arrays['active'][2]])
    assert not frame['positions'].flags.writeable
    monkeypatch.setattr(FixedGrainSystem,'step',lambda *a,**k:pytest.fail('Playback must not step the DEM solver'))
    png=png_bytes(arrays,metadata,2)
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    target=tmp_path/'actual.gif';manifest=export_gif(arrays,metadata,target,max_frames=3)
    assert target.read_bytes()[:6] in (b'GIF87a',b'GIF89a')
    assert manifest['source']=='actual_M7A_DEM_stored_states'
    np.testing.assert_array_equal(manifest['physical_times_s'],arrays['time_s'][manifest['stored_frame_indices']])
    with pytest.raises(ValueError):frame_data(arrays,len(arrays['time_s']))


def test_m7a_dashboard_replays_without_starting_solver(monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    from pharmaflow.fixed_grain import FixedGrainSystem
    from pharmaflow.dem import DEMSystem
    def prohibited(*args,**kwargs):raise AssertionError('M7A playback must use stored states only')
    monkeypatch.setattr(FixedGrainSystem,'step',prohibited)
    monkeypatch.setattr(DEMSystem,'step',prohibited)
    at=AppTest.from_file(str(ROOT/'app/streamlit_app.py'),default_timeout=60).run()
    assert not at.exception
    at.sidebar.radio[0].set_value('M7A fixed grain').run()
    assert not at.exception