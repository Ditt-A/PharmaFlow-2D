"""Build versioned M3 Parquet features/targets and grouped split manifests."""
import argparse
import json
from pathlib import Path
from pharmaflow.m3_dataset import build_dataset

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/simulated/m3'))
    p.add_argument('--output',type=Path,default=Path('data/processed/m3'))
    a=p.parse_args();r=build_dataset(a.root,a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('files','raw_trajectories')},indent=2))
