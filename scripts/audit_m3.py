"""Audit stored M3 data; exit nonzero on physics, checksum, label or split leakage."""
import argparse,json
from pathlib import Path
from pharmaflow.m3_audit import audit_dataset
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/simulated/m3'))
    p.add_argument('--processed',type=Path,default=Path('data/processed/m3'))
    a=p.parse_args();r=audit_dataset(a.root,a.processed)
    print(json.dumps({k:v for k,v in r.items() if k not in ('physics_checks','event_lead_time_coverage')},indent=2))
