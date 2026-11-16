"""Independently replay representative complete M2 runs and compare all arrays."""
import argparse
import json
from pathlib import Path
from pharmaflow.experiments import run_experiment

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('outputs/metrics/m2'))
    args=parser.parse_args();reports=[]
    for name in ('outlet7p5_seed11_dt1','outlet1p25_seed11_dt1'):
        previous=json.loads((args.root/'sweep'/name/'summary.json').read_text())
        task={k:previous[k] for k in ('run_id','case','seed','dt_factor','config','duration_s','sample_every','backend')}
        fresh=run_experiment(task,args.root/'replay',resume=False)
        if fresh['status']!='ok':raise RuntimeError(fresh.get('error'))
        matched=previous['trajectory_sha256']==fresh['trajectory_sha256']
        if not matched:raise RuntimeError(name+' trajectory fingerprint differs')
        reports.append({'run_id':name,'matched':matched,'trajectory_sha256':fresh['trajectory_sha256']})
        print(name,'identical full-run fingerprint',flush=True)
    Path('docs/results/m2/replay.json').write_text(json.dumps(reports,indent=2)+'\n')
