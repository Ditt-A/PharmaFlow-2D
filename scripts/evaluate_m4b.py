"""Build immutable releases, freeze development fits, then evaluate the locked cohort once."""
import argparse
import json

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', required=True, choices=['build-pilot', 'build-development', 'train', 'evaluate', 'visualize', 'audit'])
    p.add_argument('--root', default='data/simulated/m4b')
    p.add_argument('--output', default='outputs/metrics/m4b')
    p.add_argument('--data', default='data/processed/m4b')
    p.add_argument('--report', default='docs/results/m4b')
    a = p.parse_args()
    if a.stage.startswith('build-'):
        from pharmaflow.m4b_data import build_release
        r = build_release(a.stage[6:], a.root, a.data)
        print(json.dumps({k:v for k,v in r.items() if k not in ('files', 'raw')}, indent=2))
    elif a.stage == 'train':
        from pharmaflow.m4b_training import freeze_train
        freeze_train(root=a.root, data=a.data+'/development', output=a.output)
    elif a.stage == 'evaluate':
        from pharmaflow.m4b_evaluation import evaluate_locked
        evaluate_locked(a.root, a.data, a.output, a.report)
    elif a.stage == 'visualize':
        from pharmaflow.m4b_visualize import visualize
        visualize(a.root, a.data, a.output, a.report)
    else:
        from pharmaflow.m4b_audit import audit
        audit(a.root, a.data, a.output, a.report)
