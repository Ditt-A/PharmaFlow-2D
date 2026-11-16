"""Dependent-frame descriptions and cluster, never individual-frame, resampling."""
import numpy as np
from sklearn.metrics import (average_precision_score, roc_auc_score, precision_recall_fscore_support,
                             brier_score_loss, confusion_matrix)
from .m4_data import run_weights
from .m4_alerts import event_metrics


def frame_metrics(df, threshold, weights=None):
    y, p = df.target.to_numpy(int), df.probability.to_numpy(float)
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid probabilities')
    prediction = p >= threshold
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, prediction, average='binary', zero_division=0, sample_weight=weights)
    both = len(np.unique(y)) == 2
    cm = confusion_matrix(y, prediction, labels=[0, 1], sample_weight=weights)
    return dict(rows=len(df), positive_prevalence=float(np.average(y, weights=weights)),
                average_precision=float(average_precision_score(y, p, sample_weight=weights)) if np.any(y) else None,
                roc_auc=float(roc_auc_score(y, p, sample_weight=weights)) if both else None,
                precision=float(precision), recall=float(recall), f1=float(f1),
                brier=float(brier_score_loss(y, p, sample_weight=weights)),
                tn=float(cm[0, 0]), fp=float(cm[0, 1]), fn=float(cm[1, 0]), tp=float(cm[1, 1]))


def cluster_bootstrap(df, run_rows, threshold, group_key, repeats=300, seed=20261117):
    """Resample frozen runs/configurations with replacement; whole sequences stay intact.

    Degenerate replicates are excluded only for undefined metrics, with coverage
    reported. Percentile intervals are descriptive with very few held-out groups.
    """
    groups = sorted(df[group_key].unique())
    rng = np.random.default_rng(seed)
    values = {}
    # Raw-frame point estimand matches the descriptive frame table. Equal-run
    # metrics are reported separately, not mixed into this bootstrap estimand.
    for _ in range(repeats):
        chosen = rng.choice(groups, len(groups), replace=True)
        counts = {g: int((chosen == g).sum()) for g in groups}
        weights = df[group_key].map(counts).to_numpy(float)
        sampled = df.loc[weights > 0]
        fm = frame_metrics(sampled, threshold, weights[weights > 0])
        em = event_metrics(run_rows, run_rows[group_key].map(counts))
        for k in ('average_precision', 'roc_auc', 'brier'):
            if fm[k] is not None:
                values.setdefault(k, []).append(fm[k])
        for k in ('event_recall', 'useful_event_recall', 'false_alerts_per_non_event_run', 'false_alerts_per_eligible_s'):
            if em[k] is not None:
                values.setdefault(k, []).append(em[k])
    intervals = {k: dict(lower=float(np.quantile(v, .025)), upper=float(np.quantile(v, .975)),
                         defined_replicates=len(v), total_replicates=repeats) for k, v in values.items()}
    return dict(cluster_key=group_key, independent_clusters=len(groups), intervals=intervals,
                limitation='Descriptive cluster percentile intervals; sparse-event/2-cluster holdouts cannot establish generalization.')


def describe(df, threshold):
    raw = frame_metrics(df, threshold)
    weights, _ = run_weights(df)
    weighted = frame_metrics(df, threshold, weights)
    return dict(raw=raw, equal_run=weighted)
