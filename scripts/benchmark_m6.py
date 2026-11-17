"""Read-only benchmark screening and figures; never integrate DEM or fit parameters."""
from pathlib import Path
import argparse
import json
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pharmaflow.config import HopperConfig
from pharmaflow.run import load_run
from pharmaflow.dashboard_data import historical_registry
from pharmaflow.m4b_data import historical_training_ids
from pharmaflow.m4_data import digest,write_json
from pharmaflow.m6_benchmarks import steady_flow_support,crossing_rates


def permitted_records(root):
    m3=json.loads((root/'docs/results/m3/split_manifest.json').read_text())
    allowed=set(historical_training_ids(m3))
    dev=json.loads((root/'docs/results/m4b/development_split_manifest.json').read_text())
    allowed.update(k for k,v in dev['assignments'].items() if v=='train' and k.startswith('m4b_'))
    return sorted((r for r in historical_registry(root) if r['source']=='historical' and r['run_id'] in allowed),key=lambda r:r['run_id'])


def finish(fig,path):
    fig.savefig(path,dpi=155,bbox_inches='tight');plt.close(fig)


def figures(root,records,screen,protocol):
    out=root/'docs/results/m6';matrix=pd.read_csv(out/'compatibility_matrix.csv')
    ids=[b['id'] for b in protocol['benchmarks']]
    fig,ax=plt.subplots(figsize=(12,5.1),layout='constrained')
    values=np.zeros((3,len(ids)))
    sources=['dryad','delft','yogi']
    conditional={'conditional_raw_access','requires_PIV_and_calibration','requires_full_recording_review','native_units_unresolved'}
    for i,source in enumerate(sources):
        for j,key in enumerate(ids):
            status=matrix.loc[(matrix.source==source)&(matrix.benchmark==key),'status'].iloc[0]
            values[i,j]=1 if status in conditional else 0
            ax.text(j,i,textwrap.fill(status.replace('_',' '),17),ha='center',va='center',fontsize=7)
    ax.imshow(values,cmap=ListedColormap(['#ead1cc','#eee0b5']),vmin=0,vmax=1,aspect='auto')
    ax.set_xticks(range(len(ids)),[k.replace('_','\n') for k in ids],fontsize=8)
    ax.set_yticks(range(3),['Dryad disks','Delft gravel','Yogi profiles'])
    ax.set_title('External compatibility audit: 0 matched quantitative comparisons\nAmber: conditional observable recovery | rose: absent, incompatible or unresolved definition',fontsize=11)
    finish(fig,out/'compatibility_matrix.png')

    # Prespecified training example, not selected using a held-out flow outcome.
    example=next(r for r in records if r['run_id']=='pilot_0151aedb5166ad43_hexagonal_s202')
    a,_=load_run(root/example['trajectory_path']);c=HopperConfig(**example['config'])
    edges=np.arange(0,float(a['time_s'][-1])+.00001,.05)
    rates=crossing_rates(a['crossing_time_s'],edges,a['mass_kg'])
    fig,axes=plt.subplots(1,2,figsize=(11,4.1),layout='constrained')
    axes[0].plot(a['time_s'],a['discharged_count'],color='#267693')
    axes[0].set(xlabel='Physical simulation time [s]',ylabel='Unique outlet crossings [particles]',title='Existing training DEM: finite fill, no replenishment')
    axes[1].step((edges[:-1]+edges[1:])/2,rates['number_rate_s'],where='mid',label='Number flow [particles/s]',color='#267693')
    mass=axes[1].twinx();mass.step((edges[:-1]+edges[1:])/2,rates['mass_rate_kg_s'],where='mid',color='#a86d28')
    axes[1].set(xlabel='Physical simulation time [s]',ylabel='Number flow [particles/s]',title='50ms bins: exact simulated crossing masses')
    mass.set_ylabel('Mass flow [kg/s]',color='#a86d28')
    fig.suptitle('Available discharge observables | no verified matched experimental rate series was retrieved',fontsize=10)
    finish(fig,out/'available_discharge_observables.png')
    pd.DataFrame(rates).to_csv(root/'outputs/metrics/m6/example_rates.csv',index=False)

    # Experimental native values only. No units, sign, coordinate or cell repair is inferred.
    from numbers_parser import Document
    doc=Document(str(root/'data/raw/zenodo_20554446/quasi2D-expt.numbers'))
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained');profiles=[]
    def numeric(x):
        if x is None or isinstance(x,bool):return None
        try:
            value=float(x);return value if np.isfinite(value) else None
        except (ValueError,TypeError):return None
    for sheet in doc.sheets:
        for table in sheet.tables:
            rows=table.rows(values_only=True);header=[str(v) for v in rows[0]]
            if 'uy' not in header:continue
            pairs=[(numeric(r[header.index('y')]),numeric(r[header.index('uy')])) for r in rows[1:]]
            pairs=np.array([p for p in pairs if None not in p])
            if len(pairs):axes[0].plot(pairs[:,0],pairs[:,1],'.',ms=3,label=f'{sheet.name}: {len(pairs)}/{len(rows)-1} rows')
            profiles.append(dict(sheet=sheet.name,parsed_pairs=len(pairs),total_rows=len(rows)-1,units_verified=False))
    p,v=a['position_m'],a['velocity_m_s'];bins=np.linspace(0,.06,13);means=[];counts=[]
    time=(a['time_s']>=.05)&(a['time_s']<=.25)
    for lo,hi in zip(bins[:-1],bins[1:]):
        keep=a['active']&time[:,None]&(abs(p[...,0])<.004)&(p[...,1]>=lo)&(p[...,1]<hi)
        counts.append(int(keep.sum()));means.append(float(v[...,1][keep].mean()) if keep.any() else np.nan)
    axes[0].set(xlabel='Published y [unverified native units]',ylabel='Published uy [unverified native units]',title='Yogi experimental file: strict parseable subset')
    axes[0].legend(fontsize=6)
    axes[1].plot((bins[1:]+bins[:-1])/2,means,'o-',color='#267693')
    axes[1].set(xlabel='Height above outlet [m]',ylabel='Mean signed vertical velocity [m/s]',title='Training DEM: |x|<4mm, t=0.05–0.25s')
    fig.suptitle('Separate axes; incomplete external parsing and incompatible averaging. NO physical-agreement claim.',fontsize=10)
    finish(fig,out/'native_profile_limits.png')
    write_json(out/'native_profile_coverage.json',dict(experimental=profiles,simulation_particle_time_counts=counts,
        source_md5='c701fb415580d6ffa6d9fc9945bce0fe',note='No missing-cell repair, rescaling, error metric or fit'))

    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for cohort,group in screen.groupby('cohort'):
        axes[0].scatter(group.usable_window_s,group.observed_crossings,label=cohort,alpha=.7,s=24)
    axes[0].axhline(200,color='#b0513f',ls='--',label='Required >=200 crossings')
    axes[0].axvline(1,color='#b0513f',ls=':')
    axes[0].set(xlabel='Post-buffer duration before depletion [s]',ylabel='Observed unique crossings',
                title='Training-only screening (long arch tails are not steady flow)',ylim=(-5,225))
    axes[0].legend(fontsize=7)
    axes[1].axis('off')
    axes[1].text(.02,.95,'CONCEPTUAL DIMENSIONAL CANDIDATE\n\nQm = C rho_A,bulk sqrt(g) (D − k d)^(3/2)\n\n'
        'rho_A,bulk: kg/m², not kg/m³\nQN = Qm / m only for known equal masses\n\n'
        'C, k and exponent are not universal.\nFriction, inclination, confinement and packing matter.\n\n'
        'No zero-flow regression points.\nNo coefficients fitted.\nNo steady-flow scaling validation from these small fills.',va='top',fontsize=10)
    fig.suptitle('Scaling applicability: prespecified support requirements, not an empirical fit',fontsize=11)
    finish(fig,out/'scaling_applicability.png')

    old=json.loads((root/'docs/results/m2/benchmarks.json').read_text())['elastic']
    fig,ax=plt.subplots(figsize=(6,3.7),layout='constrained')
    ax.loglog([r['dt_s'] for r in old],[100*r['max_energy_change_fraction'] for r in old],'o-',color='#267693')
    ax.set(xlabel='Timestep [s]',ylabel='Maximum elastic-pair energy error [%]',title='Actual M2 numerical convergence ≠ physical calibration')
    ax.grid(alpha=.2);finish(fig,out/'numerical_evidence.png')
    fig,axes=plt.subplots(1,4,figsize=(12,3.6),layout='constrained')
    cards=[('A · Discretization','dt / stiffness sensitivity\nFinite overlaps\nIntegrator/contact-history error'),
           ('B · Model form','2D disks vs 3D grains\nFront/back friction\nNo rolling resistance, cohesion or air coupling'),
           ('C · Parameters','Unknown friction / restitution\nSize, mass and roughness\nConfounded bulk packing'),
           ('D · Experiment','Optical/time/mass calibration\nSampling and repeated fills\nUncertain units / geometry')]
    for ax,(title,body) in zip(axes,cards):
        ax.axis('off');ax.text(.03,.85,title,fontsize=11,weight='bold')
        ax.text(.03,.65,textwrap.fill(body,25,replace_whitespace=False),va='top',fontsize=10,
                bbox=dict(boxstyle='round,pad=.8',facecolor='#e3edf0',edgecolor='#b4c9d0'))
    fig.suptitle('CONCEPTUAL discrepancy decomposition: convergence bounds A; it does not eliminate B–D',fontsize=11)
    finish(fig,out/'uncertainty_diagram.png')

    parameters=[['Size / mass / physical thickness','Reported for Dryad disks','Measure independently'],
        ['Bulk area fraction','Definition / raw data unresolved','Not identifiable from Q alone'],
        ['Particle / sidewall friction','No separate measurements retrieved','Confounded in one Q curve'],
        ['Restitution / dashpot','No collision measurements retrieved','Require independent bounce tests'],
        ['Normal / tangential stiffness','Existing numerical sensitivity only','Choose converged regime'],
        ['Front/back friction','Absent from current engine','Model-form extension, not a fitted sidewall proxy'],
        ['Rolling / cohesion / irregularity','Absent from current engine','Cannot identify a missing physical mechanism']]
    fig,ax=plt.subplots(figsize=(12,4.5));ax.axis('off')
    table=ax.table(cellText=parameters,colLabels=['Parameter / mechanism','Present evidence','Identifiability assessment'],loc='center',cellLoc='left',colWidths=[.27,.32,.41])
    table.auto_set_font_size(False);table.set_fontsize(8);table.scale(1,2)
    ax.set_title('CONCEPTUAL identifiability assessment — no fitted sensitivity matrix or parameter estimates',fontsize=11,pad=18)
    finish(fig,out/'parameter_identifiability.png')

    acquisition=pd.read_csv(out/'acquisition_metadata.csv');verified=acquisition.loc[acquisition.header_verified]
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    for angle,group in verified.groupby('nominal_angle_deg'):
        ax.plot(group.run_index,group.sampling_hz,'o-',label=f'{angle:g}° nominal')
    for value in sorted(verified.catalog_sampling_hz.dropna().unique()):
        ax.axhline(value,color='#777',ls=':',lw=.8,label=f'Catalog value (record dependent): {value:g}Hz')
    ax.set(xlabel='Run index within each configuration',ylabel='Headered frame-rate annotation [frames/s]',
           title='Actual acquisition metadata; 10 headerless annotations excluded\nThese are recording rates, not discharge measurements')
    ax.legend(ncol=3,fontsize=7);finish(fig,out/'acquisition_uncertainty.png')

    fig,ax=plt.subplots(figsize=(9,3.8));ax.axis('off')
    ax.text(.02,.92,'PHYSICS-VALIDATION READINESS',fontsize=15,weight='bold')
    lines=['Numerical tests and convergence: recorded; no proof of calibration',
           'Three external sources: metadata and provenance audited',
           'Matched units / geometry / material / averaging: not established',
           'Current training trajectories: no qualified sustained-flow scaling runs',
           'Parameter fitting, new DEM and ML training: none',
           'Decision: M6A_LIMITED_COMPARISON_ONLY']
    ax.text(.02,.73,'\n\n'.join(lines),va='top',fontsize=10)
    ax.text(.02,.02,'Conceptual readiness checklist grounded in the source audit, not a validation score.',fontsize=8)
    finish(fig,out/'readiness_summary.png')
    return example['run_id']


