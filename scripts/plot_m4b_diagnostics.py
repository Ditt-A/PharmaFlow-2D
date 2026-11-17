"""Posthoc calibration and a real later-resumed crossing gap; never select/refit models."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pharmaflow.m4b_data import load_tables
from pharmaflow.m4b_evaluation import verify_freeze
from pharmaflow.run import load_run
from pharmaflow.m4_data import write_json,KEYS


if __name__=='__main__':
    report=Path('docs/results/m4b');output=Path('outputs/metrics/m4b')
    assert (output/'locked_evaluation_receipt.json').exists()
    frozen=verify_freeze()
    tables=load_tables('data/processed/m4b/locked')
    scores=pd.read_parquet(output/'predictions.parquet')
    scores=scores.loc[scores.scope=='locked']
    runs=pd.read_parquet(output/'event_run_metrics.parquet')
    runs=runs.loc[(runs.scope=='locked')&(runs.replay=='online')]
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    for ax,h in zip(axes,(.1,.05)):
        truth=tables['event_labels'].loc[(tables['event_labels'].horizon_s==h)&
                                        (tables['event_labels'].label_status=='eligible'),KEYS+['target']]
        for kind,color in [('ml','#68439a'),('physics_rule','#bd7d24')]:
            identifier=frozen['selected'][str(h)][kind]
            p=scores.loc[scores.candidate_id==identifier].merge(truth,on=KEYS,validate='one_to_one')
            bins=np.minimum((p.probability*10).astype(int),9)
            curve=p.assign(bin=bins).groupby('bin').agg(predicted=('probability','mean'),observed=('target','mean'))
            ax.plot(curve.predicted,curve.observed,'o-',label=kind,color=color)
        ax.plot([0,1],[0,1],':',color='.5')
        ax.set(title=f'H={h:.2f}s; eligible frames only',xlabel='Mean warning score',ylabel='Observed positive fraction',xlim=(0,1),ylim=(0,1))
        ax.legend()
    fig.savefig(report/'calibration.png',dpi=140);plt.close(fig)
    meta=tables['run_metadata'].loc[tables['run_metadata'].temporary_gap_count>0].sort_values('maximum_resumed_gap_s',ascending=False)
    if len(meta):
        r=meta.iloc[0];arrays,_=load_run(r.trajectory_path)
        crossings=np.sort(arrays['crossing_time_s'][np.isfinite(arrays['crossing_time_s'])])
        gap=int(np.argmax(np.diff(crossings)));start,end=map(float,crossings[gap:gap+2])
        f=tables['temporal_features'].loc[tables['temporal_features'].run_id==r.run_id].sort_values('frame_index')
        fig,(ax1,ax2)=plt.subplots(2,1,figsize=(9,5),sharex=True,constrained_layout=True)
        ax1.plot(arrays['time_s'],arrays['discharged_count'],label='Actual DEM crossings',color='#2c7591')
        for ax in (ax1,ax2):ax.axvspan(start,end,alpha=.2,color='#6f9eb1',label='Gap with later resumption (posthoc)')
        ids=frozen['selected']['0.1']
        for kind,color in [('ml','#68439a'),('physics_rule','#bd7d24')]:
            identifier=ids[kind]
            p=scores.loc[(scores.run_id==r.run_id)&(scores.candidate_id==identifier)].sort_values('frame_index')
            row=runs.loc[(runs.run_id==r.run_id)&(runs.candidate_id==identifier)].iloc[0]
            ax2.plot(p.time_s,p.probability,label=kind,color=color)
            alerts=json.loads(row.alerts_json);false=json.loads(row.false_alerts_json)
            ax2.scatter(alerts,np.full(len(alerts),.95 if kind=='ml' else .85),marker='v',color=color)
            ax2.scatter(false,np.full(len(false),.95 if kind=='ml' else .85),marker='x',color='red')
        onset=json.loads(r.event_onsets_json);confirmation=json.loads(r.event_confirmations_json)
        for ax in (ax1,ax2):
            if onset:ax.axvline(onset[0],color='#bd342e',ls='--',label='Onset (posthoc)')
            if confirmation:ax.axvline(confirmation[0],color='#268154',ls='-.',label='Confirmation (posthoc)')
            ax.legend(fontsize=7,loc='best')
        ax1.set(ylabel='Cumulative discharged particles',title=f'Real resumed flow: {r.run_id}')
        ax2.set(xlabel='Simulation time [s]',ylabel='Frozen online warning score',ylim=(0,1.05),xlim=(.04,max(.8,end+.1)))
        fig.savefig(report/'resumed_flow_timeline.png',dpi=140);plt.close(fig)
        write_json(report/'resumed_flow_example.json',dict(run_id=r.run_id,gap_start_s=start,next_crossing_s=end,
                   resumed_gap_s=end-start,confirmed_first_onset_s=onset[0] if onset else None,
                   interpretation='Gap end and event annotations are posthoc; all warnings were emitted from full chronological observations.'))
    print('Supplementary diagnostics generated from saved frozen predictions')
