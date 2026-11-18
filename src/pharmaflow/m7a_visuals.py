"""Headless actual-state fixed-grain views; no integration or manufactured motion."""
from io import BytesIO
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.colors import Normalize
from PIL import Image
from .config import HopperConfig
from .fixed_grain import flat_floor_walls
from .m7a_simulation import LABEL


def frame_data(arrays,index):
    if not isinstance(index,(int,np.integer)) or not 0<=index<len(arrays['time_s']):raise ValueError('Invalid stored frame')
    active=arrays['active'][index];positions=arrays['position_m'][index,active].copy()
    radii=arrays['radius_m'][active].copy();speeds=np.linalg.norm(arrays['velocity_m_s'][index,active],axis=1)
    for a in (positions,radii,speeds):a.setflags(write=False)
    return dict(time_s=float(arrays['time_s'][index]),positions=positions,radii=radii,speeds=speeds,
        discharged_count=int(arrays['discharged_count'][index]),ejected_mass_kg=float(arrays['ejected_mass_kg'][index]))


def scene_figure(arrays,metadata,index,contacts=True,posthoc=False):
    f=frame_data(arrays,index);c=HopperConfig(**metadata['config']);body=metadata['obstacle'];n=c.n_particles
    speed=np.linalg.norm(arrays['velocity_m_s'],axis=2)
    vmax=max(.02,float(speed[arrays['active']].max()))
    norm=Normalize(0,vmax);color=plt.get_cmap('viridis')
    fig,(ax,trace)=plt.subplots(1,2,figsize=(9,4),gridspec_kw={'width_ratios':[1.4,1]},layout='constrained')
    for a,b in flat_floor_walls(c,f['time_s']):ax.plot([a[0],b[0]],[a[1],b[1]],color='#444444',lw=2)
    for p,r,v in zip(f['positions'],f['radii'],f['speeds']):ax.add_patch(Circle(p,r,color=color(norm(v)),ec='#303030',lw=.25))
    if body:
        ax.add_patch(Circle(body['center_m'],body['radius_m'],fc='#b84c3f',ec='#7b281d',lw=1))
        ax.plot(*body['center_m'],'+',color='white',ms=6)
    if contacts:
        graph=arrays['contact_graph'][index];p=arrays['position_m'][index]
        for i,j in zip(*np.nonzero(np.triu(graph,1))):
            if i>=n or not arrays['active'][index,i]:continue
            a=p[i]
            if j<n:b=p[j]
            elif j==n and body:b=np.asarray(body['center_m'])
            elif j==n+1:b=np.array([np.clip(a[0],-c.width_m/2,-c.outlet_width_m/2),0.])
            elif j==n+2:b=np.array([np.clip(a[0],c.outlet_width_m/2,c.width_m/2),0.])
            else:continue
            ax.plot([a[0],b[0]],[a[1],b[1]],color='#111111',alpha=.6,lw=.6)
    ax.set(xlim=(-c.width_m/2-.006,c.width_m/2+.006),ylim=(-.045,.075),xlabel='Horizontal position [m]',ylabel='Height above chosen floor [m]')
    ax.set_aspect('equal',adjustable='box')
    q=metadata['parameters']['position_over_dFG'];name='No fixed grain' if q is None else f'Fixed grain: x/dFG={q:.2f}'
    ax.set_title(name+f"\nt={f['time_s']:.4f} s | discharged {f['discharged_count']}/{n}",fontsize=10)
    ax.text(.01,.01,'Outlet-region crop; walls continue to H=0.50m\nNear-outlet contact links; fixed grain marked +',transform=ax.transAxes,fontsize=6.7)
    fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=color),ax=ax,shrink=.6,label='Speed [m/s]')
    time=arrays['time_s'];stop=index+1
    trace.step(time[:stop],arrays['discharged_count'][:stop],where='post',color='#236a81',label='Particle count')
    mass=trace.twinx();mass.plot(time[:stop],arrays['ejected_mass_kg'][:stop]*1e6,color='#ae6b2f',lw=1.3,label='Actual nominal disk mass')
    trace.set(xlim=(0,float(time[-1])),ylim=(0,max(2,int(arrays['discharged_count'][-1])+1)),xlabel='Physical simulation time [s]',ylabel='Unique outlet crossings [particles]')
    mass.set_ylim(0,max(1,float(arrays['ejected_mass_kg'][-1])*1e6*1.1));mass.set_ylabel('Ejected mass [mg]',color='#ae6b2f')
    trace.axvline(f['time_s'],color='#666666',lw=.8);trace.grid(alpha=.18)
    trace.set_title('Stored discharge history (causal prefix)',fontsize=10)
    if posthoc:
        for e in metadata['events']:
            trace.axvline(e['onset_time_s'],ls='--',color='#b84c3f',label='Posthoc finite-arch onset')
            trace.axvline(e['confirmation_time_s'],ls=':',color='#6d4b89',label='Future confirmation')
        trace.legend(fontsize=6)
    fig.suptitle(LABEL,fontsize=9)
    return fig


