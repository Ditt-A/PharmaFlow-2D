"""Internal bounded demo supervisor/integrator; never a research campaign runner."""
import argparse
from pathlib import Path
from pharmaflow.demo_jobs import supervise_demo,integrate_demo

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--worker');group.add_argument('--integrate')
    p.add_argument('--root',type=Path,default=Path('.'))
    a=p.parse_args()
    if a.worker:supervise_demo(a.root.resolve(),a.worker)
    else:integrate_demo(a.root.resolve(),a.integrate)