def main(root):
    protocol=json.loads((root/'configs/m6/benchmark_protocol.json').read_text())
    out=root/'docs/results/m6';out.mkdir(parents=True,exist_ok=True)
    (root/'outputs/metrics/m6').mkdir(parents=True,exist_ok=True)
    records=permitted_records(root);rows=[]
    if not records:raise ValueError('Restore the local historical releases; no simulations will be generated')
    for r in records:
        path=root/r['trajectory_path']
        if digest(path)!=r['npz_sha256']:raise ValueError('Historical trajectory checksum differs')
        a,_=load_run(path);c=HopperConfig(**r['config'])
        support=steady_flow_support(a,c,protocol['steady_flow'])
        rows.append(dict(run_id=r['run_id'],cohort=r['cohort'],configuration_id=r['configuration_id'],
            packing_family=r['packing_family'],n_particles=c.n_particles,outlet_ratio=c.outlet_width_m/(2*c.particle_radius_m),
            **{k:v for k,v in support.items() if k not in ('reasons','block_rates_s')},
            reasons_json=json.dumps(support['reasons']),block_rates_json=json.dumps(support['block_rates_s'])))
    frame=pd.DataFrame(rows);frame.to_csv(out/'training_flow_support.csv',index=False,lineterminator='\n')
    example=figures(root,records,frame,protocol)
    result=dict(decision=protocol['decision'],training_runs_screened=len(rows),cohort_counts=frame.cohort.value_counts().to_dict(),
        physical_configurations=int(frame.configuration_id.nunique()),maximum_initial_particles=int(frame.n_particles.max()),
        qualified_scaling_runs=int(frame.eligible_for_scaling.sum()),maximum_post_buffer_crossings=int(frame.observed_crossings.max()),
        example_run_id=example,held_out_runs_used_for_fitting=0,parameters_fitted=0,new_solver_attempts=0,
        fitting_performed=False,external_agreement_metric_computed=False,
        limitation='Short finite fills and arch tails do not establish sustained free-flow scaling; no test cohort used for parameter or policy selection')
    write_json(out/'benchmark_summary.json',result)
    write_json(out/'figure_manifest.json',dict(files=[dict(path=str(p.relative_to(root)),sha256=digest(p)) for p in sorted(out.glob('*.png'))],
        figure_policy='Measured/simulated native data labeled explicitly; conceptual diagrams marked conceptual; no agreement overlay or fit'))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path('.'))
    main(parser.parse_args().root.resolve())
