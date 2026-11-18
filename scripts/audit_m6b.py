"""Offline M6B integrity, literal schema and physical-compatibility audit. No solver/fits."""
import argparse
from collections import Counter
import json
from pathlib import Path
import importlib.metadata
import sqlite3
import pandas as pd
from pharmaflow.m6b_data import (atomic_json,file_hash,verify_acquisition,author_schema_evidence,
    parse_delft_info,parse_yogi_profiles,compatibility_gate)


def historical_integrity(root):
    snapshot=root/'outputs/metrics/m6b/historical_snapshot.json'
    if not snapshot.exists():
        return dict(status='NOT_AVAILABLE_ON_THIS_CHECKOUT',note='Original node snapshot is required to assert historical file preservation')
    files=json.loads(snapshot.read_text())
    changed=[name for name,sha in files.items() if not (root/name).is_file() or file_hash(root/name)!=sha]
    if changed:raise ValueError('Historical inputs changed: '+repr(changed))
    before=json.loads((snapshot.parent/'core_versions.json').read_text())
    assert all(importlib.metadata.version(k)==v for k,v in before.items())
    assert importlib.metadata.version('taichi')=='1.7.3'
    ledger=(root/'outputs/demos/m5/budget.sqlite3').resolve()
    with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True) as con:
        rows=con.execute('SELECT * FROM attempts ORDER BY created_utc').fetchall()
    assert [list(r) for r in rows]==json.loads((snapshot.parent/'demo_ledger_before.json').read_text())
    from pharmaflow.m4b_evaluation import verify_freeze
    frozen=verify_freeze(root/'data/simulated/m4b',root/'outputs/metrics/m4b')
    return dict(status='PASS',historical_files=len(files),unchanged_core_packages=len(before),
                frozen_candidates=len(frozen['candidates']),unchanged_m5_charged_attempts=len(rows),new_campaign_or_demo_attempts=0)