def png_bytes(arrays,metadata,index,contacts=True):
    fig=scene_figure(arrays,metadata,index,contacts);buffer=BytesIO()
    fig.savefig(buffer,format='png',dpi=105,bbox_inches='tight');plt.close(fig);return buffer.getvalue()


def export_gif(arrays,metadata,path,max_frames=28):
    if max_frames<2:raise ValueError('At least two actual stored frames required')
    indices=np.unique(np.linspace(0,len(arrays['time_s'])-1,min(max_frames,len(arrays['time_s']))).astype(int))
    frames=[]
    for index in indices:
        fig=scene_figure(arrays,metadata,int(index));buf=BytesIO()
        fig.savefig(buf,format='png',dpi=72);plt.close(fig)
        with Image.open(buf) as im:frames.append(im.convert('RGB').quantize(colors=128))
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(target,save_all=True,append_images=frames[1:],duration=100,loop=0,optimize=True)
    return dict(source='actual_M7A_DEM_stored_states',stored_frame_indices=indices.tolist(),
        physical_times_s=arrays['time_s'][indices].tolist(),display_ms_per_frame=100,label=LABEL)


def result_figures(root):
    import json
    import pandas as pd
    from .run import load_run
    root=Path(root);out=root/'docs/results/m7a';table=pd.read_csv(out/'pilot_runs.csv')
    groups=json.loads((out/'pilot_groups.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    names=['control' if g['position_over_dFG'] is None else str(g['position_over_dFG']) for g in groups]
    means=[g['mean_ejected_mass_kg']*1e6 for g in groups];sd=[(g['sample_sd_kg'] or 0)*1e6 for g in groups]
    axes[0].bar(names,means,yerr=sd,capsize=4,color='#467e91')
    axes[0].set(xlabel='Numerical obstacle distance / diameter',ylabel='Ejected mass at 1.0s [mg]',title='Finite-fill DEM: mean ± sample SD, n=3')
    original=pd.read_csv(root/'docs/results/m6b/recovery/fixed_grain_summary.csv')
    axes[1].errorbar(original.fixed_grain_distance_over_dFG,original.normalized_mean_ejected_mass,
        yerr=original.reported_standard_error,fmt='o-',ms=3,capsize=3,color='#a96136')
    axes[1].axhline(1,color='gray',ls='--',lw=.8)
    axes[1].set(xlabel='Experimental x/dFG',ylabel='Source-normalized mean ejected mass',title='Cornerstones: 17 source bins ± reported SEM')
    fig.suptitle('Different stopping, boundary and forcing: separate observables; NO matched validation',fontsize=10)
    fig.savefig(out/'separate_observables.png',dpi=125,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for q,g in table.groupby('position_over_dFG',dropna=False):
        label='control' if pd.isna(q) else f'q={q:.2f}'
        axes[0,0].scatter(g.seed,g.ejected_mass_kg*1e6,label=label,s=23)
        axes[0,1].scatter(g.seed,g.max_overlap_over_radius,label=label,s=23)
    axes[0,0].set(xlabel='Independent seed (paired across conditions)',ylabel='Mass at 1.0s [mg]',title='All seed outcomes retained');axes[0,0].legend(fontsize=7)
    axes[0,1].axhline(.15,color='#a44',ls='--');axes[0,1].set(xlabel='Seed',ylabel='Maximum overlap / smaller radius',title='Numerical guard unchanged: 0.15')
    for q in (None,.30,1.14):
        tag='control' if q is None else 'q'+str(round(q*100)).zfill(3)
        run_id=f'm7a_{tag}_s77001';path=root/'data/simulated/m7a/trajectories'/(run_id+'.npz')
        if not path.exists():continue
        a,m=load_run(path);axes[1,0].step(a['time_s'],a['ejected_mass_kg']*1e6,where='post',label=tag)
        energy=a['diag_kinetic_j']+a['diag_gravity_j']+a['diag_normal_spring_j']+a['diag_tangent_spring_j']
        axes[1,1].plot(a['time_s'],energy,label=tag)
    axes[1,0].set(xlabel='Physical time [s]',ylabel='Cumulative ejected mass [mg]',title='Actual representative discharge histories');axes[1,0].legend(fontsize=7)
    axes[1,1].set(xlabel='Physical time [s]',ylabel='Retained mechanical energy [J]',title='Dissipation/export ≠ numerical energy error');axes[1,1].legend(fontsize=7)
    fig.savefig(out/'pilot_diagnostics.png',dpi=125,bbox_inches='tight');plt.close(fig)
    scenes={}
    for name,tag in [('control','control'),('near','q030'),('far','q114')]:
        run_id=f'm7a_{tag}_s77001';path=root/'data/simulated/m7a/trajectories'/(run_id+'.npz')
        if not path.exists():continue
        a,m=load_run(path)
        target=out/(name+'.gif');receipt=export_gif(a,m,target)
        (out/(name+'.png')).write_bytes(png_bytes(a,m,int(np.searchsorted(a['time_s'],.2))))
        scenes[name]=dict(run_id=run_id,**receipt)
    (out/'animation_provenance.json').write_text(json.dumps(scenes,indent=2)+'\n')
