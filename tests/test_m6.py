"""M6 unit integrity, comparison gates, run independence and bounded source audit."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json
import numpy as np
import pytest
from pharmaflow.m6_units import (length_to_m,velocity_to_m_s,disk_mass_kg,number_to_mass_rate,
    normalized_number_rate,bulk_areal_density,normalized_mass_rate_2d,beverloo_mass_2d)
from pharmaflow.m6_benchmarks import (VALIDATION_GATES,quantitative_eligibility,crossing_rates,
    grouped_summary,steady_flow_support,delft_file_inventory,delft_acquisition_info)

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=json.loads((ROOT/'configs/m6/benchmark_protocol.json').read_text())


def script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('unit', [None,'pixels','native','dimensionless'])
def test_unknown_coordinate_units_are_not_guessed(unit):
    with pytest.raises(ValueError):length_to_m(20,unit)


def test_explicit_coordinate_velocity_and_frame_conversions():
    np.testing.assert_allclose(length_to_m([2,3],'cm'),[.02,.03])
    np.testing.assert_allclose(velocity_to_m_s([1,-2],'mm/frame',130),[.13,-.26])
    with pytest.raises(ValueError):velocity_to_m_s(3,'mm/frame')
    with pytest.raises(ValueError):velocity_to_m_s(3,'pixels/frame',300)
    with pytest.raises(ValueError):velocity_to_m_s(np.inf,'m/s')


def test_number_mass_and_2d_density_are_distinct():
    mass=disk_mass_kg(.004,2500,.01)
    assert mass==pytest.approx(.0003141592653589793)
    assert number_to_mass_rate(100,mass)==pytest.approx(.031415926535897934)
    assert bulk_areal_density(2500,.01,.8)==20  # kg/m², NOT 2500 kg/m³
    with pytest.raises(ValueError):number_to_mass_rate(100,[mass,mass])
    with pytest.raises(ValueError):number_to_mass_rate(100,None)
    with pytest.raises(ValueError):bulk_areal_density(2500,.01,1.1)


def test_dimensionless_scaling_has_explicit_constants_and_units():
    q=beverloo_mass_2d(.04,.004,9.81,20,1.2,1.5)
    assert normalized_mass_rate_2d(q,20,.004,9.81)==pytest.approx(1.2*(10-1.5)**1.5)
    assert beverloo_mass_2d(.08,.008,9.81,20,1.2,1.5)/q==pytest.approx(2**1.5)
    assert normalized_number_rate(100,.004,9.81)==pytest.approx(100*np.sqrt(.004/9.81))
    with pytest.raises(ValueError):normalized_number_rate(np.nan,.004,9.81)
    with pytest.raises(ValueError):normalized_mass_rate_2d(-1,20,.004,9.81)


@pytest.mark.parametrize('outlet,offset',[(.005,1.5),(.006,1.5),(.02,-1),(.02,np.nan)])
def test_clogged_or_undefined_free_flow_domain_is_not_zero_regression(outlet,offset):
    with pytest.raises(ValueError):beverloo_mass_2d(outlet,.004,9.81,20,1.2,offset)


def test_crossing_intervals_and_mixture_masses():
    times=[0,.05,.10,.10,.20,np.nan]
    r=crossing_rates(times,[0,.10,.20],[1,2,3,4,5,6])
    np.testing.assert_array_equal(r['count'],[3,1])
    np.testing.assert_allclose(r['mass_rate_kg_s'],[90,50])
    assert np.sum(r['number_rate_s']*(r['end_s']-r['start_s']))==4
    with pytest.raises(ValueError):crossing_rates([np.inf],[0,1])
    with pytest.raises(ValueError):crossing_rates([.1],[0,0])
    with pytest.raises(ValueError):crossing_rates([.1],[0,1],[0])


def test_comparison_requires_all_evidence_and_never_claims_calibration():
    evidence={g:True for g in VALIDATION_GATES}
    assert quantitative_eligibility(evidence)['quantitative_validation_allowed']
    assert not quantitative_eligibility(evidence)['calibration_claim_allowed']
    for gate in VALIDATION_GATES:
        for unknown in (None,False,'true',1):
            r=quantitative_eligibility(dict(evidence,**{gate:unknown}))
            assert not r['quantitative_validation_allowed'] and gate in r['unresolved_or_failed_gates']


def test_uncertainty_resamples_runs_not_frames():
    base=grouped_summary([1,2,3,8],['a','a','a','b'])
    repeated=grouped_summary([1,2,3]*100+[8],['a']*300+['b'])
    assert base['mean']==repeated['mean']==5
    assert base['ci95']==repeated['ci95']
    single=grouped_summary([1,2,3],['one']*3)
    assert single['ci95'] is None and single['sample_sd'] is None


def stationary_trace():
    t=np.arange(501)*.005
    count=np.floor(np.maximum(0,t-.05)*300).astype(int)
    return dict(time_s=t,discharged_count=count,remaining_count=1000-count)


def test_prospective_steady_flow_positive_control():
    r=steady_flow_support(stationary_trace(),SimpleNamespace(gate_open_time_s=.05,n_particles=1000),PROTOCOL['steady_flow'])
    assert r['eligible_for_scaling'] and r['observed_crossings']>200
    assert r['block_cv']<.03 and not r['fitting_performed']


def test_arch_tail_and_small_depleted_fill_are_not_sustained_flow():
    t=np.arange(501)*.005;c=np.minimum(np.floor(np.maximum(0,t-.05)*300),40)
    r=steady_flow_support(dict(time_s=t,discharged_count=c,remaining_count=50-c),
                          SimpleNamespace(gate_open_time_s=.05,n_particles=50),PROTOCOL['steady_flow'])
    assert not r['eligible_for_scaling'] and 'flow_interruption_or_arch_tail' in r['reasons']
    c=np.minimum(c,30)
    r=steady_flow_support(dict(time_s=t,discharged_count=c,remaining_count=30-c),
                          SimpleNamespace(gate_open_time_s=.05,n_particles=30),PROTOCOL['steady_flow'])
    assert not r['eligible_for_scaling'] and r['usable_window_s']<1


def test_nonfinite_or_fractional_counts_rejected():
    a=stationary_trace();a['discharged_count']=a['discharged_count'].astype(float);a['discharged_count'][50]=1.5
    with pytest.raises(ValueError):steady_flow_support(a,SimpleNamespace(gate_open_time_s=.05,n_particles=1000),PROTOCOL['steady_flow'])


def test_acquisition_annotations_preserve_unknown_headerless_units():
    a=delft_acquisition_info('% [run nr, framerate, t_s]\n1, 400, 7\n2, 600, 7')
    assert [r['sampling_hz'] for r in a]==[400,600]
    b=delft_acquisition_info('r1 400\nr2 600')
    assert all(r['sampling_hz'] is None and not r['header_verified'] for r in b)
    with pytest.raises(ValueError):delft_acquisition_info('% framerate\n1,0')
    with pytest.raises(ValueError):delft_acquisition_info('r1 400\nr1 600')


def test_file_inventory_does_not_download_archives():
    page='<li><span class="size">2,300,000 bytes</span><span>MD5: <code>'+'a'*32+'</code></span><a href="/file/id/file">run.7z</a></li>'
    r=delft_file_inventory(page,'https://data.4tu.nl/datasets/id')
    assert len(r)==1 and r[0]['bytes']==2300000 and r[0]['published_checksum']=='md5:'+'a'*32


class Response:
    status_code=200
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,size):
        for i in range(0,len(self.data),size):yield self.data[i:i+size]


def test_bounded_download_stops_oversized_and_rejects_archive_before_get():
    module=script('audit_m6_sources');calls=[]
    session=SimpleNamespace(get=lambda *a,**k:(calls.append(a),Response(b'x'*101))[1])
    with pytest.raises(ValueError,match='cap'):module.bounded_fetch('https://datadryad.org/metadata',100,session)
    assert len(calls)==1
    for url in ('https://datadryad.org/data.zip','https://data.4tu.nl/run.7z','http://data.4tu.nl/data','https://other.example/metadata'):
        with pytest.raises(ValueError):module.bounded_fetch(url,100,session)
    assert len(calls)==1


def test_published_checksum_is_verified_not_assumed():
    module=script('audit_m6_sources');raw=b'known small file'
    assert module.checksum_ok(raw,'sha256:'+hashlib.sha256(raw).hexdigest())
    assert module.checksum_ok(raw,None) is None
    assert not module.checksum_ok(raw,'md5:'+'0'*32)


def test_replay_selection_excludes_historical_validation_tests_and_demo(monkeypatch):
    module=script('benchmark_m6')
    m3=json.loads((ROOT/'docs/results/m3/split_manifest.json').read_text())
    all_m3=set.union(*[set(b['run_assignments']) for b in m3['benchmarks'].values()])
    expected=set.intersection(*[{k for k,v in b['run_assignments'].items() if v=='train'} for b in m3['benchmarks'].values()])
    dev=json.loads((ROOT/'docs/results/m4b/development_split_manifest.json').read_text())['assignments']
    records=[dict(run_id=k,source='historical') for k in all_m3|set(dev)|{'m4b_locked_forbidden'}]
    records.append(dict(run_id='demo_forbidden',source='demo'))
    monkeypatch.setattr(module,'historical_registry',lambda root:records)
    allowed={r['run_id'] for r in module.permitted_records(ROOT)}
    assert allowed & all_m3 == expected
    assert not {'m4b_locked_forbidden','demo_forbidden'} & allowed
    assert not {k for k,v in dev.items() if v!='train'} & allowed


def test_proposal_is_not_authorization_or_a_demo_budget_change():
    assert PROTOCOL['future_m6b_budget_proposal']['launched'] is False
    assert PROTOCOL['future_m6b_budget_proposal']['m5_demo_attempts_used']==0
    sources=json.loads((ROOT/'configs/m6/external_sources.json').read_text())
    assert sources['download_policy']['solver_attempts']==0
    assert len(PROTOCOL['benchmarks'])==7
    assert all(a['expected_bytes'] is None or a['expected_bytes']<=a['maximum_bytes']<=1000000 for a in sources['artifacts'])
