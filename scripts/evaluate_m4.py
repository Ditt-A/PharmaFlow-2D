"""Evaluate frozen M4A artifacts exactly once, then create reproducible diagnostics."""
import argparse
from pharmaflow.m4_evaluation import evaluate
from pharmaflow.m4_diagnostics import diagnostics

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='outputs/metrics/m4')
    p.add_argument('--data', default='data/processed/m3')
    p.add_argument('--report', default='docs/results/m4')
    p.add_argument('--plots-only', action='store_true')
    a = p.parse_args()
    if not a.plots_only:
        evaluate(a.output, a.data, a.report)
    diagnostics(a.output, a.data, a.report)
