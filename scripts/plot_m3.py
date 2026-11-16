"""Scientific M3 diagnostics from genuine DEM data; publish only compact summaries."""
import argparse,csv,json,shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import EllipseCollection,LineCollection
from pharmaflow.run import load_run
from pharmaflow.config import HopperConfig
from pharmaflow.geometry import hopper_walls
from pharmaflow.m3_dataset import run_records

plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':160})


def save(fig,path):
    fig.tight_layout();fig.savefig(path,bbox_inches='tight');plt.close(fig)


def csv_file(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/simulated/m3'))
    p.add_argument('--processed',type=Path,default=Path('data/processed/m3'))
    p.add_argument('--output',type=Path,default=Path('docs/results/m3'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    quality=json.loads((a.processed/'quality_report.json').read_text())
    manifest=json.loads((a.processed/'dataset_manifest.json').read_text())
    runs=pd.read_parquet(a.processed/'run_metadata.parquet');labels=pd.read_parquet(a.processed/'event_labels.parquet')
    events=pd.read_parquet(a.processed/'events.parquet');sensitivity=pd.read_parquet(a.processed/'persistence_sensitivity.parquet')
    valid=runs[runs.status=='ok'];records={r['run_id']:r for r in run_records(a.root)}
    for name in ('dataset_manifest.json','split_manifest.json','feature_dictionary.json','quality_report.json'):
        shutil.copyfile(a.processed/name,a.output/name)
    columns=['run_id','configuration_id','physical_group_id','phase','seed','packing_family','status','flow_state','censored_run',
             'confirmed_event_count','outlet_ratio','friction','wall_friction','wall_angle_deg','initial_particle_count','observation_duration_s',
             'dt_s','normal_stiffness_n_m','max_overlap_over_radius','runtime_s','initial_state_sha256','npz_sha256']
    runs[columns].to_csv(a.output/'run_summary.csv',index=False,lineterminator='\n')
    events.to_csv(a.output/'first_events.csv',index=False,lineterminator='\n')
    sensitivity.to_csv(a.output/'persistence_sensitivity.csv',index=False,lineterminator='\n')
    preparation=json.loads(Path('outputs/metrics/m3/stiffness/results.json').read_text());rows=[]
    for r in preparation:
        z,_=load_run(Path('outputs/metrics/m3/stiffness')/r['run_id']/'trajectory.npz')
        energy=sum(z['diag_'+key] for key in ('kinetic_j','rotation_j','gravity_j','normal_spring_j','tangent_spring_j'))
        corrected=energy+z['diag_exported_j']
        rows.append(dict(case=r['case'],outlet_ratio=r['config']['outlet_width_m']/.004,
                         kn=r['config']['normal_stiffness_n_m'],kt=r['config']['tangential_stiffness_n_m'],dt_s=r['config']['dt_s'],
                         initial_state_sha256=r['initial_state_sha256'],peak_overlap_radius=r['accuracy']['max_overlap_over_radius'],
                         p95_overlap_upper=r['physics']['overlap_quantile_upper_bounds']['0.95'],discharged=r['metrics']['total_discharged'],
                         arch_last_02s=r['metrics']['arch']['observed_stationary_spanning_arch'],
                         energy_initial_j=float(corrected[0]),energy_final_with_advection_j=float(corrected[-1]),
                         normal_dashpot_loss_j=r['physics']['normal_damping_loss_j'],runtime_s=r['runtime_s']))
    csv_file(a.output/'stiffness.csv',rows)
    fig,axes=plt.subplots(2,2,figsize=(8,6))
    for ratio in (2,3):
        values=sorted([r for r in rows if r['outlet_ratio']==ratio],key=lambda r:r['kn'])
        assert len({r['initial_state_sha256'] for r in values})==1
        x=[r['kn'] for r in values]
        for ax,key,label in ((axes[0,0],'peak_overlap_radius','maximum overlap / radius'),(axes[0,1],'discharged','discharged [particles]'),
                             (axes[1,0],'energy_final_with_advection_j','final mechanical + advected energy [J]'),(axes[1,1],'runtime_s','runtime [s]')):
            ax.plot(x,[r[key] for r in values],'o-',label=f'D/d={ratio}');ax.set(xlabel='normal stiffness [N/m]',ylabel=label);ax.legend(fontsize=7)
    save(fig,a.output/'stiffness_sensitivity.png')
    fig,axes=plt.subplots(1,3,figsize=(11,3.5))
    colors=np.where(valid.confirmed_event_count>0,'#c35b27','#247b91')
    axes[0].scatter(valid.outlet_ratio,valid.friction,c=colors,s=35,alpha=.7)
    axes[0].set(xlabel='outlet / diameter',ylabel='particle friction')
    axes[1].scatter(valid.wall_angle_deg,valid.initial_particle_count,c=colors,s=35,alpha=.7)
    axes[1].set(xlabel='wall angle from vertical [deg]',ylabel='initial particle count')
    for family,g in valid.groupby('packing_family'):
        axes[2].scatter(g.outlet_ratio,g.confirmed_event_count+.03*(list(sorted(valid.packing_family.unique())).index(family)-1),label=family,s=25)
    axes[2].set(xlabel='outlet / diameter',ylabel='confirmed first event [0/1]');axes[2].legend(fontsize=7)
    fig.suptitle('Coverage: orange = finite-duration confirmed event; blue = no confirmed event')
    save(fig,a.output/'parameter_coverage.png')
    fig,axes=plt.subplots(1,3,figsize=(11,3.4))
    if len(events):axes[0].hist(events.onset_time_s,bins=8,label='onset',alpha=.65);axes[0].hist(events.confirmation_time_s,bins=8,label='confirmation',alpha=.55)
    axes[0].set(xlabel='time [s]',ylabel='independent first events');axes[0].legend(fontsize=7)
    from matplotlib.ticker import MaxNLocator
    axes[0].yaxis.set_major_locator(MaxNLocator(integer=True))
    counts=sensitivity.groupby('persistence_s').event_count.sum()
    axes[1].bar(counts.index.astype(str),counts.values,color='#247b91');axes[1].set(xlabel='persistence requirement [s]',ylabel='confirmed first events')
    for index,(h,g) in enumerate(labels.groupby('horizon_s')):
        e=g[g.label_status=='eligible'];positive=int((e.target==1).sum());negative=int((e.target==0).sum())
        axes[2].bar(index,negative,label='negative' if index==0 else None,color='#247b91')
        axes[2].bar(index,positive,bottom=negative,label='positive' if index==0 else None,color='#c35b27')
    axes[2].set(xticks=[0,1],xticklabels=['0.05','0.10'],xlabel='prediction horizon [s]',ylabel='eligible examples');axes[2].legend(fontsize=7)
    save(fig,a.output/'events_and_balance.png')
    selected=[]
    event_candidates=valid[valid.confirmed_event_count>0].copy()
    event_candidates['distance_to_transition']=abs(event_candidates.outlet_ratio-2.5)
    flow_candidates=valid[valid.flow_state=='completed_discharge'].copy()
    flow_candidates['distance_to_transition']=abs(flow_candidates.outlet_ratio-2.5)
    event_ids=list(event_candidates.sort_values('distance_to_transition').run_id)
    flow_ids=list(flow_candidates.sort_values('distance_to_transition').run_id)
    for pool in (event_ids,flow_ids):
        selected.extend(pool[:2])
    if not selected:raise RuntimeError('no representative runs')
    fig,axes=plt.subplots(2,1,figsize=(8,5),sharex=True)
    for run_id in selected:
        r=records[run_id];z,_=load_run(a.root/r['phase']/run_id/'trajectory.npz')
        label=f"{r['case_name']}, {r['packing_family']}"
        axes[0].plot(z['time_s'],z['discharged_count'],label=label,lw=1)
        edges=np.arange(0,z['time_s'][-1]+.01,.02)
        cross=z['crossing_time_s'][np.isfinite(z['crossing_time_s'])]
        rate=np.histogram(cross,edges)[0]/np.diff(edges)
        axes[1].step((edges[:-1]+edges[1:])/2,rate,where='mid',lw=1)
    axes[0].set(ylabel='unique crossings [particles]');axes[0].legend(fontsize=6,ncol=2)
    axes[1].set(xlabel='time [s]',ylabel='flow rate [particles/s]')
    save(fig,a.output/'flow_histories.png')
    ordered=list(valid.sort_values(['confirmed_event_count','outlet_ratio'],ascending=[False,True]).run_id)
    fig,ax=plt.subplots(figsize=(9,max(4,len(ordered)*.18)))
    for i,run_id in enumerate(ordered):
        r=records[run_id];ax.plot([0,r['observation_duration_s']],[i,i],color='#9babb3',lw=2)
        ev=events[events.run_id==run_id]
        if len(ev):
            onset=float(ev.iloc[0].onset_time_s);confirmation=float(ev.iloc[0].confirmation_time_s)
            ax.plot([onset,confirmation],[i,i],color='#c35b27',lw=5)
            ax.scatter([onset,confirmation],[i,i],c=['#ad2525','#197a57'],s=16,zorder=4)
        ax.scatter(r['observation_duration_s'],i,marker='>' if r['censored_run'] else '|',s=22,color='black')
    ax.set(yticks=range(len(ordered)),yticklabels=[f"{records[x]['case_name']} / {records[x]['seed']}" for x in ordered],xlabel='time [s]',title='First-event onset (red) and confirmation (green); > = right-censored endpoint')
    ax.tick_params(axis='y',labelsize=6)
    save(fig,a.output/'onset_timelines.png')
    representative=event_ids[0] if event_ids else flow_ids[0]
    r=records[representative];z,m=load_run(a.root/r['phase']/representative/'trajectory.npz');c=HopperConfig(**r['config'])
    ev=events[events.run_id==representative]
    onset=float(ev.iloc[0].onset_time_s) if len(ev) else .2
    confirm=float(ev.iloc[0].confirmation_time_s) if len(ev) else .6
    requested=[max(.05,onset-.10),max(.05,onset-.05),onset,confirm]
    speed=np.linalg.norm(z['velocity_m_s'],axis=2);scale=max(float(np.quantile(speed[z['active']],.99)),.05)
    fig,axes=plt.subplots(1,4,figsize=(10,4),sharex=True,sharey=True)
    for ax,t in zip(axes,requested):
        k=int(np.argmin(abs(z['time_s']-t)));position=z['position_m'][k].copy();position[~z['active'][k]]=np.nan
        disks=EllipseCollection(2*z['radius_m'],2*z['radius_m'],np.zeros(c.n_particles),units='xy',offsets=position,
                                transOffset=ax.transData,cmap='viridis',clim=(0,scale),edgecolors='black',linewidths=.2)
        disks.set_array(speed[k]);ax.add_collection(disks);ax.add_collection(LineCollection(hopper_walls(c,z['time_s'][k]),colors='black'))
        ax.set(xlim=(-.05,.05),ylim=(-.012,.075),aspect='equal',xticks=[-.04,0,.04],xlabel='x [m]',title=f't={z["time_s"][k]:.3f} s')
        ax.tick_params(axis='x',labelsize=8)
    axes[0].set_ylabel('height [m]');fig.suptitle('Actual DEM particles: pre-onset → onset → future confirmation; speed [m/s]',fontsize=10)
    fig.subplots_adjust(top=.78,bottom=.17,left=.06,right=.88,wspace=.25);bar=fig.add_axes([.92,.22,.014,.5]);fig.colorbar(disks,cax=bar,label='speed [m/s], q99 clipped')
    fig.savefig(a.output/'particle_event_sequence.png',bbox_inches='tight');plt.close(fig)
    summary=dict(attempts_including_stiffness=len(preparation)+manifest['attempted_dataset_runs'],
                 successful_including_stiffness=sum(r['status']=='ok' for r in preparation)+manifest['successful_runs'],
                 failed_including_stiffness=sum(r['status']!='ok' for r in preparation)+manifest['failed_runs'],
                 dataset_runs=manifest['attempted_dataset_runs'],confirmed_first_events=manifest['confirmed_events'],
                 right_censored_dataset_runs=manifest['censored_runs'],feature_rows=manifest['feature_rows'],feature_columns=manifest['feature_columns'],
                 label_rows=manifest['label_rows'],horizon_statistics=quality['horizon_statistics'],
                 measured_worker_wall_s=sum(r['runtime_s'] for r in preparation)+quality['total_measured_runtime_s'],
                 raw_bytes=quality['total_raw_bytes'],processed_bytes=quality['total_processed_bytes'],
                 selected_numerics=json.loads(Path('configs/m3/numerical_selection.json').read_text()),
                 parameter_ranges={k:[float(valid[k].min()),float(valid[k].max())] for k in ('outlet_ratio','friction','wall_friction','wall_angle_deg','initial_particle_count')},
                 packing_families=sorted(valid.packing_family.unique()),seeds=sorted(int(s) for s in valid.seed.unique()),
                 maximum_dataset_overlap_radius=quality['max_overlap_over_radius'],
                 persistence_sensitivity={str(k):int(v) for k,v in counts.items()},
                 stage_elapsed_estimates_s={})
    from datetime import datetime,timedelta
    for phase in ('pilot','production'):
        rs=[r for r in records.values() if r['phase']==phase]
        if rs:
            end=[datetime.fromisoformat(r['created_utc']) for r in rs]
            start=[e-timedelta(seconds=r['runtime_s']) for e,r in zip(end,rs)]
            summary['stage_elapsed_estimates_s'][phase]=(max(end)-min(start)).total_seconds()
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
