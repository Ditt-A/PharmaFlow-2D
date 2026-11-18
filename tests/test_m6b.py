"""Budget, denial handling, immutable raw data and conservative physical interpretation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from pharmaflow.m6b_data import (acquire,verify_acquisition,check_artifact,within,request_small,
    COMPARISON_GATES,compatibility_gate,parse_delft_info,parse_yogi_profiles,author_schema_evidence,
    file_hash,discover_delft_metadata)

ROOT=Path(__file__).resolve().parents[1]


def plan():
    return dict(version='test-only-transport',budget=dict(maximum_curated_files_including_code_docs_reuse_and_failed_reservations=12,
        maximum_transfer_bytes=200000000,maximum_per_file_bytes=20000000,maximum_metadata_file_bytes=1000000,maximum_redirects=5),
        artifacts=[dict(id='a',url='https://zenodo.org/a',path='a.txt',source='transport_test',role='documentation',
        maximum_bytes=20,expected_bytes=4,published_checksum='md5:'+hashlib.md5(b'test').hexdigest(),provider_supported=True)])


class Response:
    def __init__(self,status=200,data=b'test',headers=None):self.status_code=status;self.data=data;self.headers=headers or {}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,size):
        for i in range(0,len(self.data),size):yield self.data[i:i+size]


class Session:
    def __init__(self,*responses):self.responses=list(responses);self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs));return self.responses.pop(0)
    def request(self,method,url,**kwargs):return self.get(url,**kwargs)


@pytest.mark.parametrize('key,value', [('maximum_transfer_bytes',200000001),('maximum_curated_files_including_code_docs_reuse_and_failed_reservations',13)])
def test_hard_limits_cannot_be_relaxed(tmp_path,key,value):
    p=plan();p['budget'][key]=value
    with pytest.raises(ValueError):acquire(p,tmp_path,Session())


@pytest.mark.parametrize('url',['http://zenodo.org/a','https://evil.example/a','https://secret@zenodo.org/a','https://datadryad.org/a.zip'])
def test_unreviewed_routes_or_archives_rejected(url):
    p=plan();p['artifacts'][0]['url']=url
    with pytest.raises(ValueError):check_artifact(p['artifacts'][0],p)


@pytest.mark.parametrize('relative',['../other','/outside','.'])
def test_paths_stay_in_designated_raw_root(tmp_path,relative):
    with pytest.raises(ValueError):within(tmp_path,relative)


def test_checksum_resume_and_plan_freeze(tmp_path):
    p=plan();session=Session(Response())
    a=acquire(p,tmp_path,session)
    assert a['attempts'][0]['provider_checksum_verified']
    b=acquire(p,tmp_path,Session())
    assert a==b and len(session.calls)==1
    assert verify_acquisition(p,tmp_path)==b
    p['version']='changed'
    with pytest.raises(ValueError,match='Plan changed'):acquire(p,tmp_path,Session())


def test_denial_is_failure_never_data_and_blocks_further_payloads(tmp_path):
    p=plan();second=dict(p['artifacts'][0],id='b',path='b.txt');p['artifacts'].append(second)
    session=Session(Response(403,b'No'))
    a=acquire(p,tmp_path,session)
    assert [r['state'] for r in a['attempts']]==['access_failed','blocked_by_prior_denial']
    assert len(session.calls)==1 and a['observed_response_payload_bytes']==2
    assert not (tmp_path/'data/raw/m6b/a.txt').exists()
    assert acquire(p,tmp_path,Session())==a


def test_integrity_failure_retained_and_never_retried(tmp_path):
    p=plan();a=acquire(p,tmp_path,Session(Response(200,b'bad!')))
    assert a['attempts'][0]['state']=='integrity_failed'
    assert (tmp_path/'data/raw/m6b/a.txt').read_bytes()==b'bad!'
    assert acquire(p,tmp_path,Session())==a


def test_immutable_successful_input_cannot_drift(tmp_path):
    p=plan();acquire(p,tmp_path,Session(Response()))
    (tmp_path/'data/raw/m6b/a.txt').write_bytes(b'nope')
    with pytest.raises(ValueError,match='changed'):acquire(p,tmp_path,Session())
    with pytest.raises(ValueError,match='integrity'):verify_acquisition(p,tmp_path)


def test_failed_transfer_still_charged_before_any_io(tmp_path):
    p=plan();a=acquire(p,tmp_path,Session(Response(200,b'x'*30)))
    assert a['attempts'][0]['state']=='failed'
    assert a['reserved_transfer_ceiling_bytes']==8212
    assert a['attempts'][0]['transfer_bytes'] is None
    assert acquire(p,tmp_path,Session())==a


def test_file_and_byte_reservations_reject_over_budget(tmp_path):
    p=plan();p['budget']['maximum_curated_files_including_code_docs_reuse_and_failed_reservations']=1
    p['artifacts'].append(dict(p['artifacts'][0],id='b',path='b.txt'))
    session=Session(Response(403))
    with pytest.raises(ValueError,match='budget exhausted'):acquire(p,tmp_path,session)
    assert len(session.calls)==1
    p=plan();p['budget']['maximum_transfer_bytes']=8211
    with pytest.raises(ValueError,match='reservation'):acquire(p,tmp_path/'new',Session())


def test_redirects_remain_official_and_no_range_or_auth_headers():
    session=Session(Response(302,headers={'Location':'https://evil.example/a'}))
    with pytest.raises(ValueError,match='Unreviewed redirect'):request_small('https://zenodo.org/a',100,session)
    assert len(session.calls)==1
    assert session.calls[0][1]['allow_redirects'] is False
    assert session.calls[0][1]['headers']=={'Accept-Encoding':'identity'}


def pair():
    return dict(id='test',source='test',observable='test',gates=dict.fromkeys(COMPARISON_GATES,True))


@pytest.mark.parametrize('key',COMPARISON_GATES)
def test_unknown_gate_never_allows_quantitative_score(key):
    for unknown in (None,False,1,'true'):
        p=pair();p['gates'][key]=unknown;r=compatibility_gate(p)
        assert not r['agreement_score_allowed'] and key in r['unmet_gates']


def test_classifications_distinguish_absence_model_form_and_qualitative():
    p=pair();assert compatibility_gate(p)['classification']=='QUANTITATIVELY_COMPARABLE'
    assert not compatibility_gate(p)['calibration_claim_allowed']
    p['fatal_unmatched_model_form']=True
    assert compatibility_gate(p)['classification']=='INCOMPATIBLE_MODEL_FORM'
    p['gates']['measurement_accessible']=False
    assert compatibility_gate(p)['classification']=='BLOCKED_BY_MISSING_INFORMATION'
    p=pair();p['gates']['units_and_coordinates_verified']=None;p['native_qualitative_interpretation_supported']=True
    assert compatibility_gate(p)['classification']=='QUALITATIVE_ONLY'


def test_published_gate_list_blocks_all_current_physical_comparisons():
    config=json.loads((ROOT/'configs/m6b/compatibility_gates.json').read_text())
    assert all(not compatibility_gate(p)['agreement_score_allowed'] for p in config['pairs'])


def test_static_code_inspection_never_executes_or_uses_notebook_outputs(tmp_path):
    p=tmp_path/'code.ipynb'
    p.write_text(json.dumps(dict(cells=[dict(cell_type='code',source=['raise RuntimeError("frame")'],outputs=[dict(data={'text/plain':'invented positions'})])])))
    r=author_schema_evidence(p)
    assert not r['executed'] and r['notebook_outputs_not_parsed_as_measurements']==1
    assert 'invented' not in json.dumps(r['evidence'])


def accessible(relative):
    p=ROOT/'data/raw/m6b'/relative
    if not p.exists():pytest.skip('Actual raw provider example not present; run bounded M6B acquisition')
    return p


def test_actual_author_example_schema_is_code_evidence_only():
    p=accessible('author/FlowClass_WithFixedGrain.py')
    assert file_hash(p,'md5')=='706f198fb7d45dea984714b9138c6a5b'
    r=author_schema_evidence(p)
    assert 'loadmat' in json.dumps(r['evidence']) and not r['executed']
    assert r['artifact_type']=='author_code_not_experimental_measurements'


def test_actual_delft_example_parses_metadata_not_mass_or_velocity():
    p=accessible('delft/info_alp_20_d_100.txt')
    assert file_hash(p,'md5')=='da45f2071241856a0173b2ecd9732dbb'
    rows=parse_delft_info(p)
    assert len(rows)==5 and {r['sampling_hz'] for r in rows}=={400.0,600.0}
    assert all(r['mass_discharge_kg_s'] is None and r['coordinate_units'] is None for r in rows)


def test_actual_experimental_numbers_rows_not_repaired_or_promoted_to_trajectories():
    p=accessible('yogi/quasi2D-expt.numbers')
    assert file_hash(p,'md5')=='c701fb415580d6ffa6d9fc9945bce0fe'
    schema,rows=parse_yogi_profiles(p)
    assert len(schema)==4 and len(rows)==320
    assert sum(r['native_y_uy_parseable'] for r in rows)==86
    assert all(not s['time_or_particle_ids_supplied'] for s in schema)
    assert all(not r['units_verified'] for r in rows)
    assert any(r['y_raw'] is not None and r['y_native'] is None for r in rows)


def test_catalog_denial_stops_metadata_and_never_follows_advertised_payloads(tmp_path):
    session=Session(Response(403,b'denied'))
    r=discover_delft_metadata(tmp_path,session)
    assert len(r['attempts'])==len(session.calls)==1
    assert discover_delft_metadata(tmp_path,Session())==r


def test_catalog_cannot_exceed_combined_transfer_ceiling(tmp_path):
    parent=tmp_path/'data/raw/m6b';parent.mkdir(parents=True)
    (parent/'acquisition_ledger.json').write_text(json.dumps(dict(reserved_transfer_ceiling_bytes=197000000)))
    with pytest.raises(ValueError,match='Combined'):discover_delft_metadata(tmp_path,Session())
