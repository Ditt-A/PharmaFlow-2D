"""Audit M4A grouping, feature whitelist, fitted preprocessing, freezes and predictions."""
import argparse
from pharmaflow.m4_audit import audit

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='outputs/metrics/m4')
    p.add_argument('--data', default='data/processed/m3')
    p.add_argument('--report', default='docs/results/m4')
    a = p.parse_args()
    audit(a.output, a.data, a.report)
