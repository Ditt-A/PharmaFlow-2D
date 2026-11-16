"""Causal warning episodes, with future event times used ONLY in retrospective scoring."""
import json
import numpy as np
import pandas as pd


def warning_times(times, scores, threshold, consecutive=2, cooldown_s=.05, sample_s=.005):
    """Trigger at kth high frame, latch until low, respect cooldown; never backdate."""
    if consecutive < 1 or cooldown_s < 0:
        raise ValueError('Invalid alert policy')
    times, scores = np.asarray(times), np.asarray(scores)
    if len(times) != len(scores) or not np.isfinite(times).all() or not np.isfinite(scores).all():
        raise ValueError('Invalid warning sequence')
    if np.any(np.diff(times) <= 0):
        raise ValueError('Timestamps must increase')
    alerts, high, latched, last = [], 0, False, -np.inf
    previous = None
    for t, score in zip(times, scores):
        if previous is not None and t - previous > sample_s * 1.1:
            high, latched = 0, False
        if score < threshold:
            high, latched = 0, False
        else:
            high += 1
            if high >= consecutive and not latched and t - last >= cooldown_s - 1e-12:
                alerts.append(float(t))
                last, latched = t, True
        previous = t
    return alerts


def score_runs(predictions, metadata, horizon, threshold, policy):
    rows = []
    meta = metadata.set_index('run_id')
    for run_id, df in predictions.groupby('run_id', sort=True):
        df = df.sort_values('time_s')
        r = meta.loc[run_id]
        onsets = json.loads(r.event_onsets_json)
        confirmations = json.loads(r.event_confirmations_json)
        onset = float(onsets[0]) if onsets else None
        alerts = warning_times(df.time_s, df.probability, threshold,
                               policy['consecutive_frames'], policy['cooldown_s'], policy['sample_s'])
        valid = [t for t in alerts if onset is not None and 0 < onset - t <= horizon + 1e-10]
        useful = [t for t in valid if onset - t >= policy['minimum_lead_s'] - 1e-10]
        false = [t for t in alerts if t not in valid]
        # Exposure is eligible prediction-grid time, not empty/post-onset duration.
        exposure = float(len(df) * policy['sample_s'])
        rows.append(dict(run_id=run_id, physical_group_id=r.physical_group_id,
                         event=bool(onsets), onset_s=onset,
                         confirmation_s=float(confirmations[0]) if confirmations else None,
                         alerts_json=json.dumps(alerts), false_alert_times_json=json.dumps(false),
                         alert_count=len(alerts), false_alerts=len(false),
                         hit_any=bool(valid), hit_useful=bool(useful),
                         first_valid_warning_s=valid[0] if valid else None,
                         lead_s=onset - valid[0] if valid else None,
                         useful_lead_s=onset - useful[0] if useful else None,
                         redundant_valid_alerts=max(0, len(valid) - 1),
                         exposure_s=exposure, outlet_ratio=float(r.outlet_ratio),
                         packing_family=r.packing_family, friction=float(r.friction),
                         wall_friction=float(r.wall_friction)))
    return pd.DataFrame(rows)


def event_metrics(rows, multiplicity=None):
    w = np.ones(len(rows)) if multiplicity is None else np.asarray(multiplicity, dtype=float)
    event = rows.event.to_numpy(bool)
    events, non_events = float(w[event].sum()), float(w[~event].sum())
    hits = float(np.dot(w, rows.hit_any))
    useful = float(np.dot(w, rows.hit_useful))
    false = float(np.dot(w, rows.false_alerts))
    exposure = float(np.dot(w, rows.exposure_s))
    lead_w = w * rows.hit_any.to_numpy()
    lead = pd.to_numeric(rows.lead_s).fillna(0).to_numpy()
    return dict(independent_runs=int(w.sum()), event_count=int(events), non_event_runs=int(non_events),
                alerted_events=int(hits), useful_alerted_events=int(useful),
                missed_events=int(events - hits), missed_useful_events=int(events - useful),
                event_recall=hits / events if events else None,
                useful_event_recall=useful / events if events else None,
                mean_lead_s=float(np.dot(lead_w, lead) / hits) if hits else None,
                false_alerts=int(false),
                false_alerts_per_non_event_run=float(np.dot(w[~event], rows.false_alerts.to_numpy()[~event]) / non_events) if non_events else None,
                eligible_exposure_s=exposure, false_alerts_per_eligible_s=false / exposure if exposure else None)


def utility(metrics, config):
    """Prespecified train-OOF objective; held-out metrics never enter selection."""
    return ((metrics['useful_event_recall'] or 0)
            - config['false_per_non_event_penalty'] * (metrics['false_alerts_per_non_event_run'] or 0)
            - config['false_per_second_penalty'] * (metrics['false_alerts_per_eligible_s'] or 0))


def choose_threshold(predictions, metadata, horizon, config):
    candidates = []
    for threshold in config['thresholds']:
        em = event_metrics(score_runs(predictions, metadata, horizon, threshold, config['alerts']))
        candidates.append(dict(threshold=threshold, utility=utility(em, config['selection']), **em))
    # Higher threshold breaks exact ties, favoring fewer warnings.
    return max(candidates, key=lambda r: (r['utility'], r['threshold'])), candidates
