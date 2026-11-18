"""Offline supplement for four user-provided, checksum-verified Dryad files.

Place README and the three TXT files in data/raw/m6b/recovery/. This script never
retries the previously denied provider or changes the original M6B audit outputs.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pharmaflow.m6b_data import atomic_json,file_hash
from pharmaflow.m6b_recovery import parse_recovered_fixed_grain


def main(root):
    root=Path(root).resolve();raw=root/'data/raw/m6b/recovery'
    out=root/'docs/results/m6b/recovery';derived=root/'data/processed/m6b/recovery'
    rows,files=parse_recovered_fixed_grain(raw)
    original=json.loads((root/'data/raw/m6b/acquisition_ledger.json').read_text())
    catalog=json.loads((root/'data/raw/m6b/catalog/ledger.json').read_text())
    reservations=sum(a['curated_reservation'] for a in original['attempts'])+len(files)
    total_reserved=original['reserved_transfer_ceiling_bytes']+sum(a['reserved_bytes'] for a in catalog['attempts'])+sum(f['bytes'] for f in files)
    if reservations>12 or total_reserved>200000000:raise ValueError('Combined original/recovery budget exceeded')
    notebook=root/'data/raw/m6b/author/FixedParticleFigure.ipynb'
    if file_hash(notebook,'md5')!='52d59d341b95cbd8e012954b7a774aa5':
        raise ValueError('Official companion notebook checksum mismatch')
    manifest=dict(version='m6b-user-recovery-v1',original_release='b8228281578f5675dc15f7beef1be25ddb711cb0',
        source_doi='10.5061/dryad.cvdncjtb5',provider_version=376462,files=files,
        original_failed_download_unchanged=True,new_provider_requests=0,
        recovered_file_bytes=sum(f['bytes'] for f in files),recovered_numeric_summary_bytes=1275,
        combined_curated_reservations=reservations,maximum_curated_files=12,
        combined_retained_curated_bytes=sum(a['bytes'] for a in original['attempts'] if a['state']=='complete' and a['curated_reservation'])+sum(f['bytes'] for f in files),
        combined_reserved_bytes_including_local_inputs=total_reserved,maximum_transfer_bytes=200000000,
        author_notebook_sha256=file_hash(notebook),author_notebook_executed=False,
        axis_evidence='Source README plus companion notebook cells 14 and 18: x/d_FG; distance from outlet edge. No conversion to m.',
        observable_evidence='README: mean ejected mass divided by mean without a fixed grain at the same outlet; reported standard error uses the same normalization.',
        independent_run_counts=None,uncertainty='Reported SEM only; n/session covariance/normalizer uncertainty unavailable.',
        comparison_classification='INCOMPATIBLE_MODEL_FORM',
        comparison_reason='Current finite-fill monodisperse wedge has no matched fixed-grain obstacle experiment; confinement/forcing/materials also unmatched.',
        milestone_decision='M6B_QUALITATIVE_COMPARISON_ONLY',new_solver_attempts=0,new_ml_fits=0,calibration_performed=False)
    receipt=raw/'recovery_manifest.json'
    if receipt.exists() and json.loads(receipt.read_text())!=manifest:
        raise ValueError('Recovery provenance changed; never replace its immutable receipt')
    if not receipt.exists():atomic_json(receipt,manifest)
    out.mkdir(parents=True,exist_ok=True);derived.mkdir(parents=True,exist_ok=True)
    table=pd.DataFrame(rows)
    table.to_parquet(derived/'fixed_grain_summary.parquet',index=False)
    table.to_csv(out/'fixed_grain_summary.csv',index=False,float_format='%.17g')
    x=table.fixed_grain_distance_over_dFG.to_numpy();y=table.normalized_mean_ejected_mass.to_numpy();s=table.reported_standard_error.to_numpy()
    fig,ax=plt.subplots(figsize=(8.2,4.9),layout='constrained')
    ax.errorbar(x,y,yerr=s,fmt='o-',ms=4,lw=1.2,capsize=3,color='#216c84',label='Experimental mean ± reported SEM')
    ax.axhline(1,color='#777777',ls='--',lw=1,label='Source no-fixed-grain normalization')
    ax.set(xlabel='Fixed grain distance from outlet edge / fixed grain diameter',
           ylabel='Normalized mean ejected mass [dimensionless]',
           title='Cornerstones: recovered experimental fixed-grain summary')
    ax.legend(fontsize=8);ax.grid(alpha=.18)
    fig.text(.5,-.045,'Hanlan, Dillavou, Durian & Liu | Dryad 10.5061/dryad.cvdncjtb5 | CC0\n17 aggregate bins; error bars are SEM, not confidence intervals. No DEM overlay or calibration.',ha='center',fontsize=8)
    fig.savefig(out/'fixed_grain_summary.png',dpi=145,bbox_inches='tight');plt.close(fig)
    stats=dict(rows=len(rows),position_range_dimensionless=[float(x.min()),float(x.max())],
        normalized_mean_range=[float(y.min()),float(y.max())],
        reported_sem_range=[float(s.min()),float(s.max())],
        maximum_bin=dict(rows[int(np.argmax(y))]),all_finite=True,strictly_increasing_bins=True,
        independent_runs=None,particle_trajectory_files=0,physical_agreement_scores=0,
        figure='fixed_grain_summary.png')
    atomic_json(out/'provenance.json',manifest);atomic_json(out/'summary.json',stats)
    print(json.dumps(dict(stats=stats,budget=dict(curated_reservations=reservations,reserved_bytes=total_reserved)),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('.'))
    main(p.parse_args().root)
