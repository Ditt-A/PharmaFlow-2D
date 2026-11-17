"""Compact post-evaluation data/cost summaries; no fitting or policy selection."""
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from pharmaflow.m4_data import write_json,digest
from pharmaflow.m4b_data import load_tables,verify_release
from pharmaflow.run import load_run
from pharmaflow.m3_events import spans


def summarize(root,data,output,report):
    root,data,output,report=map(Path,(root,data,output,report))
    audit=json.loads((report/'audit.json').read_text())
    evaluation=json.loads((report/'summary.json').read_text())
    frozen=json.loads((output/'model_and_policy_freeze.json').read_text())
    dev,locked=load_tables(data/'development'),load_tables(data/'locked')
    split=json.loads((data/'development/split_manifest.json').read_text())['assignments']
    rows=[]
    for scope,tables in [('development',dev),('locked',locked)]:
        meta=tables['run_metadata'].loc[tables['run_metadata'].status=='ok'].copy()
        meta['split']='locked' if scope=='locked' else meta.run_id.map(split)
        for name,group in meta.groupby('split'):
            lab=tables['event_labels'].loc[tables['event_labels'].run_id.isin(group.run_id)]
            for h,l in lab.groupby('horizon_s'):
                eligible=l.loc[l.label_status=='eligible']
                rows.append(dict(split=name,horizon_s=h,independent_runs=len(group),
                                 physical_configurations=group.physical_group_id.nunique(),
                                 independent_first_events=int(group.confirmed_event_count.sum()),
                                 censored_runs=int(group.censored_run.sum()),eligible_rows=len(eligible),
                                 positive=int((eligible.target==1).sum()),negative=int((eligible.target==0).sum()),
                                 prevalence=float((eligible.target==1).mean()) if len(eligible) else None,
                                 censored_rows=int((l.label_status=='right_censored').sum())))
    pd.DataFrame(rows).to_csv(report/'class_distribution.csv',index=False,lineterminator='\n')
    new=pd.concat([dev['run_metadata'].loc[dev['run_metadata'].cohort=='m4b'],locked['run_metadata']],ignore_index=True)
    valid=new.loc[new.status=='ok']
    sensitivity=pd.concat([pd.read_parquet(data/scope/'persistence_sensitivity.parquet') for scope in ('development','locked')])
    sensitivity.to_csv(report/'persistence_sensitivity.csv',index=False,lineterminator='\n')
    ledger=json.loads((root/'manifests/attempts.json').read_text())['attempts']
    contexts=[]
    for entry in ledger.values():
        r=entry['result']
        if r['status']!='ok' or not r['events']:continue
        event=r['events'][0];arrays,_=load_run(r['trajectory_path'])
        gate=r['config']['gate_open_time_s'];g=int(np.searchsorted(arrays['time_s'],gate-1e-12))
        earliest=gate+r['sample_interval_s']
        contexts.append(dict(run_id=r['run_id'],phase=r['phase'],onset_s=event['onset_time_s'],
                             discharged_at_onset=int(arrays['discharged_count'][event['onset_frame']]),
                             quiet_spanning_snapshot_at_release=bool(spans(arrays['contact_graph'][g]) and arrays['near_max_speed_m_s'][g]<=.003),
                             earliest_two_frame_warning_s=earliest,
                             maximum_possible_lead_s=event['onset_time_s']-earliest,
                             below_20ms_timing_ceiling=event['onset_time_s']-earliest<.02-1e-10,
                             resumed_after_confirmed_arch=event['resumed_crossing_after_event']))
    context=pd.DataFrame(contexts)
    context.to_csv(report/'event_context.csv',index=False,lineterminator='\n')
    result=dict(new_attempts=audit['solver_attempts'],successful=audit['successful'],failed=audit['failed'],
                independent_new_events=audit['new_events'],censored_runs=audit['censored_runs'],
                continuation_runs=audit['continued_runs'],new_physical_configurations=int(valid.physical_group_id.nunique()),
                new_feature_rows=int(sum(len(t['temporal_features'].loc[t['temporal_features'].run_id.isin(valid.run_id)]) for t in (dev,locked))),
                new_label_rows=int(sum(len(t['event_labels'].loc[t['event_labels'].run_id.isin(valid.run_id)]) for t in (dev,locked))),
                resumed_gap_runs=int((valid.temporary_gap_count>0).sum()),
                resumed_after_confirmed_first_arch=int(valid.resumed_after_first_event.eq(True).sum()),
                maximum_resumed_crossing_gap_s=float(valid.maximum_resumed_gap_s.max()),
                events_by_persistence={str(p):int(g.event_count.sum()) for p,g in sensitivity.groupby('persistence_s')},
                locked_event_runs=audit['locked_events'],locked_event_configurations=evaluation['locked_event_configurations'],
                historical_train_runs=audit['historical_train_runs_used'],
                new_ml_fits=len([c for c in frozen['candidates'] if c['origin']=='m4b_refit']),
                total_frozen_evaluation_variants=len(frozen['candidates']),
                maximum_overlap_over_radius=audit['maximum_overlap_over_radius'],
                worker_wall_s=audit['summed_worker_wall_s'],phase_elapsed_s=audit['phase_elapsed_s'],
                training_wall_s=frozen['training_wall_s'],evaluation_wall_s=evaluation['evaluation_wall_s'],
                raw_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                processed_bytes=sum(p.stat().st_size for p in data.rglob('*') if p.is_file()),
                model_bytes=sum(p.stat().st_size for p in Path('outputs/checkpoints/m4b').glob('*.joblib')),
                events_without_prior_discharge=int((context.discharged_at_onset==0).sum()) if len(context) else 0,
                events_below_two_frame_20ms_warning_ceiling=int(context.below_20ms_timing_ceiling.sum()) if len(context) else 0,
                decision=evaluation['decision'],m3_m4a_historical_files_unchanged=audit['historical_files_unchanged'],
                model_freeze_sha256=digest(output/'model_and_policy_freeze.json'))
    write_json(report/'dataset_summary.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='data/simulated/m4b')
    p.add_argument('--data',default='data/processed/m4b')
    p.add_argument('--output',default='outputs/metrics/m4b')
    p.add_argument('--report',default='docs/results/m4b')
    a=p.parse_args();summarize(a.root,a.data,a.output,a.report)
