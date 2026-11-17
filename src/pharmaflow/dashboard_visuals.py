"""Genuine stored particle geometry with causal-prefix monitoring traces and exports."""
from pathlib import Path
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection,LineCollection
from matplotlib.patches import Circle,Rectangle
from matplotlib.animation import FuncAnimation,PillowWriter
from .geometry import hopper_walls

RULE_COLOR='#bb741c'
ML_COLOR='#7856a3'


def draw_particles(ax,bundle,index,contacts=True,diagnostics=True,vmax=1.):
    f=bundle.frame(index);c=bundle.config
    p,v,r,active=f['positions'],f['velocities'],f['radius'],f['active']
    circles=PatchCollection([Circle(p[k],r[k]) for k in np.where(active)[0]],cmap='viridis',edgecolor='#233746',linewidth=.4)
    circles.set_array(np.linalg.norm(v[active],axis=1));circles.set_clim(0,vmax);ax.add_collection(circles)
    walls=hopper_walls(c,f['time_s']);ax.add_collection(LineCollection(walls,colors='#233746',linewidths=1.5))
    if contacts and 'contact_graph' in bundle.arrays:
        graph=bundle.arrays['contact_graph'][index];n=len(r)
        a,b=np.where(np.triu(graph[:n,:n],1));segments=[np.array([p[i],p[j]]) for i,j in zip(a,b)]
        for wall in (0,1):
            direction=walls[wall,1]-walls[wall,0]
            for i in np.where(graph[:n,n+wall])[0]:
                fraction=np.clip(np.dot(p[i]-walls[wall,0],direction)/np.dot(direction,direction),0,1)
                segments.append(np.array([p[i],walls[wall,0]+fraction*direction]))
        ax.add_collection(LineCollection(segments,colors='#d35337',linewidths=.8,alpha=.85))
    if diagnostics:
        ax.add_patch(Rectangle((-c.width_m/2,0),c.width_m,.025,color='#267b9c',alpha=.05))
        span=bool(bundle.features.spanning_arch_now.iloc[index])
        ax.text(.02,.02,'Spanning path now' if span else 'No spanning path now',transform=ax.transAxes,
                fontsize=8,color='#b44232' if span else '#365361')
    top=max(.06,float(bundle.arrays['position_m'][0,:,1].max())+.012)
    # Camera depends only on known initial fill, never future trajectory extrema.
    half=max(.025,min(c.width_m*.55,float(np.abs(bundle.arrays['position_m'][0,:,0]).max())+.010))
    ax.set(xlim=(-half,half),ylim=(-.015,top),aspect='equal',xlabel='x [m]',ylabel='y [m]')
    ax.set_title(f'Actual DEM state | t = {f["time_s"]:.3f} s',fontsize=10)
    ax.annotate('outlet',xy=(0,-.001),xytext=(.035,-.012),fontsize=7,
                arrowprops=dict(arrowstyle='->',color='#687d86'))
    return circles


