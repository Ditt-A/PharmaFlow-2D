"""Run one explicitly budgeted synthetic DEM campaign; no ML training."""
import argparse
from pathlib import Path
from pharmaflow.m3_campaign import run_campaign

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path('data/simulated/m3'))
    p.add_argument('--jobs',type=int,default=1)
    a=p.parse_args()
    if not 1<=a.jobs<=8:p.error('jobs must be in [1,8]')
    for folder in ('pilot','production','manifests','failures'):(a.root/folder).mkdir(parents=True,exist_ok=True)
    result=run_campaign(a.plan,a.root,a.jobs)
    raise SystemExit(0 if all(r['status']=='ok' for r in result['records']) else 1)
