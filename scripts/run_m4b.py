"""Freeze the M4B design or execute a budgeted phase; locked runs require frozen models."""
import argparse
import json
from pharmaflow.m4b_campaign import freeze_design, run_phase

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['freeze', 'pilot', 'adaptive', 'locked'], required=True)
    p.add_argument('--root', default='data/simulated/m4b')
    p.add_argument('--design', default='configs/m4b/design.json')
    p.add_argument('--adaptive', default='configs/m4b/adaptive.json')
    p.add_argument('--jobs', type=int, default=4)
    a = p.parse_args()
    r = freeze_design(a.design, a.root) if a.phase == 'freeze' else run_phase(a.phase, a.root, a.design, a.adaptive, a.jobs)
    print(json.dumps({k:v for k,v in r.items() if k not in ('records', 'tasks', 'pilot_tasks', 'locked_tasks', 'initial_sha256')}, indent=2))
