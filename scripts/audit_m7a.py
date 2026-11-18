"""Read-only M7A geometry, frozen pilot provenance and numerical results audit."""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from pharmaflow.config import HopperConfig
from pharmaflow.fixed_grain import mixture_packing,obstacle_at_outlet,elastic_collision_metrics
from pharmaflow.m7a_campaign import tasks,source_hashes,signature
from pharmaflow.m6b_data import atomic_json,file_hash
from pharmaflow.run import load_run


def geometry_gate(root):
    design=json.loads((root/'configs/m7a/pilot.json').read_text());entries=tasks(design)
    initial={};smallest_limit=float('inf')
    for entry in entries:
        p=entry['parameters'];c=HopperConfig(**p['config']);c.validate()
        s=mixture_packing(c,p['diameters_m'],p['packing_bottom_m'])
        smallest_limit=min(smallest_limit,c.timestep_limit_s(float(s.mass.min())))
        fingerprint=hashlib.sha256(s.position.tobytes()+s.radius.tobytes()+s.mass.tobytes()).hexdigest()
        if c.seed in initial:assert initial[c.seed]==fingerprint
        initial[c.seed]=fingerprint
        if p['position_over_dFG'] is not None:
            body=obstacle_at_outlet(c,p['position_over_dFG'],p['fixed_radius_m'],p['fixed_friction'])
            assert np.all(np.linalg.norm(s.position-body.center_m,axis=1)>s.radius+body.radius_m)
    gate=dict(version='m7a-geometry-v1',numerical_geometry_representable=True,experimental_geometry_matched=False,
        representable_geometry='Ideal flat floor with central outlet and vertical sides; circle rigidly fixed to floor',
        idealization='Chosen coordinates y_floor=0, y_FG=R_FG; x_FG=-D/2-q*dFG. Not measured source wall coordinates.',
        experimental_mismatches=['unknown exact floor/lip dimensions and tolerances','unknown species fractions (equal-count mixture assumed)',
            'no front/back friction','no vibration or recirculation','60-grain finite fill rather than approximately 35cm source fill',
            'outlet-plane unique passages rather than source semicircular observation boundary','0.4s finite-arch criterion rather than source 5s no-exit rule',
            'friction/stiffness/damping uncalibrated'],
        actual_smallest_mass_timestep_limit_s=smallest_limit,paired_initial_state_sha256=initial,
        approved_for_exploratory_pilot_only=True,physical_agreement_score_allowed=False)
    atomic_json(root/'docs/results/m7a/geometry_gate.json',gate)
    atomic_json(root/'docs/results/m7a/elastic_contact_verification.json',elastic_collision_metrics())
    print(json.dumps(gate,indent=2));return gate


def historical_check(root):
    before=json.loads((root/'outputs/metrics/m7a/historical_snapshot.json').read_text())
    changed=[p for p,sha in before.items() if not (root/p).is_file() or file_hash(root/p)!=sha]
    if changed:raise ValueError('Historical artifact changed: '+repr(changed))
    ledger=(root/'outputs/demos/m5/budget.sqlite3').resolve()
    with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True) as con:rows=con.execute('SELECT * FROM attempts ORDER BY created_utc').fetchall()
    assert [list(r) for r in rows]==json.loads((root/'outputs/metrics/m7a/demo_ledger_before.json').read_text())
    from pharmaflow.m4b_evaluation import verify_freeze
    frozen=verify_freeze()
    return dict(unchanged_historical_files=len(before),unchanged_m5_attempts=len(rows),frozen_candidates=len(frozen['candidates']))


