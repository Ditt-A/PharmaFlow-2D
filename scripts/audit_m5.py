"""Descriptive operational taxonomy and unchanged frozen-monitor replay audit."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from pharmaflow.dashboard_data import historical_registry,load_bundle,save_monitor_cache,prepare_portfolio
from pharmaflow.operational_events import observe_history
from pharmaflow.m4_data import digest,write_json


if __name__=='__main__':
    report=Path('docs/results/m5');report.mkdir(parents=True,exist_ok=True)
    records=historical_registry();summary=[];arches=[];pauses=[];max_difference=0.;replay_checks=0
    old=pd.read_parquet('outputs/metrics/m4b/predictions.parquet',filters=[('candidate_id','in',
       ['m4b_h100_D_full_xgboost','frozen_configuration_holdout_h100_baseline_rule'])])
    old_events=pd.read_parquet('outputs/metrics/m4b/event_run_metrics.parquet')
    reference_ids=['frozen_configuration_holdout_h100_baseline_rule','m4b_h100_D_full_xgboost']
    old_events.loc[(old_events.scope=='locked')&(old_events.replay=='online')&
        (old_events.candidate_id.isin(reference_ids))].to_csv(report/'frozen_locked_event_runs.csv',index=False,lineterminator='\n')
    for r in records:
        if r['source']!='historical':continue
        b=load_bundle(r,require_ml=True);save_monitor_cache(b)
        fields=dict(run_id=r['run_id'],cohort=r['cohort'],phase=r['phase'],membership=r['membership'],
                    configuration_id=r['configuration_id'],packing_family=r['packing_family'],seed=r['seed'])
        outcome=b.annotations
        summary.append(dict(**fields,**{k:v for k,v in outcome.items() if k not in ('arches','interpretation')},
                            temporary_interruptions=len(b.logs['resumptions']),
                            established_flow_observed=bool(b.monitoring.flow_established_now.any()),
                            final_observed_crossings=int(b.arrays['discharged_count'][-1]),
                            rule_notifications=len(b.logs['rule']),ml_notifications=len(b.logs['ml'])))
        arches.extend(dict(**fields,**e) for e in outcome['arches'])
        pauses.extend(dict(**fields,**e) for e in b.logs['resumptions'])
        for kind,key in [('rule','rule_score'),('ml','ml_score')]:
            c=b.specs[kind]
            s=old.loc[(old.run_id==r['run_id'])&(old.candidate_id==c['candidate_id'])].sort_values('frame_index')
            if len(s):
                difference=float(np.max(np.abs(s.probability.to_numpy()-b.monitoring[key].to_numpy())))
                np.testing.assert_allclose(s.probability,b.monitoring[key],rtol=1e-12,atol=1e-12)
                expected=old_events.loc[(old_events.run_id==r['run_id'])&(old_events.candidate_id==c['candidate_id'])&
                                      (old_events.replay=='online')].iloc[0]
                if json.loads(expected.alerts_json)!=[e['time_s'] for e in b.logs[kind]]:
                    raise ValueError('Frozen warning policy replay differs')
                max_difference=max(max_difference,difference);replay_checks+=1
    runs=pd.DataFrame(summary);a=pd.DataFrame(arches);p=pd.DataFrame(pauses)
    runs.to_csv(report/'operational_runs.csv',index=False,lineterminator='\n')
    a.to_csv(report/'arch_taxonomy.csv',index=False,lineterminator='\n')
    p.to_csv(report/'temporary_interruptions.csv',index=False,lineterminator='\n')
    a.groupby(['cohort','prior_observed_crossings']).agg(events=('run_id','size'),
        established_flow_events=('established_flow_interruption','sum')).reset_index().to_csv(
            report/'counts_by_prior_crossings.csv',index=False,lineterminator='\n')
    for key in ('configuration_id','packing_family','cohort'):
        table=runs.groupby(['cohort',key] if key!='cohort' else key).agg(runs=('run_id','size'),
            startup=('startup_blockage','sum'),post_discharge=('post_discharge_arch','sum'),
            established_flow_arch=('established_flow_arch','sum'),temporary_episodes=('temporary_interruptions','sum'),
            completed=('completed_discharge','sum'),unresolved=('unresolved_or_censored','sum')).reset_index()
        table.to_csv(report/('counts_by_'+key+'.csv'),index=False,lineterminator='\n')
    locked=runs.loc[runs.membership=='locked']
    result=dict(version='operational-observation-v1',historical_runs=len(runs),
        confirmed_first_arches=len(a),startup=int(runs.startup_blockage.sum()),post_discharge=int(runs.post_discharge_arch.sum()),
        established_flow_arches=int(runs.established_flow_arch.sum()),temporary_episodes=len(p),
        temporary_runs=int((runs.temporary_interruptions>0).sum()),completed=int(runs.completed_discharge.sum()),
        unresolved=int(runs.unresolved_or_censored.sum()),locked_established_flow_arches=int(locked.established_flow_arch.sum()),
        frozen_replay_checks=replay_checks,max_frozen_score_difference=max_difference,
        historical_labels_modified=False,model_fitting=False,
        limitation='Established-flow arches are a subset of post-discharge arches; temporary/completed outcomes may overlap.')
    write_json(report/'taxonomy_summary.json',result)
    selected=dict(continuous=runs.loc[(runs.completed_discharge)&(runs.temporary_interruptions==0)&
                    (runs.startup_blockage==0)&(runs.post_discharge_arch==0)].iloc[0].run_id,
                  startup=runs.loc[runs.startup_blockage>0].iloc[0].run_id,
                  resumed=runs.loc[runs.temporary_interruptions>0].iloc[0].run_id)
    prepare_portfolio(records,selected)
    write_json(report/'representative_scenes.json',dict(scenes=selected,origin='Genuine existing M3/M4B DEM arrays',new_simulations=0))
    print(json.dumps(result,indent=2));print('SCENES',selected)
