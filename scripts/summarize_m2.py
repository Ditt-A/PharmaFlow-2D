"""Quantitative tables and headless M2 research figures from saved solver runs."""
import argparse
import csv
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pharmaflow.run import load_run
from pharmaflow.config import HopperConfig
from pharmaflow.geometry import hopper_walls

plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':160})


def table_row(r):
    c=r['config'];m=r.get('metrics',{});p=r.get('physics',{});a=r.get('accuracy',{})
    return dict(run_id=r['run_id'],case=r['case'],seed=r['seed'],dt_s=c['dt_s'],duration_s=r['duration_s'],
                particles=c['n_particles'],outlet_diameter_ratio=c['outlet_width_m']/(2*c['particle_radius_m']),
                friction=c['friction'],wall_friction=c['wall_friction'],funnel_height_m=c['funnel_height_m'],
                wall_angle_from_vertical_deg=np.degrees(np.arctan((c['width_m']-c['outlet_width_m'])/(2*c['funnel_height_m']))),
                initial_lift_m=c['initial_lift_m'],status=r['status'],error=r.get('error',''),
                discharged=m.get('total_discharged'),fraction=m.get('discharge_fraction'),
                time_to_empty_s=m.get('time_to_empty_s'),flow_state=m.get('flow_state'),interior_pause=m.get('had_interior_pause'),
                near_outlet_area_fraction=m.get('near_outlet_area_fraction_mean'),speed_p95_m_s=m.get('active_speed_p95_m_s'),
                max_overlap_over_radius=a.get('max_overlap_over_radius'),overlap_p95_upper=p.get('overlap_quantile_upper_bounds',{}).get('0.95'),
                max_force_n=p.get('max_contact_force_n'),max_omega_rad_s=p.get('max_angular_speed_rad_s'),
                boundary_leak_samples=p.get('boundary_center_leak_samples'),conserved=a.get('particle_accounting'),
                runtime_s=r['runtime_s'],initial_state_sha256=r.get('initial_state_sha256'),trajectory_sha256=r.get('trajectory_sha256'))


def write_csv(path,rows):
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


def figure(path,fig):
    fig.tight_layout();fig.savefig(path,bbox_inches='tight');plt.close(fig)