def audit(root):
    base=root/'data/simulated/m7a';out=root/'docs/results/m7a'
    frozen=json.loads((base/'design_freeze.json').read_text());design=json.loads((root/'configs/m7a/pilot.json').read_text())
    assert frozen['source_sha256']==source_hashes(root) and frozen['design_sha256']==signature(design)
    assert frozen['geometry_gate_sha256']==file_hash(out/'geometry_gate.json')
    assert frozen['prepilot_verification_sha256']==file_hash(out/'prepilot_verification.json')
    with sqlite3.connect((base/'attempts.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as con:
        ledger=[dict(zip(('run_id','status','parameters','started_utc','finished_utc','wall_s','error'),r)) for r in con.execute('SELECT * FROM attempts ORDER BY started_utc')]
    assert len(ledger)<=12 and sum(r['wall_s'] or 0 for r in ledger)<=21600
    reports=[];failed=[]
    for entry in ledger:
        if entry['status']!='success':failed.append(entry);continue
        path=base/'trajectories'/(entry['run_id']+'.npz');receipt=json.loads(path.with_suffix('.receipt.json').read_text())
        assert file_hash(path)==receipt['sha256']
        a,m=load_run(path);assert m['source_sha256']==frozen['source_sha256']
        assert np.all(np.diff(a['time_s'])>0) and m['max_overlap_over_radius']<=.15
        assert np.all(np.isfinite(a['position_m'])) and np.all(np.isfinite(a['velocity_m_s']))
        expected=float(a['mass_kg'][np.isfinite(a['crossing_time_s'])].sum())
        assert abs(expected-m['ejected_mass_kg'])<1e-14
        assert np.all(np.isfinite(a['crossing_time_s'][~a['active'][-1]]))
        assert m['physics']['boundary_center_leak_samples']==0
        near_speed=None
        if m['obstacle']:
            distance=np.linalg.norm(a['position_m']-m['obstacle']['center_m'],axis=2)
            keep=a['active']&(a['position_m'][...,1]>=0)&(distance<=m['obstacle']['radius_m']+3*a['radius_m'].max())
            near_speed=float(np.linalg.norm(a['velocity_m_s'][keep],axis=1).mean()) if keep.any() else None
        c=HopperConfig(**m['config']);last=a['position_m'][-1];active=a['active'][-1]
        near=active&(last[:,1]>=0)&(last[:,1]<=2*c.outlet_width_m)&(np.abs(last[:,0])<c.outlet_width_m/2+5*float(a['radius_m'].max()))
        final_speed=np.linalg.norm(a['velocity_m_s'][-1,near],axis=1)
        from pharmaflow.m3_events import spans
        final_graph=a['contact_graph'][-1]
        is_censored=not m['events'] and not m['completed_discharge']
        reports.append(dict(run_id=entry['run_id'],seed=m['config']['seed'],position_over_dFG=m['parameters']['position_over_dFG'],
            observation_duration_s=float(a['time_s'][-1]),final_discharged_count=int(a['discharged_count'][-1]),
            final_remaining_particles=int(a['remaining_count'][-1]),right_censored_for_arch_event=is_censored,
            censoring_reason='observation_end_without_confirmed_arch_or_empty_hopper' if is_censored else None,
            final_near_outlet_speed_mean_m_s=float(final_speed.mean()) if len(final_speed) else None,
            final_near_contact_edges=int(np.triu(final_graph,1).sum()),
            final_contact_graph_spans_walls=bool(spans(final_graph)),
            ejected_count=m['ejected_count'],ejected_mass_kg=m['ejected_mass_kg'],mass_fraction=m['mass_fraction'],
            completed_discharge=m['completed_discharge'],confirmed_finite_arch=bool(m['events']),startup_blockage=m['startup_blockage'],
            arch_onset_s=m['events'][0]['onset_time_s'] if m['events'] else None,
            arch_confirmation_s=m['events'][0]['confirmation_time_s'] if m['events'] else None,
            first_finite_arch_mass_kg=m['first_finite_arch_mass_kg'],
            max_overlap_over_radius=m['max_overlap_over_radius'],overlap_p95_upper=m['physics']['overlap_quantile_upper_bounds']['0.95'],
            max_angular_speed_rad_s=m['physics']['max_angular_speed_rad_s'],max_force_n=m['physics']['max_contact_force_n'],
            near_obstacle_speed_mean_m_s=near_speed,obstacle_contact_observations=m['obstacle_contact_step_observations'],
            wall_s=entry['wall_s'],cpu_s=m['cpu_time_s'],initial_state_sha256=m['initial_state_sha256'],trajectory_sha256=receipt['sha256']))
    table=pd.DataFrame(reports);table.to_csv(out/'pilot_runs.csv',index=False)
    groups=[]
    if len(table):
        for seed,g in table.groupby('seed'):assert g.initial_state_sha256.nunique()==1
        control=table[table.position_over_dFG.isna()]
        denominator=float(control.ejected_mass_kg.mean()) if len(control)==3 else None
        for q in [None,.30,.66,1.14]:
            g=control if q is None else table[table.position_over_dFG==q]
            if not len(g):continue
            mean=float(g.ejected_mass_kg.mean())
            groups.append(dict(position_over_dFG=q,n=len(g),mean_ejected_mass_kg=mean,
                sample_sd_kg=float(g.ejected_mass_kg.std(ddof=1)) if len(g)>1 else None,
                mean_ejected_count=float(g.ejected_count.mean()),confirmed_finite_arches=int(g.confirmed_finite_arch.sum()),
                normalized_fixed_horizon_mass=mean/denominator if denominator is not None and denominator>0 and len(g)==3 else None,
                normalization_scope='1.0s finite-fill outlet-plane mass; not source avalanche mass or flow rate'))
    atomic_json(out/'pilot_groups.json',groups);atomic_json(out/'attempt_ledger.json',ledger)
    summary=dict(decision='M7A_NUMERICAL_ANALOGUE_FEASIBLE' if len(reports) else 'M7A_NUMERICAL_VALIDITY_BLOCKED',
        attempts=len(ledger),successful=len(reports),failed=len(failed),unattempted=12-len(ledger),
        actual_worker_wall_s=sum(r['wall_s'] or 0 for r in ledger),actual_solver_cpu_s=sum(r['cpu_s'] for r in reports),
        confirmed_finite_arches=sum(r['confirmed_finite_arch'] for r in reports),startup_blockages=sum(r['startup_blockage'] for r in reports),
        completed_discharge=sum(r['completed_discharge'] for r in reports),unresolved_no_confirmed_arch=sum(not r['confirmed_finite_arch'] and not r['completed_discharge'] for r in reports),
        right_censored_no_confirmed_arch=sum(r['right_censored_for_arch_event'] for r in reports),
        maximum_overlap=max([r['max_overlap_over_radius'] for r in reports],default=None),
        experimental_comparison='Qualitative mechanism comparison only; geometry, forcing, boundary and stopping are unmatched',
        physical_agreement_score=None,larger_campaign_automatically_authorized=False,historical_integrity=historical_check(root))
    atomic_json(out/'audit_summary.json',summary)
    atomic_json(out/'design_freeze.json',frozen)
    print(json.dumps(summary,indent=2));return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--geometry-only',action='store_true');args=p.parse_args()
    (geometry_gate if args.geometry_only else audit)(Path('.').resolve())
