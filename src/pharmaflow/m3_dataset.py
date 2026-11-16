"""Causal features, future-only labels, grouped splits and versioned Parquet storage."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .config import HopperConfig
from .run import load_run
from .m3_campaign import digest_file,stable_id
from .m3_events import detect_events,label_frames,PROTOCOL_VERSION
from .m3_features import extract_features,feature_dictionary


def processing_hash():
    h=hashlib.sha256()
    for name in ('m3_events.py','m3_features.py','m3_dataset.py'):
        h.update(name.encode());h.update(Path(__file__).with_name(name).read_bytes())
    return h.hexdigest()


def run_records(root):
    return [json.loads(p.read_text()) for phase in ('pilot','production') for p in sorted((Path(root)/phase).glob('*/run.json'))]


def physical_group(config):
    fields=('width_m','height_m','outlet_width_m','funnel_height_m','particle_radius_m','gravity_m_s2',
            'density_kg_m3','thickness_m','friction','wall_friction','n_particles','initial_lift_m')
    return stable_id({k:config[k] for k in fields})[:20]


def grouped_assignment(rows,key,seed=20261117):
    """Outcome-stratified groups; split selection does not fit/transform features."""
    groups={}
    for r in rows:
        g=r[key];groups.setdefault(g,[]).append(r)
    strata={False:[],True:[]}
    for group,rs in groups.items():strata[any(r['confirmed_event_count']>0 for r in rs)].append(group)
    assignments={}
    for event,values in strata.items():
        values=sorted(values,key=lambda v:hashlib.sha256(f'{seed}:{key}:{v}'.encode()).hexdigest())
        n=len(values)
        if n>=3:
            validation=max(1,round(n*.2));test=max(1,round(n*.2));train=n-validation-test
            names=['train']*train+['validation']*validation+['test']*test
        else:
            names=['train','test'][:n]
        assignments.update(zip(values,names))
    return assignments


def split_statistics(run_rows,labels,assignment,key):
    result={}
    for split in ('train','validation','test'):
        rs=[r for r in run_rows if assignment[r[key]]==split]
        ids={r['run_id'] for r in rs};subset=labels[labels.run_id.isin(ids)]
        eligible=subset[subset.label_status=='eligible']
        result[split]=dict(independent_runs=len(rs),configurations=len({r['physical_group_id'] for r in rs}),
                           event_runs=sum(r['confirmed_event_count']>0 for r in rs),
                           right_censored_runs=sum(r['censored_run'] for r in rs),eligible_examples=len(eligible),
                           positive_examples=int((eligible.target==1).sum()),negative_examples=int((eligible.target==0).sum()),
                           censored_examples=int((subset.label_status=='right_censored').sum()),
                           event_run_fraction=sum(r['confirmed_event_count']>0 for r in rs)/len(rs) if rs else None)
    return result


def build_dataset(root='data/simulated/m3',output='data/processed/m3'):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=True)
    records=run_records(root)
    if not records:raise ValueError('no completed run records')
    for campaign_path in (root/'manifests').glob('*_campaign.json'):
        campaign=json.loads(campaign_path.read_text())
        if campaign.get('state')!='complete':raise RuntimeError('Campaign still incomplete: '+str(campaign_path))
        expected={r['run_id'] for r in campaign['records']}
        actual={r['run_id'] for r in records if r['phase']==campaign['plan']['phase']}
        if actual!=expected:raise RuntimeError('Missing or unregistered campaign run records')
    run_rows=[];features=[];labels=[];event_rows=[];sensitivity=[];raw_manifest=[]
    for r in records:
        base={key:r.get(key) for key in ('run_id','configuration_id','phase','seed','packing_family','packing_id','initial_state_sha256',
              'solver_version','solver_source_sha256','status','numerical_valid','runtime_s','observation_duration_s','continued','censored_run')}
        base.update(error=r.get('error'),physical_parameters_json=json.dumps(r['physical'],sort_keys=True),
                    numerical_parameters_json=json.dumps(r['numerical'],sort_keys=True),sample_interval_s=r['sample_interval_s'],
                    planned_duration_s=r['duration_s'],maximum_duration_s=r['max_duration_s'])
        if r['status']!='ok':
            base.update(confirmed_event_count=0,physical_group_id=None,flow_state='numerical_failure',censored_run=False)
            run_rows.append(base);continue
        path=root/r['phase']/r['run_id']/'trajectory.npz'
        if digest_file(path)!=r['npz_sha256']:raise RuntimeError('Raw checksum mismatch: '+r['run_id'])
        arrays,raw_meta=load_run(path);c=HopperConfig(**r['config'])
        events=detect_events(arrays,c.gate_open_time_s,r['protocol'])
        base.update(physical_group_id=physical_group(r['config']),flow_state=r['flow_state'],config_json=json.dumps(r['config'],sort_keys=True),
                    confirmed_event_count=len(events),censored_run=bool(not events and arrays['remaining_count'][-1]>0),
                    event_onsets_json=json.dumps([e['onset_time_s'] for e in events]),
                    event_confirmations_json=json.dumps([e['confirmation_time_s'] for e in events]),
                    outlet_ratio=c.outlet_width_m/(2*c.particle_radius_m),friction=c.friction,wall_friction=c.wall_friction,
                    wall_angle_deg=float(np.degrees(np.arctan((c.width_m-c.outlet_width_m)/(2*c.funnel_height_m)))),
                    initial_particle_count=c.n_particles,dt_s=c.dt_s,normal_stiffness_n_m=c.normal_stiffness_n_m,
                    max_overlap_over_radius=r['checks']['max_overlap_over_radius'],npz_sha256=r['npz_sha256'],trajectory_path=str(path))
        run_rows.append(base)
        identity=dict(run_id=r['run_id'],configuration_id=r['configuration_id'],physical_group_id=base['physical_group_id'])
        features.extend(dict(row,**identity) for row in extract_features(arrays,c,r['packing_family']))
        labels.extend(dict(row,**identity) for row in label_frames(arrays,events,gate_open_s=c.gate_open_time_s,protocol=r['protocol']))
        event_rows.extend(dict(e,**identity) for e in events)
        for duration in (.2,.4,.6):
            p=dict(r['protocol'],persistence_s=duration)
            found=detect_events(arrays,c.gate_open_time_s,p)
            sensitivity.append(dict(run_id=r['run_id'],persistence_s=duration,event_count=len(found),
                                    first_onset_s=found[0]['onset_time_s'] if found else None))
        raw_manifest.append(dict(run_id=r['run_id'],path=str(path),sha256=r['npz_sha256'],trajectory_sha256=r['trajectory_sha256'],
                                 solver_source_sha256=r['solver_source_sha256'],configuration_id=r['configuration_id'],physical_group_id=base['physical_group_id']))
    metadata=pd.DataFrame(run_rows);feature_table=pd.DataFrame(features);label_table=pd.DataFrame(labels)
    if feature_table.empty:raise ValueError('no valid trajectories')
    label_table['target']=pd.array(label_table['target'],dtype='Int8')
    metadata['censored_run']=metadata['censored_run'].fillna(False).astype(bool)
    for name,table in (('run_metadata',metadata),('temporal_features',feature_table),('event_labels',label_table)):
        table.to_parquet(output/(name+'.parquet'),index=False,engine='pyarrow')
    events_table=pd.DataFrame(event_rows)
    if events_table.empty:events_table=pd.DataFrame(columns=['run_id','event_id','onset_time_s','confirmation_time_s'])
    events_table.to_parquet(output/'events.parquet',index=False)
    pd.DataFrame(sensitivity).to_parquet(output/'persistence_sensitivity.parquet',index=False)
    valid_rows=[r for r in run_rows if r['status']=='ok']
    split=dict(seed=20261117,ratios=[.6,.2,.2],normalization='none; M4 must fit preprocessing using training groups only',benchmarks={})
    for name,key in (('run_grouped','run_id'),('configuration_holdout','physical_group_id')):
        assignment=grouped_assignment(valid_rows,key)
        split['benchmarks'][name]=dict(group_key=key,assignments=assignment,
                                       run_assignments={r['run_id']:assignment[r[key]] for r in valid_rows},
                                       statistics=split_statistics(valid_rows,label_table,assignment,key))
    (output/'split_manifest.json').write_text(json.dumps(split,indent=2,allow_nan=False)+'\n')
    dictionary=feature_dictionary()
    for key in ('run_id','configuration_id','physical_group_id'):
        dictionary[key]=dict(role='identifier_not_predictor',units='identifier',meaning='join/group key; do not use for learning',availability='static',window_s=0,missing_policy='never missing')
    (output/'feature_dictionary.json').write_text(json.dumps(dictionary,indent=2)+'\n')
    files={p.name:dict(sha256=digest_file(p),bytes=p.stat().st_size) for p in sorted(output.iterdir()) if p.suffix in ('.parquet','.json') and p.name not in ('dataset_manifest.json','quality_report.json')}
    manifest=dict(schema_version=1,label_protocol=PROTOCOL_VERSION,processing_source_sha256=processing_hash(),
                  attempted_dataset_runs=len(records),successful_runs=len(valid_rows),failed_runs=len(records)-len(valid_rows),
                  censored_runs=int(metadata['censored_run'].sum()),confirmed_events=len(event_rows),
                  feature_rows=len(feature_table),feature_columns=len(feature_table.columns),label_rows=len(label_table),
                  eligible_positive_examples=int((label_table.target==1).sum()),eligible_negative_examples=int((label_table.target==0).sum()),
                  label_status_counts={str(k):int(v) for k,v in label_table.label_status.value_counts().items()},
                  files=files,raw_trajectories=raw_manifest,model_training=False,permanent_clogging_claimed=False,
                  source_scope='Physics/packing/generation hash on every raw run; separate label/feature processing hash in this manifest.')
    (output/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    return manifest
