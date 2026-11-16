"""Run independent M2 cases; every frame comes from the DEM solver."""
import argparse
from pathlib import Path
from pharmaflow.experiments import run_suite

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--no-resume', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error('jobs must be between 1 and 8')
    results = run_suite(args.suite, args.output, args.jobs, not args.no_resume)
    raise SystemExit(0 if all(result['status'] == 'ok' for result in results) else 1)
