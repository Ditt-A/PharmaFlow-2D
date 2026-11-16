"""Finite-duration arch events and first-onset early-warning targets, no ML."""
import numpy as np

PROTOCOL_VERSION='first-persistent-arch-v1'
DEFAULT_PROTOCOL=dict(persistence_s=.4,stationary_speed_m_s=.003,gate_buffer_s=.02,minimum_remaining=2)


def spans(graph):
    """The last two graph nodes are the left and right finite hopper walls."""
    n=len(graph)
    reached=np.zeros(n,dtype=bool);reached[-2]=True
    for _ in range(n):
        expanded=reached | np.any(graph & reached[:,None],axis=0)
        if np.array_equal(expanded,reached):break
        reached=expanded
    return bool(reached[-1])


def detect_events(trace,gate_open_s,protocol=None):
    p=dict(DEFAULT_PROTOCOL,**(protocol or {}))
    if p['persistence_s']<=0 or p['stationary_speed_m_s']<=0:raise ValueError('invalid persistence/speed')
    time=np.asarray(trace['time_s'])
    if len(time)<2 or np.any(np.diff(time)<=0):raise ValueError('strictly increasing timestamps required')
    count=np.asarray(trace['discharged_count'])
    instantaneous=trace['contact_graph']
    intervals=trace.get('interval_common_contacts',instantaneous)
    speed=np.asarray(trace['near_max_speed_m_s'])
    interval_speed=trace.get('interval_max_near_speed_m_s',speed)
    remaining=np.asarray(trace['remaining_count'])
    interval_remaining=trace.get('interval_min_remaining',remaining)
    eligible=(time>=gate_open_s+p['gate_buffer_s']-1e-12)&(remaining>=p['minimum_remaining'])&(speed<=p['stationary_speed_m_s'])
    events=[];i=0
    while i<len(time):
        if not eligible[i] or not spans(instantaneous[i]):i+=1;continue
        common=instantaneous[i].astype(bool).copy();confirmation=None;j=i+1
        while j<len(time):
            if (not eligible[j] or count[j]!=count[i] or interval_speed[j]>p['stationary_speed_m_s'] or interval_remaining[j]<p['minimum_remaining']):break
            common &= intervals[j]
            if not spans(common):break
            if confirmation is None and time[j]-time[i]>=p['persistence_s']-1e-12:
                confirmation=j
            j+=1
        if confirmation is not None:
            events.append(dict(event_id=len(events),onset_time_s=float(time[i]),confirmation_time_s=float(time[confirmation]),
                               last_supported_time_s=float(time[j-1]),end_time_s=float(time[j]) if j<len(time) else None,
                               observed_duration_s=float(time[j-1]-time[i]),persistent_to_observation_end=j==len(time),
                               resumed_crossing_after_event=bool(np.any(count[j:]>count[i])) if j<len(time) else False,
                               onset_remaining_particles=int(remaining[i]),persistence_s=p['persistence_s'],
                               onset_frame=int(i),confirmation_frame=int(confirmation),permanent_clogging=False))
            # This dataset is a first-event prediction benchmark. Do not count
            # contact-path rewiring without resumed discharge as another onset.
            return events
        else:i+=1
    return events


def label_frames(trace,events,horizons=(.05,.10),gate_open_s=.05,protocol=None,numerically_valid=True):
    p=dict(DEFAULT_PROTOCOL,**(protocol or {}));time=np.asarray(trace['time_s'])
    first=events[0] if events else None
    rows=[]
    for frame,t in enumerate(time):
        for h in horizons:
            if h<=0:raise ValueError('horizon must be positive')
            target=None;reason=None
            if not numerically_valid:status='numerical_failure';reason='invalid_physics'
            elif t<gate_open_s-1e-12:status='pre_release';reason='gate_closed'
            elif trace['remaining_count'][frame]==0:status='empty';reason='hopper_empty'
            elif first is not None and t>=first['onset_time_s']-1e-12:status='post_onset';reason='first_event_already_begun'
            elif first is not None and first['onset_time_s']<=t+h+1e-12:
                status='eligible';target=1
            elif t+h+p['persistence_s']<=time[-1]+1e-12:
                status='eligible';target=0
            else:status='right_censored';reason='insufficient_horizon_plus_confirmation_observation'
            rows.append(dict(frame_index=frame,time_s=float(t),horizon_s=float(h),target=target,label_status=status,
                             censoring_reason=reason,event_onset_time_s=first['onset_time_s'] if first else None,
                             event_confirmation_time_s=first['confirmation_time_s'] if first else None,
                             persistence_s=p['persistence_s'],label_protocol=PROTOCOL_VERSION))
    return rows