def monitoring_figure(bundle,index,contacts=True,diagnostics=True,posthoc=False):
    bundle.frame(index)
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False})
    fig=plt.figure(figsize=(11,6.1),layout='constrained')
    grid=fig.add_gridspec(3,2,width_ratios=[1,1.65])
    particle=fig.add_subplot(grid[:,0]);circles=draw_particles(particle,bundle,index,contacts,diagnostics)
    fig.colorbar(circles,ax=particle,label='Particle speed [m/s]',fraction=.045)
    axes=[fig.add_subplot(grid[j,1]) for j in range(3)]
    f=bundle.features.iloc[:index+1];m=bundle.monitoring.iloc[:index+1];times=f.time_s
    axes[0].plot(times,bundle.arrays['discharged_count'][:index+1],color='#277c9e',label='Observed crossings')
    axes[0].set(ylabel='Discharged [particles]',ylim=(0,bundle.config.n_particles+1))
    flux=axes[0].twinx();flux.plot(times,f.flow_rate_50ms_particles_s,color='#a3b5bb',lw=1,label='Trailing 50ms flux')
    flux.set(ylabel='Flux [particles/s]',ylim=(0,max(100,float(f.flow_rate_50ms_particles_s.max())*1.1)))
    axes[1].plot(times,f.near_occupancy_estimate,color='#37876e',label='Occupancy estimator')
    axes[1].set(ylabel='Approx. local occupancy',ylim=(0,max(1,float(f.near_occupancy_estimate.max())*1.1)))
    speed=axes[1].twinx();speed.plot(times,f.near_speed_mean_m_s,color='#6e98ab',lw=1,label='Local mean speed')
    speed.set(ylabel='Speed [m/s]',ylim=(0,max(.5,float(f.near_speed_mean_m_s.max())*1.1)))
    for kind,color,label in [('rule',RULE_COLOR,'Frozen M4A rule'),('ml',ML_COLOR,'Frozen M4B ML')]:
        if kind=='ml' and m.ml_score.isna().all():continue
        axes[2].plot(times,m[kind+'_score'],label=label,color=color)
        axes[2].axhline(bundle.specs[kind]['threshold'],color=color,ls=':',lw=.8)
        log=[e for e in bundle.logs[kind] if e['time_s']<=times.iloc[-1]+1e-12]
        axes[2].scatter([e['time_s'] for e in log],[e['score'] for e in log],marker='v',s=22,color=color)
    axes[2].set(ylabel='Warning score',ylim=(0,1.05),xlabel='Physical simulation time [s]')
    for ax in axes:
        ax.set_xlim(0,max(.1,float(bundle.arrays['time_s'][-1])))
        ax.axvline(times.iloc[-1],color='#253f4c',lw=.6)
        ax.grid(alpha=.14)
        if posthoc:
            for event in bundle.annotations['arches']:
                ax.axvline(event['onset_time_s'],color='#b74532',ls='--',lw=1)
                ax.axvline(event['confirmation_time_s'],color='#358358',ls='-.',lw=1)
    axes[2].legend(loc='upper right',fontsize=7)
    fig.suptitle('Online observations only' if not posthoc else 'Research view | dashed onset / dash-dot future confirmation are posthoc',fontsize=10,color='#264553')
    return fig


def screenshot_bytes(bundle,index,**kwargs):
    fig=monitoring_figure(bundle,index,**kwargs);out=io.BytesIO()
    fig.savefig(out,format='png',dpi=130);plt.close(fig)
    return out.getvalue()


def export_gif(bundle,path,start=0,end=None,max_frames=50,posthoc=False):
    end=min(len(bundle.features)-1,start+int(round(.8/bundle.record['sample_interval_s']))) if end is None else end
    bundle.frame(start);bundle.frame(end)
    if end<=start or max_frames>60 or max_frames<2:raise ValueError('Export requires 2-60 stored frames')
    if bundle.arrays['time_s'][end]-bundle.arrays['time_s'][start]>1.+1e-10:raise ValueError('Export clips are limited to one physical second')
    indices=np.unique(np.linspace(start,end,min(max_frames,end-start+1),dtype=int))
    fig=plt.figure(figsize=(9,5.1))
    def update(index):
        fig.clear()
        # Draw the exact same scientific scene into this animation canvas.
        temporary=monitoring_figure(bundle,int(index),posthoc=posthoc)
        temporary.canvas.draw()
        rgba=np.asarray(temporary.canvas.buffer_rgba()).copy()
        ax=fig.add_axes([0,0,1,1]);ax.imshow(rgba);ax.axis('off');plt.close(temporary)
        return []
    animation=FuncAnimation(fig,update,frames=indices,interval=100,blit=False)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    try:animation.save(path,writer=PillowWriter(fps=10),dpi=75)
    finally:plt.close(fig)
    return dict(path=str(path),frame_indices=indices.tolist(),physical_start_s=float(bundle.arrays['time_s'][start]),
                physical_end_s=float(bundle.arrays['time_s'][end]),playback_fps=10,source='actual stored DEM states')


def interactive_history(bundle,index):
    import plotly.graph_objects as go
    m=bundle.monitoring.iloc[:index+1]
    fig=go.Figure()
    for kind,color in [('rule',RULE_COLOR),('ml',ML_COLOR)]:
        if kind=='ml' and m.ml_score.isna().all():continue
        fig.add_trace(go.Scatter(x=m.time_s,y=m[kind+'_score'],name=kind+' score',line=dict(color=color),mode='lines'))
    fig.update_layout(height=230,margin=dict(l=15,r=15,t=15,b=20),yaxis_title='Score (not probability)',
                      xaxis_title='Simulation time [s]',yaxis_range=[0,1.05],legend=dict(orientation='h'))
    return fig
