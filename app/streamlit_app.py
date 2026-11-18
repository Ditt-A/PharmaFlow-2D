"""Research UI: replay is read-only; only the explicit form submits a DEM job."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from pharmaflow.dashboard_data import historical_registry,load_bundle
from pharmaflow.dashboard_visuals import monitoring_figure,interactive_history,screenshot_bytes,export_gif
from pharmaflow.demo_jobs import jobs,launch_demo,limits

st.set_page_config(page_title='PharmaFlow · DEM research',page_icon='◉',layout='wide')
st.title('PharmaFlow · 2D DEM research')
st.caption('Actual dry-disk DEM states · frozen warning comparators · research scores, not industrial risk probabilities')

@st.cache_resource(max_entries=5)
def replay(serialized_record):
    return load_bundle(json.loads(serialized_record),ROOT)

page=st.sidebar.radio('Workspace',['Trajectory replay','Run a DEM demo','Research analysis','M7A fixed grain','Calibration gaps'])
st.sidebar.caption('Historical data, labels and models remain frozen. Demo runs are unevaluated and never enter research metrics.')

def set_play(value):
    st.session_state.playing=value
    st.session_state.advance_cursor=False
def scrub():
    st.session_state.playing=False
    st.session_state.advance_cursor=False
    st.session_state.scrubbed=True
def step(delta,n):
    st.session_state.playing=False
    st.session_state.frame=max(0,min(n-1,st.session_state.get('frame',0)+delta))

def replay_page():
    records=historical_registry(ROOT)
    if not records:
        st.info('No trajectory files found. Restore local M3/M4B data or a portable portfolio bundle; see docs/M5_DASHBOARD.md.')
        return
    scenes=json.loads((ROOT/'docs/results/m5/representative_scenes.json').read_text())['scenes']
    names={v:k for k,v in scenes.items()}
    records.sort(key=lambda r:(0 if r['run_id'] in names else 1,r['run_id']))
    choices={r['run_id']:r for r in records}
    selected=st.selectbox('Stored DEM trajectory',list(choices),format_func=lambda k:
        f"{names.get(k,'run')} · {k} · {choices[k]['membership']}")
    r=choices[selected]
    if st.session_state.get('selected_run')!=selected:
        st.session_state.update(selected_run=selected,frame=0,playing=False)
        st.session_state.pop('clip_bytes',None)
    b=replay(json.dumps(r,sort_keys=True));n=len(b.features)
    st.caption(f"{r['cohort']} / {r['membership']} | {r['packing_family']} | {r['config']['n_particles']} disks | "
               f"D/d = {b.features.outlet_ratio.iloc[0]:.2f} | stored interval {r['sample_interval_s']:.3f}s")
    if r['source']=='demo':
        st.warning('Unevaluated local demo. Frozen model scores may be outside its training regime, especially above 50 disks.')
    controls=st.columns([1,1,1,1,2,2])
    controls[0].button('Play',on_click=set_play,args=(True,))
    controls[1].button('Pause',on_click=set_play,args=(False,))
    controls[2].button('Previous',on_click=step,args=(-1,n))
    controls[3].button('Next',on_click=step,args=(1,n))
    stride=controls[4].selectbox('Stored frames per tick',[1,2,5,10],index=2)
    contacts=controls[5].checkbox('Near-outlet contact network',True)
    diagnostics=st.checkbox('Instantaneous arch diagnostic (not confirmed clogging)',True)
    st.caption('Playback advances stored states every wall-clock second. The simulation clock below is authoritative; playback is slowed down.')

    @st.fragment(run_every=1. if st.session_state.get('playing') else None)
    def scene():
        if st.session_state.pop('scrubbed',False):st.rerun()
        if st.session_state.get('playing') and st.session_state.get('advance_cursor'):
            st.session_state.frame=min(n-1,st.session_state.frame+stride)
        st.session_state.advance_cursor=bool(st.session_state.get('playing'))
        st.slider('Stored frame',0,n-1,key='frame',on_change=scrub)
        index=st.session_state.frame;row=b.monitoring.iloc[index];f=b.features.iloc[index]
        cols=st.columns(5)
        for col,label,value in zip(cols,['Physical time','Discharged','Remaining in hopper','Local occupancy estimator','Local mean speed'],
             [f'{row.time_s:.3f} s',str(int(row.discharged_count)),str(int(row.remaining_count)),
              f'{f.near_occupancy_estimate:.3f}',f'{f.near_speed_mean_m_s:.4f} m/s']):col.metric(label,value)
        st.write('Observed operation:',row.observed_state.replace('_',' '))
        left,right=st.columns(2)
        left.info(f"Frozen M4A rule: {row.rule_score:.3f} · {'active alert' if row.rule_active else 'clear'} · threshold 0.85")
        right.info('Frozen M4B ML: unavailable (restore its artifact or verified score cache)' if pd.isna(row.ml_score) else
                   f"Frozen M4B ML: {row.ml_score:.3f} · {'active alert' if row.ml_active else 'clear'} · threshold {b.specs['ml']['threshold']}")
        png=screenshot_bytes(b,index,contacts=contacts,diagnostics=diagnostics)
        st.image(png,width='stretch')
        with st.expander('Interactive warning-score trace and observed warning log'):
            st.plotly_chart(interactive_history(b,index),width='stretch')
            log=[dict(comparator=kind,**e) for kind in ('rule','ml') for e in b.logs[kind] if e['time_s']<=row.time_s+1e-12]
            st.dataframe(pd.DataFrame(log),hide_index=True,width='stretch')
        st.download_button('Download current PNG',png,
                           file_name=selected+f'_frame{index}.png',mime='image/png')
        if st.session_state.get('playing'):
            if index==n-1:
                st.session_state.playing=False;st.rerun()
    scene()
    st.divider()
    st.write('Short animation export uses the real stored frames, up to 0.8 physical seconds from the current cursor.')
    if st.button('Export short GIF'):
        index=st.session_state.frame
        start=min(index,n-2);end=min(n-1,start+round(.8/r['sample_interval_s']))
        target=ROOT/'outputs/dashboard/m5/exports'/f'{selected}_{start}.gif'
        with st.spinner('Rendering stored DEM states…'):
            manifest=export_gif(b,target,start,end,max_frames=30)
        target.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
        st.session_state.clip_bytes=target.read_bytes()
    if 'clip_bytes' in st.session_state:
        st.download_button('Download short GIF',st.session_state.clip_bytes,file_name=selected+'.gif',mime='image/gif')

def demo_page():
    st.subheader('Run a bounded real DEM demo')
    cap=limits(ROOT);all_jobs=jobs(ROOT)
    st.write(f"Budget: {len(all_jobs)}/{cap['maximum_attempts']} charged attempts; "
             f"{sum(j['request']['duration_s'] for j in all_jobs):.2f}/{cap['maximum_total_simulated_s']:.1f} requested simulation seconds. Failed attempts count.")
    st.caption('CPU solver · kn=4000 N/m · kt=1000 N/m · dt=5 µs · overlap guard 0.15 R · one job at a time · 180s wall-clock limit. '
               'Changing outlet width preserves the requested wall angle. No automatic retry or budget reset.')
    with st.form('new_demo'):
        a,b=st.columns(2)
        request=dict(outlet_ratio=a.slider('Outlet D/d',2.,6.,5.,.1),
            friction=a.slider('Particle friction',.15,.65,.3,.05),wall_friction=a.slider('Wall friction',.15,.65,.3,.05),
            wall_angle_deg=a.slider('Hopper angle from vertical [degrees]',28.,42.,35.,1.),
            n_particles=b.number_input('Initial disk count',30,100,30,1),
            packing_family=b.selectbox('Packing family',['staggered','hexagonal','random_sequential']),
            seed=b.number_input('Independent seed',0,2**32-1,57001,1),
            duration_s=b.number_input('Physical duration [s]',.10,.80,.12,.005,format='%.3f'))
        submitted=st.form_submit_button('Run DEM simulation')
    if submitted:
        try:
            run_id=launch_demo(request,ROOT);st.success('Reserved and launched '+run_id)
        except (ValueError,OSError) as exc:st.error(str(exc))
    @st.fragment(run_every=1.)
    def progress():
        current=jobs(ROOT)
        st.dataframe(pd.DataFrame([dict(run_id=j['run_id'],status=j['status'],duration_s=j['request']['duration_s'],error=j['error'])
                                  for j in current]),hide_index=True,width='stretch')
        st.caption('Completed jobs appear in Trajectory replay. Worker logs and failure records remain in outputs/demos/m5/.')
    progress()

def research_page():
    st.subheader('Frozen M4B evidence · retrospective research analysis')
    st.write('No policies were selected or tuned in M5. This page displays the original frozen locked evaluation.')
    table=pd.read_csv(ROOT/'docs/results/m4b/metrics.csv')
    ids=['frozen_configuration_holdout_h100_baseline_rule','m4b_h100_D_full_xgboost','m4b_h100_physics_rule_rule']
    rows=table.loc[(table.scope=='locked')&(table.replay=='online')&(table.candidate_id.isin(ids))]
    st.dataframe(rows[['candidate_id','events','useful_hits','mean_lead_s','false_forecasts','post_onset_alerts',
                       'false_per_observed_s','average_precision','brier']],hide_index=True,width='stretch')
    st.write('Original M4A rule: 7/7 useful warnings (≥20ms lead) and zero false first-event forecasts in 12 locked runs '
             'covering four configurations. This observation does not establish perfect generalization. '
             'The M4B ML policy issued 12 false first-event forecasts; 6 were late post-onset alerts. '
             'Raw rule and ML scores are not calibrated risk probabilities.')
    events=pd.read_csv(ROOT/'docs/results/m5/frozen_locked_event_runs.csv')
    import plotly.graph_objects as go
    lead=go.Figure()
    for identifier,label in [(ids[0],'Original M4A rule'),(ids[1],'Selected M4B ML')]:
        matched=events.loc[(events.candidate_id==identifier)&events.hit_any]
        lead.add_trace(go.Box(y=matched.lead_s*1000,name=label,boxpoints='all',jitter=.15,
                             hovertext=matched.run_id))
    lead.add_hline(y=20,line_dash='dot',annotation_text='20ms useful lead')
    lead.update_layout(yaxis_title='First valid warning lead [ms]',height=300,showlegend=False,
                       title='Frozen locked-event leads · seven independent first events per comparator')
    st.plotly_chart(lead,width='stretch')
    st.image(str(ROOT/'docs/results/m4b/locked_summary.png'),caption='Original M4B frozen evaluation',width='stretch')
    with st.expander('Lead times and historical event-level records'):
        st.dataframe(events,hide_index=True,width='stretch')
    st.subheader('Additional descriptive taxonomy · historical labels unchanged')
    st.dataframe(pd.read_csv(ROOT/'docs/results/m5/counts_by_cohort.csv'),hide_index=True,width='stretch')
    st.write('Established-flow arches are a subset of post-discharge arches: 7 of 42 first arches across M3/M4B, '
             'only 2 on the M4B locked cohort. Temporary interruptions can precede an arch or completed discharge; these categories are not disjoint.')
    for group in ('configuration_id','packing_family','prior_crossings'):
        with st.expander('Counts by '+group.replace('_',' ')):
            st.dataframe(pd.read_csv(ROOT/f'docs/results/m5/counts_by_{group}.csv'),hide_index=True,width='stretch')
    if st.checkbox('Show posthoc event annotations for a representative scene'):
        records=historical_registry(ROOT)
        ids=json.loads((ROOT/'docs/results/m5/representative_scenes.json').read_text())['scenes']
        name=st.selectbox('Research scene',list(ids))
        r=next((r for r in records if r['run_id']==ids[name]),None)
        if r:
            b=replay(json.dumps(r,sort_keys=True));fig=monitoring_figure(b,len(b.features)-1,posthoc=True)
            st.pyplot(fig,width='stretch');plt.close(fig);st.json(b.annotations)
        st.caption('Dashed onset and dash-dot confirmation use future observations for annotation only. They never enter online alert control.')

if page=='Trajectory replay':replay_page()
elif page=='Run a DEM demo':demo_page()
elif page=='Research analysis':research_page()
elif page=='M7A fixed grain':
    from pharmaflow.m7a_dashboard import fixed_grain_page
    fixed_grain_page(ROOT)
else:
    st.subheader('Physics calibration gaps')
    st.write('The simulator uses uncalibrated dry 2D disks. Cohesion, humidity sensitivity and irregular shape are absent. '
             'Legacy M5 scenes use equal-sized disks; M7A separately adds an exploratory three-size mixture and immobile obstacle. '
             'Published reference data describe a quasi-2D system of 3D particles; quantitative calibration remains unresolved. '
             'Startup blockage differs from interruption during established flow. No pharmaceutical or industrial deployment readiness is claimed.')
    st.markdown((ROOT/'docs/M5_CALIBRATION_GAPS.md').read_text() if (ROOT/'docs/M5_CALIBRATION_GAPS.md').exists() else
                'See docs/M5_CALIBRATION_GAPS.md for required material measurements and external validation experiments.')
