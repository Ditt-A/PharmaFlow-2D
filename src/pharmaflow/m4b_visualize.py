"""Saved DEM particles/contacts synchronized with frozen online scores and truth annotations."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import EllipseCollection, LineCollection
from matplotlib.animation import FuncAnimation, PillowWriter
from .config import HopperConfig
from .geometry import hopper_walls
from .run import load_run
from .m4b_data import load_tables
from .m4b_evaluation import verify_freeze
from .m4_data import write_json


def render_scene(run_id, tables, scores, runs, frozen, path, max_frames=70, dpi=90):
    meta = tables['run_metadata'].set_index('run_id').loc[run_id]
    arrays, _ = load_run(meta.trajectory_path)
    c = HopperConfig(**json.loads(meta.config_json))
    ids = frozen['selected']['0.1']
    f = tables['temporal_features'].loc[tables['temporal_features'].run_id == run_id].sort_values('frame_index')
    times = arrays['time_s']
    fig = plt.figure(figsize=(9, 5))
    grid = fig.add_gridspec(2, 2, width_ratios=[1, 1.5])
    ax, flux, risk = fig.add_subplot(grid[:,0]), fig.add_subplot(grid[0,1]), fig.add_subplot(grid[1,1])
    speed = np.linalg.norm(arrays['velocity_m_s'], axis=2)
    scale = max(.05, float(np.quantile(speed[arrays['active']], .99)))
    disks = EllipseCollection(2*arrays['radius_m'], 2*arrays['radius_m'], np.zeros(c.n_particles),
                              units='xy', offsets=arrays['position_m'][0], transOffset=ax.transData,
                              cmap='viridis', clim=(0, scale), edgecolors='black', linewidths=.3)
    ax.add_collection(disks)
    walls = LineCollection(hopper_walls(c, 0), colors='black', linewidths=1.5)
    contacts = LineCollection([], colors='#d34a26', linewidths=.8)
    ax.add_collection(walls)
    ax.add_collection(contacts)
    ax.set(xlim=(-c.width_m*.55,c.width_m*.55), ylim=(-.015,.105), xlabel='x [m]', ylabel='y [m]', aspect='equal')
    fig.colorbar(disks, ax=ax, label='Speed [m/s]', fraction=.04)
    flux.plot(times, arrays['discharged_count'], color='#2878a0', label='DEM crossings')
    flux.set(xlabel='Simulation time [s]', ylabel='Discharged particles', ylim=(0,c.n_particles+1))
    flux2 = flux.twinx()
    flux2.plot(f.time_s, f.flow_rate_50ms_particles_s, color='.65', alpha=.6, label='50ms flux')
    flux2.set(ylabel='Flux [particles/s]', ylim=(0,max(1,float(f.flow_rate_50ms_particles_s.max())*1.1)))
    risk_artists=[]
    for identifier,color,label in [(ids['ml'],'#6a4295','ML (frozen)'),(ids['physics_rule'],'#c27b18','Rule (frozen)')]:
        s = scores.loc[(scores.candidate_id == identifier)&(scores.run_id == run_id)].sort_values('frame_index')
        r = runs.loc[(runs.candidate_id == identifier)&(runs.run_id == run_id)&(runs.replay == 'online')].iloc[0]
        line,=risk.plot([],[],color=color,label=label)
        alert_times = json.loads(r.alerts_json)
        warnings=risk.scatter([],[],marker='v',s=16,color=color)
        false = json.loads(r.false_alerts_json)
        false_marks=risk.scatter([],[],marker='x',s=20,color='#b42526')
        risk_artists.append((line,warnings,false_marks,s,np.asarray(alert_times),np.asarray(false),.95 if label.startswith('ML') else .85))
    onsets = json.loads(meta.event_onsets_json)
    confirmations = json.loads(meta.event_confirmations_json)
    clip_end=max(.8,confirmations[0]+.05) if confirmations else .8
    crossings=np.sort(arrays['crossing_time_s'][np.isfinite(arrays['crossing_time_s'])])
    if not confirmations and len(crossings)>1:
        gap=int(np.argmax(np.diff(crossings)))
        clip_end=max(clip_end,float(crossings[gap+1])+.10)
    for chart in (flux,risk):
        if onsets:
            chart.axvline(onsets[0],color='#bd382d',ls='--',lw=1,label='Onset (posthoc)')
            chart.axvline(confirmations[0],color='#278050',ls='-.',lw=1,label='Confirmation (posthoc)')
        chart.set_xlim(0,min(float(times[-1]),clip_end))
    risk.set(xlabel='Simulation time [s]',ylabel='Online warning score',ylim=(0,1.06))
    risk.legend(fontsize=6,loc='lower right')
    cursors=[chart.axvline(0,color='black',lw=.7) for chart in (flux,risk)]
    stamp=ax.text(.02,.98,'',va='top',transform=ax.transAxes,fontsize=7)
    end=min(len(times)-1,int(np.searchsorted(times,flux.get_xlim()[1])))
    frames=np.unique(np.linspace(0,end,min(max_frames,end+1),dtype=int))
    def update(i):
        positions=arrays['position_m'][i].copy()
        positions[~arrays['active'][i]]=np.nan
        disks.set_offsets(positions)
        disks.set_array(speed[i])
        walls.set_segments(hopper_walls(c,float(times[i])))
        graph=arrays['contact_graph'][i]
        a,b=np.where(np.triu(graph[:c.n_particles,:c.n_particles],1))
        segments=list(np.stack((positions[a],positions[b]),axis=1)) if len(a) else []
        for wall in (0,1):
            segment=hopper_walls(c,float(times[i]))[wall]
            direction=segment[1]-segment[0]
            for particle in np.where(graph[:c.n_particles,c.n_particles+wall])[0]:
                fraction=np.clip(np.dot(positions[particle]-segment[0],direction)/np.dot(direction,direction),0,1)
                segments.append(np.array([positions[particle],segment[0]+fraction*direction]))
        contacts.set_segments(segments)
        for line,warnings,false_marks,s,alerts,false,level in risk_artists:
            past=s.time_s<=times[i]+1e-12
            line.set_data(s.loc[past,'time_s'],s.loc[past,'probability'])
            for artist,values in ((warnings,alerts),(false_marks,false)):
                values=values[values<=times[i]+1e-12]
                artist.set_offsets(np.column_stack((values,np.full(len(values),level))))
        for cursor in cursors:cursor.set_xdata([times[i],times[i]])
        stamp.set_text(f't={times[i]:.3f}s\nNear contacts: {len(a)}')
        return disks,walls,contacts,stamp,*cursors
    fig.suptitle('Actual 2D DEM | online forecasts; onset/confirmation and red X are posthoc',fontsize=9)
    fig.tight_layout()
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    animation=FuncAnimation(fig,update,frames=frames,interval=80,blit=False)
    animation.save(path,writer=PillowWriter(fps=12),dpi=dpi)
    update(frames[min(len(frames)-1,len(frames)//2)])
    fig.savefig(path.with_suffix('.png'),dpi=130)
    plt.close(fig)
    return dict(clip_start_s=0.,clip_end_s=float(times[end]),full_observation_s=float(times[-1]),frames=len(frames),fps=12)


def visualize(root='data/simulated/m4b', data='data/processed/m4b', output='outputs/metrics/m4b', report='docs/results/m4b'):
    root,data,output,report=map(Path,(root,data,output,report))
    frozen=verify_freeze(root,output)
    scores=pd.read_parquet(output/'predictions.parquet')
    runs=pd.read_parquet(output/'event_run_metrics.parquet')
    tables=load_tables(data/'locked')
    valid=tables['run_metadata'].loc[tables['run_metadata'].status=='ok'].sort_values('run_id')
    metrics=pd.read_csv(report/'metrics.csv')
    fig,axes=plt.subplots(1,3,figsize=(12,3.6),constrained_layout=True)
    configs=valid.groupby(['physical_group_id','outlet_ratio'],sort=True).agg(runs=('run_id','size'),events=('confirmed_event_count','sum')).reset_index()
    x=np.arange(len(configs))
    axes[0].bar(x,configs.runs,color='.8',label='Valid runs')
    axes[0].bar(x,configs.events,color='#b85743',label='First events')
    axes[0].set(xticks=x,xticklabels=[f'D/d={v:g}' for v in configs.outlet_ratio],ylabel='Independent runs',title='Locked physical configurations')
    axes[0].legend(fontsize=7)
    selected_ids={i for h in frozen['selected'].values() for i in h.values()}
    m=metrics.loc[(metrics.scope=='locked')&(metrics.replay=='online')&metrics.candidate_id.isin(selected_ids)].sort_values(['horizon_s','model'])
    labels=[f'H={r.horizon_s:g}\n{r.model}' for r in m.itertuples()]
    axes[1].bar(np.arange(len(m)),m.useful_event_recall,color='#4b7d96')
    axes[1].set(xticks=np.arange(len(m)),xticklabels=labels,ylim=(0,1.05),ylabel='Useful event recall',title='Frozen selections, lead >=20ms')
    axes[2].bar(np.arange(len(m)),m.false_per_operating_s,color='#bd765b')
    axes[2].set(xticks=np.arange(len(m)),xticklabels=labels,ylabel='False forecasts / operating second',title='Full chronological operation')
    fig.savefig(report/'locked_summary.png',dpi=140)
    plt.close(fig)
    # Representative selection is descriptive after evaluation, never model selection.
    events=valid.loc[valid.confirmed_event_count>0]
    non_events=valid.loc[valid.confirmed_event_count==0].sort_values('temporary_gap_count',ascending=False)
    reps=[]
    for kind,group in [('event',events),('resumed_or_completed',non_events)]:
        if len(group):
            rid=group.iloc[0].run_id
            path=Path('outputs/animations/m4b')/(kind+'.gif')
            timing=render_scene(rid,tables,scores.loc[scores.scope=='locked'],runs.loc[runs.scope=='locked'],frozen,path)
            reps.append(dict(kind=kind,run_id=rid,gif=str(path),**timing))
    if reps:
        render_scene(reps[0]['run_id'],tables,scores.loc[scores.scope=='locked'],runs.loc[runs.scope=='locked'],
                     frozen,report/'demo.gif',max_frames=42,dpi=65)
    write_json(report/'visualization_manifest.json',dict(origin='Actual new locked-cohort DEM arrays',representatives=reps,
               scores='Full chronological online forecasts; future truth used only as labeled posthoc annotations',
               colors='SI speed; per-scene active-particle q99 used for display only, never model preprocessing'))
    print('M4B figures and real DEM animations generated')
