"""Fail-loud dataset QA for physics, chronology, future-only labels and grouped splits."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .config import HopperConfig
from .run import load_run
from .m3_campaign import digest_file
from .m3_dataset import run_records
from .m3_features import extract_features,FRAME_FIELDS
from .m3_events import detect_events,label_frames


def audit_dataset(root='data/simulated/m3',processed='data/processed/m3'):
    root,processed=Path(root),Path(processed)
    manifest=json.loads((processed/'dataset_manifest.json').read_text())
    for name,info in manifest['files'].items():
        if digest_file(processed/name)!=info['sha256']:raise RuntimeError('Processed checksum mismatch: '+name)
    runs=pd.read_parquet(processed/'run_metadata.parquet');features=pd.read_parquet(processed/'temporal_features.parquet');labels=pd.read_parquet(processed/'event_labels.parquet')
    if runs.run_id.duplicated().any() or features.duplicated(['run_id','frame_index']).any() or labels.duplicated(['run_id','frame_index','horizon_s']).any():raise RuntimeError('Duplicate row keys')
    numeric=features.select_dtypes(include='number')
    if not np.isfinite(numeric.to_numpy()).all() or features.isna().any().any():raise RuntimeError('Missing/nonfinite features')
    if not labels[labels.label_status!='eligible'].target.isna().all():raise RuntimeError('Censored/ineligible example has target')
    if not labels[labels.label_status=='eligible'].target.isin([0,1]).all():raise RuntimeError('Eligible target invalid')
    raw=run_records(root);seen={};initial_seen={};duplicates=[];initial_reuse=[];checks=[];lead=[];censoring_checks=[]
    valid_ids=set(runs[runs.status=='ok'].run_id)
    if set(features.run_id)!=valid_ids or set(labels.run_id)!=valid_ids:raise RuntimeError('Invalid/failure run enters feature/label tables')
    for r in raw:
        if r['status']!='ok':
            if not (root/'failures'/(r['run_id']+'.json')).exists():raise RuntimeError('Failure missing from separate catalog')
            continue
        path=root/r['phase']/r['run_id']/'trajectory.npz'
        if digest_file(path)!=r['npz_sha256']:raise RuntimeError('Raw checksum mismatch')
        a,embedded=load_run(path);c=HopperConfig(**r['config']);t=a['time_s'];n=c.n_particles
        if embedded['run_id']!=r['run_id'] or embedded['solver_source_sha256']!=r['solver_source_sha256']:raise RuntimeError('Embedded run identity/source mismatch')
        if embedded['config']!=r['config'] or embedded['initial_state_sha256']!=r['initial_state_sha256']:raise RuntimeError('Embedded physical configuration/packing mismatch')
        if not np.allclose(np.diff(t),r['sample_interval_s'],rtol=0,atol=1e-12) or t[0]!=0:raise RuntimeError('Inconsistent sampling timestamps')
        if not np.isclose(t[-1],r['observation_duration_s'],rtol=0,atol=1e-12):raise RuntimeError('Duration mismatch')
        if r['checks']['max_overlap_over_radius']>c.max_overlap_ratio or not r['checks']['particle_conservation'] or r['physics']['boundary_center_leak_samples']:
            raise RuntimeError('Invalid physics exported as successful')
        if np.any(np.diff(a['active'].astype(int),axis=0)>0) or np.any(np.diff(a['discharged_count'])<0):raise RuntimeError('Invalid removal/discharge history')
        if not np.array_equal(a['particle_id'],np.arange(n)) or a['active'].shape!=(len(t),n):raise RuntimeError('Particle identity/accounting mismatch')
        if not a['active'][0].all() or not np.allclose(a['radius_m'],c.particle_radius_m) or not np.allclose(a['mass_kg'],c.particle_mass_kg):raise RuntimeError('Initial mass/radius/accounting mismatch')
        for key,value in a.items():
            if key!='crossing_time_s' and not np.isfinite(value).all():raise RuntimeError('Nonfinite raw array: '+key)
        cross=a['crossing_time_s']
        expected=np.array([np.sum(np.isfinite(cross)&(cross<=time+1e-12)) for time in t])
        if not np.array_equal(expected,a['discharged_count']):raise RuntimeError('Inconsistent outlet counts')
        if np.any((~a['active'])&~np.isfinite(cross)[None,:]):raise RuntimeError('Unaccounted removal')
        duplicate=seen.get(r['trajectory_sha256'])
        if duplicate:duplicates.append([duplicate,r['run_id']])
        seen[r['trajectory_sha256']]=r['run_id']
        previous=initial_seen.get(r['initial_state_sha256'])
        if previous:initial_reuse.append([previous,r['run_id']])
        initial_seen[r['initial_state_sha256']]=r['run_id']
        events=detect_events(a,c.gate_open_time_s,r['protocol'])
        if events:
            cutoff=events[0]['onset_time_s']+r['protocol']['persistence_s']/2
            length=int(np.searchsorted(t,cutoff,side='right'))
            prefix={k:(v[:length].copy() if v.ndim>0 and v.shape[0]==len(t) else v.copy()) for k,v in a.items()}
            prefix_events=detect_events(prefix,c.gate_open_time_s,r['protocol'])
            prefix_labels=label_frames(prefix,prefix_events,gate_open_s=c.gate_open_time_s,protocol=r['protocol'])
            censored=[row for row in prefix_labels if row['label_status']=='right_censored']
            if prefix_events or not censored or any(row['target'] is not None for row in censored):raise RuntimeError('Truncated real event trace is not correctly censored')
            if extract_features(prefix,c,r['packing_family'])!=extract_features(a,c,r['packing_family'])[:length]:raise RuntimeError('Truncation changes causal prefix features')
            censoring_checks.append(dict(run_id=r['run_id'],truncated_at_s=float(prefix['time_s'][-1]),
                                         censored_rows=len(censored),passed=True,included_as_training_examples=False))
        expected_labels=pd.DataFrame(label_frames(a,events,gate_open_s=c.gate_open_time_s,protocol=r['protocol']))
        expected_labels['target']=pd.array(expected_labels.target,dtype='Int8')
        actual=labels[labels.run_id==r['run_id']].reset_index(drop=True)
        for key in ('frame_index','time_s','horizon_s','label_status','target'):
            if not actual[key].equals(expected_labels[key]):raise RuntimeError('Label inconsistency: '+r['run_id']+' '+key)
        positive=actual[actual.target==1]
        if len(positive):
            delta=positive.event_onset_time_s-positive.time_s
            if np.any(delta<=0) or np.any(delta>positive.horizon_s+1e-12):raise RuntimeError('Positive target outside (t,t+H]')
            lead.append(dict(run_id=r['run_id'],min_s=float(delta.min()),max_s=float(delta.max()),positive_rows=len(positive)))
        # Executable causal-prefix test: mutate all future observations/counts.
        cutoff=max(1,len(t)//2);changed={k:v.copy() for k,v in a.items()}
        for key in FRAME_FIELDS:changed[key][cutoff:]=changed[key][cutoff:]+100
        changed['discharged_count'][cutoff:]+=n
        before=extract_features(a,c,r['packing_family'])[:cutoff]
        after=extract_features(changed,c,r['packing_family'])[:cutoff]
        if before!=after:raise RuntimeError('Future observations change past features')
        checks.append(dict(run_id=r['run_id'],finite=True,conserved=True,timestamps_consistent=True,causal_prefix_passed=True))
    if duplicates:raise RuntimeError('Duplicate trajectories: '+str(duplicates))
    split=json.loads((processed/'split_manifest.json').read_text())
    for name,benchmark in split['benchmarks'].items():
        if set(benchmark['run_assignments'])!=valid_ids:raise RuntimeError('Incomplete split membership')
        if name=='configuration_holdout':
            table=runs[runs.status=='ok'].copy();table['split']=table.run_id.map(benchmark['run_assignments'])
            if (table.groupby('physical_group_id')['split'].nunique()>1).any():raise RuntimeError('Physical configuration leakage')
            if (table.groupby('configuration_id')['split'].nunique()>1).any():raise RuntimeError('Configuration ID leakage')
    eligible=labels[labels.label_status=='eligible'].merge(features[['run_id','frame_index','outlet_ratio','discharged_fraction','initial_particle_count']],on=['run_id','frame_index'],validate='many_to_one')
    correlations={}
    for key in ('outlet_ratio','discharged_fraction','initial_particle_count','time_s'):
        correlations[key]=float(eligible[key].corr(eligible.target.astype(float))) if eligible[key].nunique()>1 and eligible.target.nunique()>1 else None
    valid=runs[runs.status=='ok']
    rates=[]
    for ratio,group in valid.groupby('outlet_ratio'):
        rates.append(dict(outlet_ratio=float(ratio),runs=len(group),event_runs=int((group.confirmed_event_count>0).sum()),event_fraction=float((group.confirmed_event_count>0).mean())))
    horizon_stats={}
    for h,group in labels.groupby('horizon_s'):
        e=group[group.label_status=='eligible']
        horizon_stats[str(h)]=dict(positive=int((e.target==1).sum()),negative=int((e.target==0).sum()),
                                  positive_fraction=float((e.target==1).mean()) if len(e) else None,
                                  censored=int((group.label_status=='right_censored').sum()))
    report=dict(passed=True,audit_source_sha256=digest_file(__file__),successful_runs=len(valid),failed_runs=int((runs.status!='ok').sum()),
                censored_runs=int(valid.censored_run.sum()),confirmed_first_events=int(valid.confirmed_event_count.sum()),
                duplicate_trajectories=duplicates,reused_initial_states_across_configs=initial_reuse,
                physics_checks=checks,feature_missing_values=0,feature_nonfinite_values=0,
                label_status_counts={str(k):int(v) for k,v in labels.label_status.value_counts().items()},
                horizon_statistics=horizon_stats,event_lead_time_coverage=lead,
                real_trajectory_censoring_checks=censoring_checks,
                descriptive_frame_label_correlations=correlations,outlet_event_rates=rates,
                split_statistics={name:b['statistics'] for name,b in split['benchmarks'].items()},
                total_raw_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                total_processed_bytes=sum(p.stat().st_size for p in processed.iterdir() if p.is_file() and p.name!='quality_report.json'),
                processed_size_excludes_quality_report=True,
                total_measured_runtime_s=float(runs.runtime_s.sum()),
                max_overlap_over_radius=float(valid.max_overlap_over_radius.max()),
                permanent_clogging_claimed=False,normalization_fitted=False,
                limitations=['Finite-duration first-event labels, not indefinite clogging.','Small adaptive cohort and correlated paired parameter draws; no independent industrial calibration.'])
    (processed/'quality_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report
