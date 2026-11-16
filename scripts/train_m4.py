"""Train the prespecified M4A CPU baselines without inspecting held-out metrics."""
import argparse
from pharmaflow.m4_training import train

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='configs/m4/baselines.json')
    p.add_argument('--output', default='outputs/metrics/m4')
    p.add_argument('--models', default='outputs/checkpoints/m4')
    p.add_argument('--data', default='data/processed/m3')
    a = p.parse_args()
    train(a.config, a.output, a.models, a.data)