def audit(root):
    root=Path(root).resolve();raw=root/'data/raw/m6b';derived=root/'data/processed/m6b'
    compact=root/'docs/results/m6b';derived.mkdir(parents=True,exist_ok=True);compact.mkdir(parents=True,exist_ok=True)
    plan=json.loads((root/'configs/m6b/acquisition_plan.json').read_text())
    ledger=verify_acquisition(plan,root)
    provenance=[dict(a) for a in ledger['attempts']]
    atomic_json(compact/'acquisition_manifest.json',dict(plan_sha256=ledger['plan_sha256'],attempts=provenance,
        immutable_raw_inputs=True,error_bodies_are_not_measurements=True))
    evidence=[author_schema_evidence(raw/'author'/name) for name in
              ('ClassSelectionScript.py','FlowClass_WithFixedGrain.py','FixedParticleFigure.ipynb')]
    atomic_json(derived/'author_schema_evidence.json',evidence)
    # Compact field contract records uncertainty, not a fabricated parsed MATLAB run.
    contract=dict(status='CODE_EVIDENCE_ONLY_NO_MAT_FILE',raw_mat_schema_validated=False,
        trackinfo='numeric columns selected dynamically by tinfo_header',
        comment_named_columns=['x','y','timestamp','frame','species','dx','dy','ID'],
        structured_groups=['parameters','massflow','frameinfo'],
        code_named_parameters=['rads','D','cpt','xoutlet1','xoutlet2','youtlet1','youtlet2'],
        code_named_massflow=['M','T'],raw_coordinate_units=None,raw_velocity_units=None,
        raw_timestamp_units=None,raw_sampling_interval_verified=False,
        documentation_camera_rate_hz=130,documentation_rate_is_not_a_verified_mat_timestamp_conversion=True,
        axis_warning='Author drawing uses (y,x), (dy,dx), invert_yaxis; no mapping to DEM coordinates is inferred',
        executable_code_run=False,notebook_outputs_used_as_measurements=False,
        missing_inputs=['Flows3/*.mat','FreeData.pickle','FixedData.pickle','FreeOutletValues.pickle','Filenames_for_bin*.txt'],
        summary_text_context='Notebook cell 1 loads BinCenters, Dimensionless_M and Dimensionless_M_std_error for fixed-particle analysis. No values or fully verified normalization acquired.',
        source_files=[dict(file=e['file'],sha256=e['sha256']) for e in evidence])
    atomic_json(compact/'dryad_candidate_schema.json',contract)
    delft=parse_delft_info(raw/'delft/info_alp_20_d_100.txt')
    pd.DataFrame(delft).to_parquet(derived/'delft_acquisition_metadata.parquet',index=False)
    atomic_json(compact/'delft_acquisition_schema.json',dict(source_sha256=file_hash(raw/'delft/info_alp_20_d_100.txt'),
        source_license='CC BY-SA 4.0',attribution='Fransen, Schott and Langelaar, TU Delft Hopper Discharge Experiments',
        source_doi='10.4121/e3e48335-3a2f-4c10-88c4-54b9473d3927.v1',rows=delft))
    schema,profiles=parse_yogi_profiles(raw/'yogi/quasi2D-expt.numbers')
    pd.DataFrame(profiles).to_parquet(derived/'yogi_native_profiles.parquet',index=False)
    coverage=[]
    for table in schema:
        matching=[r for r in profiles if r['sheet']==table['sheet'] and r['table']==table['table']]
        coverage.append(dict(table,profile_rows=len(matching),native_parseable_y_uy_pairs=sum(r['native_y_uy_parseable'] for r in matching)))
    atomic_json(compact/'yogi_experimental_schema.json',dict(source_sha256=file_hash(raw/'yogi/quasi2D-expt.numbers'),
        source_license='CC BY 4.0',attribution='Yogi and Khakhar, Zenodo 20554446',tables=coverage,
        parsing='Literal strings plus nullable native floats. No cell repair, units/sign conversion or trajectory construction.'))
    protocol=json.loads((root/'configs/m6b/compatibility_gates.json').read_text())
    gates=[compatibility_gate(p) for p in protocol['pairs']]
    pd.DataFrame([{**g,'unmet_gates':'|'.join(g['unmet_gates'])} for g in gates]).to_csv(compact/'compatibility.csv',index=False)
    atomic_json(compact/'compatibility.json',gates)
    # A categorical evidence diagram, not an experimental trajectory or agreement plot.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from pharmaflow.m6b_data import COMPARISON_GATES
    fig,ax=plt.subplots(figsize=(11,5.6),layout='constrained')
    matrix=[[int(p['gates'].get(k) is True) for k in COMPARISON_GATES] for p in protocol['pairs']]
    ax.imshow(matrix,cmap=ListedColormap(['#efdbd5','#d3e7dd']),vmin=0,vmax=1,aspect='auto')
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):ax.text(j,i,'documented' if value else 'unresolved',ha='center',va='center',fontsize=8)
    ax.set_yticks(range(len(gates)),[g['id'] for g in gates],fontsize=9)
    ax.set_xticks(range(6),['Accessible\nmeasurement','Verified units\n& coordinates','Documented\ngeometry','Matched\nobservable','Uncertainty\nlimits explicit','Model form\nconsidered'],fontsize=8)
    ax.set_title('M6B-A evidence audit: 0 quantitatively eligible pairs\nCategorical checklist; no physical agreement or calibration',fontsize=11)
    fig.savefig(compact/'compatibility_gates.png',dpi=135,bbox_inches='tight');plt.close(fig)
    catalog_path=raw/'catalog/ledger.json';catalog=json.loads(catalog_path.read_text()) if catalog_path.exists() else dict(attempts=[])
    inventory=[]
    for a in catalog['attempts']:
        if a['state']!='complete':continue
        p=raw/'catalog'/a['path']
        if file_hash(p)!=a['sha256']:raise ValueError('Catalog checksum drift')
        data=json.loads(p.read_text())
        if isinstance(data,dict):
            for f in data.get('files',[]):
                inventory.append(dict(catalog=a['id'],name=f['name'],bytes=f['size'],published_md5=f.get('computed_md5'),
                    downloaded=False,source_url=a['url'],kind='advertised_file_not_acquired'))
    if len(catalog['attempts'])>4:raise ValueError('Catalog request budget exceeded')
    pd.DataFrame(inventory).to_csv(compact/'additional_delft_inventory.csv',index=False)
    atomic_json(compact/'catalog_provenance.json',catalog)
    source_bytes=sum(a['bytes'] for a in ledger['attempts'] if a['state']=='complete' and a['curated_reservation'])
    catalog_reserve=sum(a['reserved_bytes'] for a in catalog['attempts'])
    reserved=ledger['reserved_transfer_ceiling_bytes']+catalog_reserve
    assert reserved<=200000000
    result=dict(version='m6b-a-v1',decision='M6B_QUALITATIVE_COMPARISON_ONLY',
        charged_curated_reservations=sum(a['curated_reservation'] for a in ledger['attempts']),maximum_curated_files=12,
        successful_curated_files=sum(a['state']=='complete' and a['curated_reservation'] for a in ledger['attempts']),
        curated_bytes_on_disk=source_bytes,new_author_code_bytes=sum(a['bytes'] for a in ledger['attempts'] if a['role']=='author_code' and a['state']=='complete'),
        newly_downloaded_experimental_measurement_bytes=0,reused_experimental_profile_bytes=6942628,
        acquisition_observed_response_bytes=ledger['observed_response_payload_bytes'],
        catalog_observed_response_bytes=sum(a.get('transfer_bytes',0) for a in catalog['attempts']),
        combined_reserved_transfer_upper_bound_bytes=reserved,maximum_transfer_bytes=200000000,
        raw_mat_files=0,particle_trajectory_files=0,yogi_native_profile_rows=len(profiles),
        directly_parseable_native_y_uy_pairs=sum(r['native_y_uy_parseable'] for r in profiles),
        delft_acquisition_annotation_rows=len(delft),additional_delft_advertised_files=len(inventory),
        compatibility_counts=dict(Counter(g['classification'] for g in gates)),
        quantitative_comparisons=0,physical_agreement_scores_computed=0,
        historical_integrity=historical_integrity(root),new_solver_attempts=0,new_ml_fits=0,calibration_performed=False)
    atomic_json(compact/'audit_summary.json',result)
    atomic_json(compact/'processed_manifest.json',[dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=file_hash(p)) for p in sorted(derived.glob('*')) if p.is_file()])
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path('.'))
    audit(parser.parse_args().root)
