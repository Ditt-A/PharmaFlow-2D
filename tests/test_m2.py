from dataclasses import replace, asdict
import json
import numpy as np
import pytest
from pharmaflow.config import HopperConfig
from pharmaflow.dem import DEMSystem, ParticleState, initial_state
from pharmaflow.validation import PhysicsMonitor, flow_metrics
from pharmaflow.run import simulate
from pharmaflow.experiments import build_tasks


def test_passive_measurement_preserves_interacting_trajectory():
    c = HopperConfig(n_particles=20)
    plain, _ = simulate(c, .02, 100)
    measured, metadata = simulate(c, .02, 100, monitor=PhysicsMonitor(c))
    for key in plain:
        np.testing.assert_array_equal(plain[key], measured[key])
    assert len(measured['diag_kinetic_j']) == len(measured['time_s'])
    assert metadata['physics_monitor']['boundary_center_leak_samples'] == 0


def test_contact_histogram_force_spin_and_dissipation_are_measured():
    c = replace(HopperConfig(), gravity_m_s2=0)
    state = ParticleState.create([[-.00195,0],[.00195,0]],c.particle_radius_m,c.particle_mass_kg,[[.03,.08],[-.03,-.02]])
    system = DEMSystem(c,state,walls=(),track_outlet=False)
    monitor=PhysicsMonitor(c);system.monitor=monitor
    monitor.sample(system)
    system.advance(200);monitor.sample(system)
    report=monitor.summary()
    assert sum(report['overlap_histogram_counts']) == report['contact_step_observations'] > 0
    assert report['max_contact_force_n'] > 0
    assert report['max_angular_speed_rad_s'] > 0
    assert report['normal_damping_loss_j'] > 0
    assert np.all(np.isfinite(monitor.arrays()['diag_normal_spring_j']))


def test_removed_energy_is_advected_not_silently_lost():
    c=HopperConfig(n_particles=1,gate_open_time_s=0)
    state=ParticleState.create([[0,.001]],c.particle_radius_m,c.particle_mass_kg)
    system=DEMSystem(c,state)
    monitor=PhysicsMonitor(c);system.monitor=monitor
    system.advance(10000)
    assert not state.active[0]
    expected=.5*state.mass[0]*np.sum(state.velocity[0]**2)+state.mass[0]*c.gravity_m_s2*state.position[0,1]
    assert monitor.exported == pytest.approx(expected)


def synthetic(crossings, n=5, duration=.5):
    c=HopperConfig(n_particles=n,gate_open_time_s=0)
    t=np.linspace(0,duration,11)
    p=np.tile(np.column_stack((np.linspace(-.01,.01,n),np.full(n,.03))),(len(t),1,1))
    ct=np.full(n,np.nan);ct[:len(crossings)]=crossings
    for i,when in enumerate(crossings):p[t>=when,i,1]=-.01
    a={'time_s':t,'position_m':p,'velocity_m_s':np.zeros_like(p),'active':np.ones((len(t),n),bool),
       'radius_m':np.full(n,c.particle_radius_m),'crossing_time_s':ct,
       'discharged_count':np.array([np.sum(ct<=x) for x in t])}
    return a,c


def test_flow_bins_account_for_every_crossing_and_empty_has_priority():
    a,c=synthetic([.1,.11,.3,.4,.49])
    m=flow_metrics(a,c,.5)
    assert m['flow_state']=='completed_discharge'
    assert m['had_interior_pause']
    assert np.sum(np.array(m['flow_rate_particles_s'])*np.diff(m['flow_bin_edges_s'])) == pytest.approx(5)
    assert m['time_to_empty_s']==.49


def test_resumed_flow_after_quiet_gap_is_intermittent_not_permanent_clog():
    a,c=synthetic([.1,.12,.3])
    m=flow_metrics(a,c,.5)
    assert m['flow_state']=='intermittent_flow'
    assert not m['permanent_clogging_claimed']
    assert not m['arch']['observed_stationary_spanning_arch']


def test_continuous_and_unresolved_are_separate_from_empty():
    a,c=synthetic([.41,.44,.48])
    assert flow_metrics(a,c,.5)['flow_state']=='continuous_flow_observed'
    a,c=synthetic([])
    assert flow_metrics(a,c,.5)['flow_state']=='unresolved_transient'


def test_past_crossings_do_not_make_a_reentered_hopper_empty():
    a,c=synthetic([.1,.11,.12,.13,.14])
    a['position_m'][-1,0,1]=.01
    assert flow_metrics(a,c,.5)['flow_state']!='completed_discharge'


def test_paired_tasks_share_initial_state_and_physical_times():
    suite={'base':{'n_particles':10},'seeds':[11], 'dt_factors':[1,2,4], 'duration_s':.1,
           'sample_interval_s':.0025, 'cases':[{'name':'paired','outlet_ratio':3}]}
    tasks=build_tasks(suite)
    states=[initial_state(HopperConfig(**t['config'])).position for t in tasks]
    for state in states[1:]:np.testing.assert_array_equal(state,states[0])
    assert {t['duration_s'] for t in tasks}=={.1}
    assert all(t['sample_every']*t['config']['dt_s']==pytest.approx(.0025) for t in tasks)


def test_invalid_sampling_grid_rejected():
    suite={'seeds':[1],'duration_s':.1,'sample_interval_s':.000012,'cases':[{'name':'bad'}]}
    with pytest.raises(ValueError,match='sampling'):build_tasks(suite)


def test_fill_lift_changes_configuration_without_creating_overlap():
    c=HopperConfig(n_particles=20)
    a,b=initial_state(c),initial_state(replace(c,initial_lift_m=.01))
    np.testing.assert_allclose(b.position-a.position,np.tile([0,.01],(20,1)))
    with pytest.raises(ValueError):replace(c,initial_lift_m=-1).validate()


def test_elastic_analytic_solution_and_energy_converge(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from benchmark_m2 import controlled_pair
    measured=[controlled_pair(dt)[0] for dt in (1e-5,5e-6,2.5e-6)]
    assert measured[1]['max_energy_change_fraction'] < .6*measured[0]['max_energy_change_fraction']
    assert measured[2]['max_energy_change_fraction'] < .6*measured[1]['max_energy_change_fraction']
    assert measured[-1]['final_position_error_m'] < 1e-9


def test_damped_pair_loses_energy_with_finite_spin(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from benchmark_m2 import controlled_pair
    measured,trace=controlled_pair(2.5e-6,True)
    assert .9 < measured['final_energy_fraction'] < .99
    assert measured['max_omega_rad_s'] > 1
    assert np.all(np.isfinite(trace['omega']))
