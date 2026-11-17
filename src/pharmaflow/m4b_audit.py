"""Historical immutability, budget, release independence and chronological replay audit."""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from .m4_data import digest, write_json, exact_join, feature_sets, run_weights
from .m4b_models import predict
from .m4_audit import verify_prediction_replay
from .m4b_data import load_tables, verify_release, historical_training_ids
from .m4b_evaluation import verify_freeze
from .m4b_online import online_warnings
from .run import load_run
from .config import HopperConfig
from .m3_events import detect_events,label_frames
from .m3_packing import make_packing


def audit(root='data/simulated/m4b', data='data/processed/m4b', output='outputs/metrics/m4b', report='docs/results/m4b'):
    root,data,output,report=map(Path,(root,data,output,report))
    historical=json.loads((output/'historical_snapshot.json').read_text())
    for path,sha in historical.items():
        if digest(path)!=sha:raise ValueError('Historical M1-M4A asset changed: '+path)
    frozen=verify_freeze(root,output)
    receipt=json.loads((output/'locked_evaluation_receipt.json').read_text())
    for path,key in [(output/'model_and_policy_freeze.json','model_freeze_sha256'),
                     (output/'predictions.parquet','predictions_sha256'),(output/'event_run_metrics.parquet','runs_sha256'),
                     (report/'metrics.csv','metrics_sha256')]:
        if digest(path)!=receipt[key]:raise ValueError('Saved evaluation changed')
    ledger=json.loads((root/'manifests/attempts.json').read_text())['attempts']
    if len(ledger)>48 or any(r['state']!='finished' for r in ledger.values()):raise ValueError('Budget/incomplete attempt')
    records=[r['result'] for r in ledger.values()]
    valid=[r for r in records if r['status']=='ok']
    real_censor_checks=0
    for r in records:
        if r['status']=='ok':
            if digest(r['trajectory_path'])!=r['npz_sha256']:raise ValueError('Raw checksum mismatch')
            if r['checks']['max_overlap_over_radius']>.15 or r['physics']['boundary_center_leak_samples']:
                raise ValueError('Physics guard violation')
            arrays,embedded=load_run(r['trajectory_path'])
            if embedded['run_id']!=r['run_id'] or embedded['solver_source_sha256']!=r['solver_source_sha256']:
                raise ValueError('Embedded provenance changed')
            for key,value in arrays.items():
                if key!='crossing_time_s' and not np.isfinite(value).all():raise ValueError('Nonfinite raw '+key)
            _,initial=make_packing(HopperConfig(**r['config']),r['packing_family'])
            if initial!=r['initial_state_sha256']:raise ValueError('Initial state is not reproducible')
            if r['events']:
                cutoff=r['events'][0]['onset_time_s']+.2
                n=int(np.searchsorted(arrays['time_s'],cutoff,side='right'))
                prefix={key:(value[:n] if value.ndim and len(value)==len(arrays['time_s']) else value)
                        for key,value in arrays.items()}
                ev=detect_events(prefix,r['config']['gate_open_time_s'],r['protocol'])
                lab=label_frames(prefix,ev,gate_open_s=r['config']['gate_open_time_s'],protocol=r['protocol'])
                censored=[row for row in lab if row['label_status']=='right_censored']
                if ev or not censored or any(row['target'] is not None for row in censored):
                    raise ValueError('Real truncated observation is not censored correctly')
                real_censor_checks+=1
        elif not (root/'failures'/(r['run_id']+'.json')).exists():raise ValueError('Failure not catalogued')
    old=json.loads(Path('data/processed/m3/dataset_manifest.json').read_text())
    old_initial=set(pd.read_parquet('data/processed/m3/run_metadata.parquet').initial_state_sha256)
    new_initial=[r['initial_state_sha256'] for r in valid]
    if len(set(new_initial))!=len(new_initial) or set(new_initial)&old_initial:raise ValueError('Initial packing reused')
    fingerprints=[r['trajectory_sha256'] for r in valid]
    if len(set(fingerprints))!=len(fingerprints) or set(fingerprints)&{r['trajectory_sha256'] for r in old['raw_trajectories']}:
        raise ValueError('Duplicate trajectory')
    for scope in ('pilot','development','locked'):verify_release(data/scope)
    dev,locked=load_tables(data/'development'),load_tables(data/'locked')
    split=json.loads((data/'development/split_manifest.json').read_text())
    old_split=json.loads(Path('data/processed/m3/split_manifest.json').read_text())
    permitted=set(historical_training_ids(old_split))
    historical_used=set(dev['run_metadata'].loc[dev['run_metadata'].cohort=='m3_permitted_train','run_id'])
    if historical_used!=permitted:raise ValueError('Historical held-out runs entered new development')
    dgroups=set(dev['run_metadata'].physical_group_id.dropna())
    tgroups=set(locked['run_metadata'].physical_group_id.dropna())
    if dgroups&tgroups or set(dev['run_metadata'].run_id)&set(locked['run_metadata'].run_id):raise ValueError('Locked cohort leak')
    assigned=dev['run_metadata'].assign(split=dev['run_metadata'].run_id.map(split['assignments']))
    if assigned.groupby('physical_group_id').split.nunique().max()>1:raise ValueError('Development config leak')
    for f in frozen['cv_folds']:
        if set(f['fit_groups'])&set(f['held_groups']):raise ValueError('CV physical group leak')
        if any(split['assignments'][r]!='train' for r in f['fit_runs']+f['held_runs']):raise ValueError('CV used validation/test')
    saved=pd.read_parquet(output/'predictions.parquet')
    rows=pd.read_parquet(output/'event_run_metrics.parquet')
    max_difference=0.;checked=0
    checked_preprocessing=set()
    for c in frozen['candidates']:
        artifact=joblib.load(c['artifact_path'])
        if c['origin'].startswith('m4b_refit') or c['origin'].startswith('m4a_rule_score_reselected'):
            if any(split['assignments'][r]!='train' for r in artifact['train_runs']):raise ValueError('Artifact trained on held-out run')
            if c['artifact_path'] not in checked_preprocessing:
                eligible=exact_join(dev['temporal_features'],dev['event_labels'],c['horizon_s'])
                training=eligible.loc[eligible.run_id.map(split['assignments'])=='train']
                if artifact['train_runs']!=sorted(training.run_id.unique()):raise ValueError('Training cohort changed')
                if c['model']!='rule':
                    dictionary=json.loads((data/'development/feature_dictionary.json').read_text())
                    if c['columns']!=feature_sets(dictionary)[c['feature_set']]:raise ValueError('Unsafe feature selection')
                    numeric=[col for col in c['columns'] if col!='packing_family']
                    pre=artifact['pipeline']['preprocess']
                    np.testing.assert_allclose(pre.named_transformers_['numeric'].mean_,training[numeric].mean(),atol=1e-12,rtol=1e-12)
                    if 'packing_family' in c['columns'] and set(pre.named_transformers_['packing'].categories_[0])!=set(training.packing_family):
                        raise ValueError('Encoder learned outside training')
                    if not np.isclose(artifact['prevalence'],run_weights(training)[1]):raise ValueError('Training prevalence changed')
                checked_preprocessing.add(c['artifact_path'])
        for scope,tables in [('development_validation',dev),('locked',locked)]:
            s=saved.loc[(saved.candidate_id==c['candidate_id'])&(saved.scope==scope)].sort_values(['run_id','frame_index'])
            f=tables['temporal_features'].loc[tables['temporal_features'].run_id.isin(s.run_id)].sort_values(['run_id','frame_index'])
            if list(zip(s.run_id,s.frame_index,s.time_s))!=list(zip(f.run_id,f.frame_index,f.time_s)):raise ValueError('Prediction alignment changed')
            max_difference=max(max_difference,verify_prediction_replay(s.probability,predict(artifact,f),c['threshold']))
            for run_id,sequence in s.groupby('run_id'):
                observed=f.loc[f.run_id==run_id]
                alerts=online_warnings(observed.time_s,sequence.probability,observed.remaining_count,c['threshold'],c['policy'])
                stored=rows.loc[(rows.scope==scope)&(rows.candidate_id==c['candidate_id'])&(rows.run_id==run_id)&(rows.replay=='online')].iloc[0]
                if alerts!=json.loads(stored.alerts_json):raise ValueError('Online episode replay changed')
                cut=max(2,len(sequence)//2)
                prefix=online_warnings(observed.time_s.to_numpy()[:cut],sequence.probability.to_numpy()[:cut],
                                       observed.remaining_count.to_numpy()[:cut],c['threshold'],c['policy'])
                if prefix!=[t for t in alerts if t<=observed.time_s.iloc[cut-1]]:raise ValueError('Controller looks into future')
                checked+=1
    m=pd.DataFrame([{k:r.get(k) for k in ('run_id','phase','case_name','packing_family','seed','status','runtime_s','observation_duration_s','continued','flow_state','censored_run')} |
                    dict(events=len(r.get('events',[])),max_overlap_over_radius=r.get('checks',{}).get('max_overlap_over_radius')) for r in records])
    m.to_csv(report/'campaign_runs.csv',index=False,lineterminator='\n')
    for scope,tables in [('development',dev),('locked',locked)]:
        table=tables['run_metadata'].loc[tables['run_metadata'].status=='ok']
        groups=table.groupby(['physical_group_id','outlet_ratio','friction','wall_friction','wall_angle_deg']).agg(
            independent_runs=('run_id','size'),first_events=('confirmed_event_count','sum'),censored_runs=('censored_run','sum')).reset_index()
        groups.to_csv(report/(scope+'_configuration_events.csv'),index=False,lineterminator='\n')
    result=dict(status='pass',historical_files_unchanged=len(historical),solver_attempts=len(records),
                successful=len(valid),failed=len(records)-len(valid),new_events=sum(bool(r.get('events')) for r in valid),
                censored_runs=sum(bool(r.get('censored_run')) for r in valid),
                continued_runs=sum(bool(r.get('continued')) for r in valid),
                maximum_overlap_over_radius=max(r['checks']['max_overlap_over_radius'] for r in valid),
                locked_events=int(locked['run_metadata'].confirmed_event_count.sum()),
                locked_physical_configurations=len(tgroups),historical_train_runs_used=len(permitted),
                duplicate_trajectories=0,duplicate_initial_states=0,oracle_replay_gating=False,
                causal_full_run_replay_checks=checked,max_prediction_replay_absolute_difference=max_difference,
                audited_new_preprocessing_artifacts=len(checked_preprocessing),
                real_prefix_censoring_checks=real_censor_checks,
                initial_packing_reproducibility_checks=len(valid),raw_nonfinite_values_excluding_uncrossed_sentinels=0,
                summed_worker_wall_s=float(sum(r['runtime_s'] for r in records)),
                phase_elapsed_s={phase:json.loads((root/'manifests'/(phase+'_campaign.json')).read_text())['phase_wall_s']
                                 for phase in ('pilot','adaptive','locked')})
    write_json(report/'audit.json',result)
    print(json.dumps(result,indent=2))
    return result
