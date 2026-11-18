"""Freeze, profile and run the separately budgeted M7A CPU pilot; no automatic retries."""
import argparse
from pathlib import Path
import sys
if '--worker' in sys.argv:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(1790,1790))
from pharmaflow.m7a_campaign import freeze,dispatch,worker

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--freeze',action='store_true');group.add_argument('--profile',action='store_true')
    group.add_argument('--remaining',action='store_true');group.add_argument('--worker')
    args=p.parse_args()
    if args.worker:worker(Path('.'),args.worker)
    elif args.freeze:
        f=freeze();print(dict(runs=len(f['entries']),design_sha256=f['design_sha256'],frozen_utc=f['frozen_utc']))
    else:dispatch(profile_only=args.profile)
