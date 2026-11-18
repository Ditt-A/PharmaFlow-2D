"""Read-only M7A research page. Every frame comes from a stored pilot trajectory."""
from pathlib import Path
import json
import pandas as pd
from .m6b_data import file_hash
from .run import load_run
from .m7a_simulation import LABEL
from .m7a_visuals import png_bytes


def fixed_grain_page(root):
    import streamlit as st
    root=Path(root);st.subheader('Fixed-grain feasibility study');st.info(LABEL)
    numerical,experimental=st.tabs(['Numerical analogue','Cornerstones experimental measurements'])
    with experimental:
        st.write('17 experimental aggregate bins with original reported SEM. The observable is normalized mean ejected mass, not instantaneous discharge rate.')
        st.image(str(root/'docs/results/m6b/recovery/fixed_grain_summary.png'),width='stretch')
        st.dataframe(pd.read_csv(root/'docs/results/m6b/recovery/fixed_grain_summary.csv'),hide_index=True,width='stretch')
        st.caption('Hanlan, Dillavou, Durian & Liu · Dryad 10.5061/dryad.cvdncjtb5 · CC0. Source paper/notebook provide x/dFG. No physical agreement score or calibrated optimum.')
    with numerical:
        st.write('Fixed geometry and independent paired seeds. The numerical pilot measures mass through the outlet plane over 1.0s; source forcing, observation boundary and five-second termination are unmatched.')
        base=root/'data/simulated/m7a/trajectories'
        records={p.stem:p for p in sorted(base.glob('*.npz')) if p.with_suffix('.receipt.json').exists()}
        if not records:st.info('No completed local M7A trajectories are present. Restore the evaluated pilot files; this page never starts a simulation.');return
        selected=st.selectbox('M7A stored pilot run',list(records))
        target=records[selected];receipt=json.loads(target.with_suffix('.receipt.json').read_text())
        if file_hash(target)!=receipt['sha256']:st.error('Stored trajectory checksum mismatch');return
        a,m=load_run(target);n=len(a['time_s'])
        if st.session_state.get('m7_selected')!=selected:
            st.session_state.update(m7_selected=selected,m7_frame=0,m7_playing=False,m7_advance=False)
        def play():st.session_state.m7_playing=True;st.session_state.m7_advance=False
        def pause():st.session_state.m7_playing=False
        def move(delta):
            st.session_state.m7_playing=False;st.session_state.m7_frame=max(0,min(n-1,st.session_state.m7_frame+delta))
        c=st.columns(5)
        c[0].button('M7A Play',on_click=play);c[1].button('M7A Pause',on_click=pause)
        c[2].button('M7A -1 frame',on_click=move,args=(-1,));c[3].button('M7A +1 frame',on_click=move,args=(1,))
        stride=c[4].selectbox('M7A stored frames per tick',[1,5,10],index=1)
        contacts=st.checkbox('M7A near-outlet contacts',True)
        st.caption('Playback uses original physical timestamps. Speed color is in m/s; the immobile grain is red with a +. No warning model is fitted or rescored here.')
        @st.fragment(run_every=.5 if st.session_state.m7_playing else None)
        def scene():
            if st.session_state.m7_playing and st.session_state.m7_advance:
                st.session_state.m7_frame=min(n-1,st.session_state.m7_frame+stride)
            st.session_state.m7_advance=bool(st.session_state.m7_playing)
            st.slider('Stored M7A frame',0,n-1,key='m7_frame',on_change=pause)
            k=st.session_state.m7_frame
            values=st.columns(3)
            values[0].metric('Physical simulation time',f'{a["time_s"][k]:.4f} s')
            values[1].metric('Particles discharged',f'{a["discharged_count"][k]}/{m["config"]["n_particles"]}')
            values[2].metric('Nominal disk mass ejected',f'{a["ejected_mass_kg"][k]*1e6:.2f} mg')
            data=png_bytes(a,m,k,contacts=contacts);st.image(data,width='stretch')
            st.download_button('Download M7A current PNG',data,file_name=selected+f'_frame{k}.png',mime='image/png')
            if st.session_state.m7_playing and k==n-1:
                st.session_state.m7_playing=False;st.rerun()
        scene()
        summary=root/'docs/results/m7a/pilot_runs.csv'
        if summary.exists():
            with st.expander('Complete pilot outcomes and numerical diagnostics'):
                st.dataframe(pd.read_csv(summary),hide_index=True,width='stretch')
        with st.expander('Physical assumptions and retrospective finite-arch observations'):
            st.json(dict(parameters=m['parameters'],finite_arches=m['events'],scope='0.4s future confirmation; separate from source 5s no-exit criterion'))
        for name in ('control','near','far'):
            gif=root/f'docs/results/m7a/{name}.gif'
            if gif.exists():st.download_button('Download '+name+' DEM GIF',gif.read_bytes(),file_name=name+'.gif',mime='image/gif')
