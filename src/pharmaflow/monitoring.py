"""Chronological warning state; only current observations/scores enter the controller."""
from pathlib import Path
import json
import numpy as np
from .m4_data import digest


def physics_score(frame):
    """The unchanged frozen M4A rule, with no learned coefficients or calibration."""
    if frame['near_count'] < 2 or frame['remaining_count'] < 2:
        return 0.
    return float(.45*frame['near_stationary_fraction']+.35*frame['spanning_arch_now']
                 +.20*np.exp(-frame['near_speed_mean_m_s']/.02))


class AlertMonitor:
    def __init__(self, threshold, policy, gate_open_s=.05, sample_s=.005):
        self.threshold, self.policy = threshold, dict(policy)
        self.gate_open_s, self.sample_s = gate_open_s, sample_s
        self.high = self.low = self.reminders = 0
        self.last = -np.inf
        self.latched = False
        self.previous = None
        self.log = []

    def observe(self, time_s, score, remaining_count):
        t, score = float(time_s), float(score)
        if not np.isfinite([t,score,remaining_count]).all() or not 0 <= score <= 1:
            raise ValueError('Invalid current warning observation')
        if self.previous is not None and t <= self.previous:
            raise ValueError('Warning times must increase')
        p = self.policy
        if self.previous is not None and t-self.previous > self.sample_s*1.1:
            self.high, self.low, self.reminders, self.latched = 0, 0, 0, False
        self.previous = t
        issued, reminder = False, False
        if t < self.gate_open_s-1e-12 or remaining_count <= 0:
            self.high, self.low, self.reminders, self.latched = 0, 0, 0, False
        else:
            if score < self.threshold*p['low_fraction']:
                self.low += 1
                if self.low >= p['clear_frames']:
                    self.latched, self.reminders = False, 0
            else:
                self.low = 0
            self.high = self.high+1 if score >= self.threshold else 0
            reminder = bool(self.latched and p['refresh_s'] is not None and
                            t-self.last >= p['refresh_s']-1e-12 and self.reminders < p['max_reminders'])
            if self.high >= p['high_frames'] and (not self.latched or reminder) and t-self.last >= p['cooldown_s']-1e-12:
                if reminder:
                    self.reminders += 1
                self.last, self.latched, issued = t, True, True
                self.log.append(dict(time_s=t, score=score, reminder=reminder, notification=len(self.log)+1))
        return dict(alert_issued=issued, alert_active=bool(self.latched), reminder=bool(issued and reminder),
                    notifications=len(self.log), score=score)


def frozen_specs(root=Path('.')):
    path = Path(root)/'outputs/metrics/m4b/model_and_policy_freeze.json'
    if not path.exists():
        path = Path(root)/'docs/results/m4b/model_and_policy_freeze.json'
    frozen = json.loads(path.read_text())
    rule = next(c for c in frozen['candidates'] if c['candidate_id']=='frozen_configuration_holdout_h100_baseline_rule')
    ml = next(c for c in frozen['candidates'] if c['candidate_id']==frozen['selected']['0.1']['ml'])
    if rule['threshold'] != .85 or rule['policy']['name'] != 'legacy_m4a':
        raise ValueError('Reference rule must remain the original frozen M4A policy')
    return dict(rule=rule, ml=ml)


def frozen_ml_scores(features, specification, root=Path('.')):
    import joblib
    from .m4b_models import predict
    path = Path(root)/specification['artifact_path']
    if digest(path) != specification['artifact_sha256']:
        raise ValueError('Frozen ML artifact checksum mismatch')
    return predict(joblib.load(path), features)


def monitor_features(features, discharged_counts, specs, ml_scores=None, gate_open_s=.05, sample_s=.005):
    """No labels, onset, confirmation, final outcome or crossing-time vector accepted."""
    from .operational_events import OperationalMonitor
    if len(features) != len(discharged_counts) or (ml_scores is not None and len(ml_scores)!=len(features)):
        raise ValueError('Monitoring observations must align')
    flow = OperationalMonitor(gate_open_s)
    rule = AlertMonitor(specs['rule']['threshold'],specs['rule']['policy'],gate_open_s,sample_s)
    ml = AlertMonitor(specs['ml']['threshold'],specs['ml']['policy'],gate_open_s,sample_s)
    result=[]
    for index, frame in enumerate(features.to_dict('records')):
        t, remaining = frame['time_s'], frame['remaining_count']
        observation=flow.observe(t,int(discharged_counts[index]),int(remaining))
        rule_state=rule.observe(t,physics_score(frame),remaining)
        ml_state=ml.observe(t,float(ml_scores[index]),remaining) if ml_scores is not None else None
        result.append(dict(**observation,rule_score=rule_state['score'],rule_alert=rule_state['alert_issued'],
                           rule_active=rule_state['alert_active'],ml_score=ml_state['score'] if ml_state else None,
                           ml_alert=ml_state['alert_issued'] if ml_state else False,
                           ml_active=ml_state['alert_active'] if ml_state else False))
    return result,dict(rule=rule.log,ml=ml.log,resumptions=flow.resumptions)