def summarize(root,output):
    output.mkdir(parents=True,exist_ok=True)
    all_groups={}
    for group in ('pilot','pilot_fill','sweep','convergence'):
        results=json.loads((root/group/'results.json').read_text())
        from pharmaflow.validation import flow_metrics
        for r in results:
            if r['status']=='ok':
                arrays,meta=load_run(root/group/r['run_id']/'trajectory.npz')
                revised=flow_metrics(arrays,HopperConfig(**r['config']),r['duration_s'])
                if revised['flow_state']!=r['metrics']['flow_state']:
                    raise RuntimeError('Empty-hopper verification changed classification: '+r['run_id'])
                r['metrics']=revised
        all_groups[group]=results
        write_csv(output/(group+'.csv'),[table_row(r) for r in results])
    sweep=all_groups['sweep'];valid=[r for r in sweep if r['status']=='ok']
    grouped=defaultdict(list)
    for r in valid:grouped[r['case']].append(r)
    aggregate=[]
    for name,rs in sorted(grouped.items()):
        fractions=[r['metrics']['discharge_fraction'] for r in rs]
        states={s:sum(r['metrics']['flow_state']==s for r in rs) for s in sorted({r['metrics']['flow_state'] for r in rs})}
        aggregate.append({'case':name,'successful_seeds':len(rs),'fraction_mean':float(np.mean(fractions)),
                          'fraction_sample_sd':float(np.std(fractions,ddof=1)) if len(rs)>1 else None,
                          'states':states,'runtime_mean_s':float(np.mean([r['runtime_s'] for r in rs]))})
    fig,ax=plt.subplots(figsize=(9,4))
    for k,row in enumerate(aggregate):
        values=[r['metrics']['discharge_fraction'] for r in grouped[row['case']]]
        ax.scatter(np.full(len(values),k)+np.linspace(-.08,.08,len(values)),values,color='#247b91',s=24,zorder=3)
        ax.errorbar(k,row['fraction_mean'],yerr=row['fraction_sample_sd'] or 0,fmt='k_',capsize=4)
    ax.set(xticks=range(len(aggregate)),xticklabels=[r['case'] for r in aggregate],ylabel='discharge fraction at 0.8 s',ylim=(-.05,1.08))
    ax.tick_params(axis='x',rotation=28);ax.grid(axis='y',alpha=.2)
    figure(output/'parameter_sweep.png',fig)
    wide=next(r for r in valid if r['case']=='outlet7p5' and r['seed']==11)
    narrow=next(r for r in valid if r['case']=='outlet1p25' and r['seed']==11)
    fig,axes=plt.subplots(2,1,figsize=(7,5),sharex=True)
    for case in ('outlet1p25','outlet2','outlet3','outlet7p5'):
        for r in grouped[case]:
            a,_=load_run(root/'sweep'/r['run_id']/'trajectory.npz')
            label=f"{case}, mu={r['config']['friction']:g}"
            axes[0].plot(a['time_s'],a['discharged_count'],alpha=.65,lw=1,label=label if r['seed']==11 else None)
            edges=np.asarray(r['metrics']['flow_bin_edges_s']);rate=r['metrics']['flow_rate_particles_s']
            axes[1].step((edges[1:]+edges[:-1])/2,rate,where='mid',alpha=.4,lw=1)
    axes[0].set(ylabel='outlet crossings [particles]');axes[0].legend(ncol=2)
    axes[1].set(xlabel='time [s]',ylabel='rate [particles/s]')
    figure(output/'outlet_comparison.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(8,3.3))
    for r in (wide,narrow):
        p=r['physics'];edges=np.asarray(p['overlap_histogram_edges']);counts=np.asarray(p['overlap_histogram_counts'])
        axes[0].plot(edges[1:],np.cumsum(counts)/counts.sum(),label=r['case'])
        axes[1].scatter(p['max_contact_force_n'],p['max_angular_speed_rad_s'],label=r['case'])
    axes[0].set(xlabel='overlap / smaller radius',ylabel='contact-step empirical CDF',xlim=(0,.15));axes[0].legend()
    axes[1].set(xlabel='maximum contact force [N]',ylabel='maximum |spin| [rad/s]')
    figure(output/'overlap_rotation.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(9,3.5))
    for ax,r in zip(axes,(wide,narrow)):
        a,_=load_run(root/'sweep'/r['run_id']/'trajectory.npz');t=a['time_s']
        mechanical=sum(a['diag_'+key] for key in ('kinetic_j','rotation_j','gravity_j','normal_spring_j','tangent_spring_j'))
        ax.plot(t,mechanical,label='retained mechanical')
        ax.plot(t,mechanical+a['diag_exported_j'],label='+ advected energy')
        ax.plot(t,a['diag_normal_damping_loss_j'],label='normal dashpot loss')
        ax.set(title=r['case'],xlabel='time [s]',ylabel='energy [J]');ax.legend(fontsize=7)
    figure(output/'hopper_energy.png',fig)
    convergence=[];fig,axes=plt.subplots(1,2,figsize=(8,3.3))
    for ax,case in zip(axes,('wide','narrow')):
        rs=sorted([r for r in all_groups['convergence'] if r['case']==case],key=lambda r:r['dt_factor'])
        if any(r['status']!='ok' for r in rs):raise RuntimeError('failed convergence run')
        assert len({r['initial_state_sha256'] for r in rs})==1
        fine,_=load_run(root/'convergence'/rs[-1]['run_id']/'trajectory.npz')
        for r in rs:
            a,_=load_run(root/'convergence'/r['run_id']/'trajectory.npz')
            np.testing.assert_allclose(a['time_s'],fine['time_s'],atol=1e-12,rtol=0)
            mask=a['active'] & fine['active'] & (a['position_m'][...,1]>=0) & (fine['position_m'][...,1]>=0)
            error=np.linalg.norm(a['position_m']-fine['position_m'],axis=2)
            row=table_row(r)
            row.update(position_rmse_diameters=float(np.sqrt(np.mean(error[mask]**2))/(2*r['config']['particle_radius_m'])),
                       count_rmse_particles=float(np.sqrt(np.mean((a['discharged_count']-fine['discharged_count'])**2))),
                       final_count_difference_vs_finest=int(a['discharged_count'][-1]-fine['discharged_count'][-1]))
            convergence.append(row)
            ax.plot(a['time_s'],a['discharged_count'],label=f"dt/{r['dt_factor']}")
        ax.set(title=case,xlabel='time [s]',ylabel='outlet crossings',ylim=(0,rs[0]['config']['n_particles']+1));ax.legend()
    figure(output/'hopper_convergence.png',fig);write_csv(output/'convergence.csv',convergence)
    benchmarks=json.loads((root/'benchmarks/results.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(8,3.3))
    for key,style in (('elastic','-'),('damped_frictional','--')):
        for factor in (1,2,4):
            z=np.load(root/'benchmarks'/f'{key}_dt{factor}.npz')
            axes[0].plot(z['time_s'],z['energy_j']/z['energy_j'][0],style,label=f'{key}, dt/{factor}',lw=1)
    axes[0].set(xlabel='time [s]',ylabel='total pair energy / initial energy');axes[0].legend(fontsize=6)
    dt=[r['dt_s'] for r in benchmarks['elastic']]
    axes[1].loglog(dt,[r['max_energy_change_fraction'] for r in benchmarks['elastic']],'o-',label='elastic max energy error')
    axes[1].set(xlabel='dt [s]',ylabel='relative energy error');axes[1].legend(fontsize=7)
    figure(output/'controlled_convergence_energy.png',fig)
    (output/'benchmarks.json').write_text(json.dumps(benchmarks,indent=2)+'\n')
    audit=json.loads((root/'reference_audit.json').read_text())
    (output/'reference_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    report={'run_counts':{g:{'total':len(rs),'passed':sum(r['status']=='ok' for r in rs)} for g,rs in all_groups.items()},
            'sweep_aggregate':aggregate,'convergence':convergence,'benchmarks':benchmarks,
            'max_sweep_overlap_radius':max(r['accuracy']['max_overlap_over_radius'] for r in valid),
            'total_boundary_leak_samples':sum(r['physics']['boundary_center_leak_samples'] for r in valid),
            'all_successful_runs_conserve_particles':all(r['accuracy']['particle_accounting'] for r in valid),
            'source_sha256':sorted({r['source_sha256'] for r in sweep}),
            'failures':[table_row(r) for rs in all_groups.values() for r in rs if r['status']!='ok']}
    (output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return wide,narrow


def render_scene(path,output,small=False):
    from matplotlib.animation import FuncAnimation,PillowWriter
    from matplotlib.collections import EllipseCollection,LineCollection
    from pharmaflow.validation import flow_metrics
    a,m=load_run(path);c=HopperConfig(**m['config'])
    metrics=flow_metrics(a,c,m['duration_actual_s'])
    speed=np.linalg.norm(a['velocity_m_s'],axis=2);scale=max(float(np.quantile(speed[a['active']],.99)),.05)
    fig=plt.figure(figsize=(8,4.5));grid=fig.add_gridspec(2,2,width_ratios=[1,1.2])
    ax=fig.add_subplot(grid[:,0]);count_ax=fig.add_subplot(grid[0,1]);flow_ax=fig.add_subplot(grid[1,1])
    disks=EllipseCollection(2*a['radius_m'],2*a['radius_m'],np.zeros(c.n_particles),units='xy',
                            offsets=a['position_m'][0],transOffset=ax.transData,cmap='viridis',clim=(0,scale),linewidths=.25,edgecolors='#333333')
    ax.add_collection(disks);walls=LineCollection(hopper_walls(c,0),colors='black',lw=1.5);ax.add_collection(walls)
    ax.set(xlim=(-.055,.055),ylim=(c.removal_y_m,.11),aspect='equal',xlabel='x [m]',ylabel='y [m]')
    ax.set_title(f'DEM outlet / diameter = {c.outlet_width_m/(2*c.particle_radius_m):g}')
    fig.colorbar(disks,ax=ax,label='speed [m/s], clipped at q99',fraction=.045)
    count_ax.plot(a['time_s'],a['discharged_count'],color='#247b91');marker,=count_ax.plot([0],[0],'o',color='#c35a20')
    count_ax.set(xlim=(0,a['time_s'][-1]),ylim=(0,c.n_particles+1),ylabel='crossings [particles]')
    edges=np.array(metrics['flow_bin_edges_s']);flow_ax.step((edges[:-1]+edges[1:])/2,metrics['flow_rate_particles_s'],where='mid')
    cursor=flow_ax.axvline(0,color='#c35a20');flow_ax.set(xlim=(0,a['time_s'][-1]),xlabel='time [s]',ylabel='rate [particles/s]')
    stamp=count_ax.text(.03,.88,'',transform=count_ax.transAxes)
    title=fig.suptitle('Solver trajectory | SI units | uncalibrated 2D disks',fontsize=10)
    indices=np.unique(np.linspace(0,len(a['time_s'])-1,36 if small else 100,dtype=int))
    def update(k):
        p=a['position_m'][k].copy();p[~a['active'][k]]=np.nan
        disks.set_offsets(p);disks.set_array(speed[k]);walls.set_segments(hopper_walls(c,a['time_s'][k]))
        marker.set_data([a['time_s'][k]],[a['discharged_count'][k]]);cursor.set_xdata([a['time_s'][k]]*2)
        stamp.set_text(f"t={a['time_s'][k]:.3f} s; discharged={a['discharged_count'][k]}/{c.n_particles}")
        return disks,walls,marker,cursor,stamp
    fig.tight_layout()
    update(int(np.argmin(abs(a['time_s']-(.12 if c.outlet_width_m>.02 else a['time_s'][-1])))))
    fig.savefig(output.with_suffix('.png'),dpi=180,bbox_inches='tight')
    animation=FuncAnimation(fig,update,frames=indices,blit=False)
    animation.save(output,writer=PillowWriter(fps=12 if small else 25),dpi=75 if small else 100)
    plt.close(fig)


def reference_figure(root,output,trajectory):
    from numbers_parser import Document
    from audit_m2_reference import numeric
    doc=Document('data/raw/zenodo_20554446/quasi2D-sim.numbers')
    fig,axes=plt.subplots(1,2,figsize=(9,3.7))
    descriptors=[]
    for sheet in doc.sheets:
        for table in sheet.tables:
            rows=table.rows(values_only=True);header=[str(v) for v in rows[0]]
            if 'uy' not in header:continue
            pairs=[(numeric(row[header.index('y')]),numeric(row[header.index('uy')])) for row in rows[1:]]
            pairs=[p for p in pairs if None not in p];values=np.array(pairs)
            axes[0].plot(values[:,0],values[:,1],label=f'{sheet.name} ({len(pairs)}/{len(rows)-1} rows)')
            descriptors.append({'sheet':sheet.name,'velocity_numeric_range':np.ptp(values[:,1]).item(),
                                'velocity_coefficient_of_variation':float(np.std(values[:,1])/abs(np.mean(values[:,1]))),
                                'parsed_pair_count':len(pairs),'total_data_rows':len(rows)-1,
                                'comparison':'Parseable subset only; fragmented cells excluded without reconstruction. Not an accuracy metric or a complete reference profile.'})
    a,m=load_run(trajectory);p=a['position_m'];v=a['velocity_m_s'];active=a['active']
    edges=np.linspace(0,.06,13);centers=(edges[1:]+edges[:-1])/2;means=[]
    valid_time=(a['time_s']>=.05)&(a['time_s']<=.25)
    for lo,hi in zip(edges[:-1],edges[1:]):
        mask=active & valid_time[:,None] & (abs(p[...,0])<.004) & (p[...,1]>=lo)&(p[...,1]<hi)
        means.append(float(np.mean(abs(v[...,1][mask]))) if mask.any() else np.nan)
    axes[1].plot(centers,means,'o-',color='#247b91')
    axes[0].set(xlabel='published y (units/origin unverified)',ylabel='published uy (units unverified)',title='Reference: parseable subset only');axes[0].legend(fontsize=6)
    axes[1].set(xlabel='height above outlet [m]',ylabel='mean |vertical velocity| [m/s]',title='Our disks: center-strip spatial bins')
    fig.suptitle('Qualitative only: partial reference parsing, different axes/geometry/averaging',fontsize=10)
    figure(output/'reference_qualitative.png',fig)
    (output/'reference_descriptors.json').write_text(json.dumps(descriptors,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('outputs/metrics/m2'))
    parser.add_argument('--output',type=Path,default=Path('docs/results/m2'))
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    wide,narrow=summarize(args.root,args.output)
    if args.render:
        Path('outputs/animations').mkdir(parents=True,exist_ok=True);Path('assets').mkdir(exist_ok=True)
        for r,name in ((wide,'m2_wide'),(narrow,'m2_arch')):
            render_scene(args.root/'sweep'/r['run_id']/'trajectory.npz',Path('outputs/animations')/(name+'.gif'))
        render_scene(args.root/'sweep'/wide['run_id']/'trajectory.npz',Path('assets/m2_demo.gif'),small=True)
    reference_figure(args.root,args.output,args.root/'sweep'/wide['run_id']/'trajectory.npz')
    print('Saved quantitative tables and PNG figures:',args.output)
