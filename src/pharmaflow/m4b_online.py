"""Chronological controller reads observed time/count and current scores, never labels."""
import json
import numpy as np
import pandas as pd


def online_warnings(times, scores, remaining, threshold, policy, gate_open_s=.05, sample_s=.005):
    times, scores, remaining = map(np.asarray, (times, scores, remaining))
    if not (len(times) == len(scores) == len(remaining)) or np.any(np.diff(times) <= 0):
        raise ValueError('Invalid chronology')
    if not np.isfinite(scores).all() or not np.isfinite(times).all() or not np.isfinite(remaining).all():
        raise ValueError('Nonfinite replay inputs')
    high, low, reminders, last, latched, previous = 0, 0, 0, -np.inf, False, None
    alerts = []
    for t, score, count in zip(times, scores, remaining):
        if previous is not None and t-previous > sample_s*1.1:
            high, low, reminders, latched = 0, 0, 0, False
        previous = t
        if t < gate_open_s-1e-12 or count <= 0:
            high, low, reminders, latched = 0, 0, 0, False
            continue
        if score < threshold*policy['low_fraction']:
            low += 1
            if low >= policy['clear_frames']:
                latched, reminders = False, 0
        else:
            low = 0
        high = high+1 if score >= threshold else 0
        refresh = (latched and policy['refresh_s'] is not None and
                   t-last >= policy['refresh_s']-1e-12 and reminders < policy['max_reminders'])
        if high >= policy['high_frames'] and (not latched or refresh) and t-last >= policy['cooldown_s']-1e-12:
            if refresh:
                reminders += 1
            alerts.append(float(t))
            last, latched = t, True
    return alerts


def summarize_runs(predictions, features, labels, metadata, horizon, threshold, policy,
                   mode='online', minimum_lead=.02):
    """Retrospective truth categorizes already-emitted episodes; it never gates online input."""
    if mode not in ('online', 'eligible'):
        raise ValueError('Unknown replay mode')
    rows = []
    meta = metadata.set_index('run_id')
    lab = labels.loc[labels.horizon_s == horizon]
    for run_id, scores in predictions.groupby('run_id', sort=True):
        scores = scores.sort_values('frame_index')
        f = features.loc[features.run_id == run_id].sort_values('frame_index')
        truth = lab.loc[lab.run_id == run_id].sort_values('frame_index')
        if list(scores.frame_index) != list(f.frame_index) or list(truth.frame_index) != list(f.frame_index):
            raise ValueError('Replay requires the full chronological run, no oracle cropping')
        selected = np.ones(len(f), dtype=bool) if mode == 'online' else (truth.label_status == 'eligible').to_numpy()
        gate = float(meta.loc[run_id].get('gate_open_s', .05))
        alerts = online_warnings(f.time_s.to_numpy()[selected], scores.probability.to_numpy()[selected],
                                 f.remaining_count.to_numpy()[selected], threshold, policy, gate)
        onsets = json.loads(meta.loc[run_id].event_onsets_json)
        onset = float(onsets[0]) if onsets else None
        valid, useful, false, late, unknown = [], [], [], [], []
        # Truth lookup is strictly after replay; nullable future remains unscored.
        status = {int(r.frame_index):r.label_status for r in truth.itertuples()}
        index_at_time = dict(zip(f.time_s, f.frame_index))
        for t in alerts:
            lead = onset-t if onset is not None else None
            if lead is not None and 0 < lead <= horizon+1e-10:
                valid.append(t)
                if lead >= minimum_lead-1e-10:
                    useful.append(t)
            elif onset is not None and t >= onset:
                late.append(t)
                false.append(t)  # conservative false forecast of a first event already begun
            elif status[int(index_at_time[t])] == 'right_censored':
                unknown.append(t)
            else:
                false.append(t)
        dt = float(meta.loc[run_id].sample_interval_s)
        operating = (f.time_s.to_numpy() >= gate-1e-12) & (f.remaining_count.to_numpy() > 0)
        r = meta.loc[run_id]
        rows.append(dict(run_id=run_id, physical_group_id=r.physical_group_id, event=bool(onsets),
                         censored=bool(r.censored_run), hit_any=bool(valid), hit_useful=bool(useful),
                         first_valid_warning_s=valid[0] if valid else None,
                         lead_s=onset-valid[0] if valid else None, onset_s=onset,
                         alerts_json=json.dumps(alerts), false_alerts_json=json.dumps(false),
                         alert_count=len(alerts), false_forecasts=len(false), post_onset_alerts=len(late),
                         unscorable_alerts=len(unknown), operating_s=float(operating.sum()*dt),
                         observed_s=float(max(0, f.time_s.iloc[-1]-gate)),
                         eligible_s=float((truth.label_status == 'eligible').sum()*dt),
                         outlet_ratio=float(r.outlet_ratio), packing_family=r.packing_family,
                         friction=float(r.friction), wall_friction=float(r.wall_friction),
                         wall_angle_deg=float(r.wall_angle_deg),
                         temporary_gap_count=int(r.get('temporary_gap_count', 0) if pd.notna(r.get('temporary_gap_count', 0)) else 0)))
    return pd.DataFrame(rows)


def summary(rows, weights=None):
    w = np.ones(len(rows)) if weights is None else np.asarray(weights, dtype=float)
    event, censored = rows.event.to_numpy(bool), rows.censored.to_numpy(bool)
    ev = float(w[event].sum())
    non_event = (~event) & (~censored)
    n = float(w.sum())
    false = float(np.dot(w, rows.false_forecasts))
    op, obs = float(np.dot(w, rows.operating_s)), float(np.dot(w, rows.observed_s))
    hits, useful = float(np.dot(w, rows.hit_any)), float(np.dot(w, rows.hit_useful))
    non_n = float(w[non_event].sum())
    return dict(independent_runs=int(n), events=int(ev), censored_runs=int(w[censored].sum()),
                any_hits=int(hits), useful_hits=int(useful), missed_useful_events=int(ev-useful),
                event_recall=hits/ev if ev else None, useful_event_recall=useful/ev if ev else None,
                false_forecasts=int(false), post_onset_alerts=int(np.dot(w, rows.post_onset_alerts)),
                unscorable_alerts=int(np.dot(w, rows.unscorable_alerts)),
                false_per_run=false/n if n else None, false_per_operating_s=false/op if op else None,
                false_per_observed_s=false/obs if obs else None,
                false_per_non_event_run=float(np.dot(w[non_event], rows.false_forecasts.to_numpy()[non_event])/non_n) if non_n else None,
                operating_s=op, observed_s=obs,
                mean_lead_s=float(np.dot(w, pd.to_numeric(rows.lead_s).fillna(0).to_numpy(float))/hits) if hits else None)


def utility(metrics, config):
    return ((metrics['useful_event_recall'] or 0)
            - config['false_per_non_event_run_penalty']*(metrics['false_per_non_event_run'] or 0)
            - config['false_per_operating_second_penalty']*(metrics['false_per_operating_s'] or 0)
            - config['false_per_run_penalty']*(metrics['false_per_run'] or 0))


def select_policy(predictions, tables, horizon, config):
    trace = []
    for policy in config['policies']:
        for threshold in config['thresholds']:
            rows = summarize_runs(predictions, tables['temporal_features'], tables['event_labels'],
                                  tables['run_metadata'], horizon, threshold, policy)
            metrics = summary(rows)
            trace.append(dict(threshold=threshold, policy=policy, utility=utility(metrics, config['selection']), **metrics))
    return max(trace, key=lambda r:(r['utility'], -config['policies'].index(r['policy']), r['threshold'])), trace
