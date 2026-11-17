"""Versioned descriptive taxonomy, separate from immutable M3 prediction labels."""
from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class OperationalDefinition:
    version: str = 'operational-observation-v1'
    flow_window_s: float = .10
    minimum_crossings: int = 5
    minimum_crossing_frames: int = 3
    maximum_flow_gap_s: float = .04
    pause_s: float = .05


class OperationalMonitor:
    """Consumes current time, observed crossing count and current retained count only."""
    def __init__(self, gate_open_s=.05, definition=None):
        self.definition = definition or OperationalDefinition()
        self.gate_open_s = gate_open_s
        self.previous_time = None
        self.previous_count = 0
        self.crossing_frames = deque()
        self.last_crossing_s = None
        self.established_at_last_crossing = False
        self.pause_start_s = None
        self.resumptions = []

    def observe(self, time_s, discharged_count, remaining_count):
        d = self.definition
        if not all(math.isfinite(float(v)) for v in (time_s, discharged_count, remaining_count)):
            raise ValueError('Nonfinite observation')
        t, count, remaining = float(time_s), int(discharged_count), int(remaining_count)
        if t < 0 or count != discharged_count or remaining != remaining_count or count < self.previous_count or remaining < 0:
            raise ValueError('Invalid observed counts/time')
        if self.previous_time is not None and t <= self.previous_time:
            raise ValueError('Observation times must increase')
        change = count - self.previous_count
        previous_crossing = self.last_crossing_s
        previous_established = self.established_at_last_crossing
        if change:
            self.crossing_frames.append((t, change))
        start = min(t,max(self.gate_open_s, t-d.flow_window_s))
        while self.crossing_frames and self.crossing_frames[0][0] <= start+1e-12:
            self.crossing_frames.popleft()
        times = [start] + [s for s, _ in self.crossing_frames] + [t]
        max_gap = max((b-a for a,b in zip(times,times[1:])), default=0.)
        crossing_total = sum(n for _,n in self.crossing_frames)
        established = (t-self.gate_open_s >= d.flow_window_s-1e-12 and remaining > 0
                       and crossing_total >= d.minimum_crossings
                       and len(self.crossing_frames) >= d.minimum_crossing_frames
                       and max_gap <= d.maximum_flow_gap_s+1e-12)
        resumed = False
        if change:
            if self.pause_start_s is not None and previous_crossing is not None:
                self.resumptions.append(dict(kind='temporary_interruption', gap_start_s=previous_crossing,
                    pause_observed_s=self.pause_start_s, resume_observed_s=t,
                    observed_gap_s=t-previous_crossing, preceding_established_flow=bool(previous_established)))
                resumed = True
            self.last_crossing_s = t
            self.established_at_last_crossing = bool(established)
            self.pause_start_s = None
        age = t-self.last_crossing_s if self.last_crossing_s is not None else None
        paused = bool(remaining > 0 and age is not None and age >= d.pause_s-1e-12)
        if paused and self.pause_start_s is None:
            self.pause_start_s = t
        if remaining == 0:
            self.pause_start_s = None
        if t < self.gate_open_s-1e-12:
            state = 'gate_closed'
        elif remaining == 0:
            state = 'no_particle_remaining'
        elif count == 0:
            state = 'awaiting_first_discharge'
        elif paused:
            state = 'pause_after_established_flow' if self.established_at_last_crossing else 'pause_after_discharge'
        elif established:
            state = 'established_flow_observed'
        else:
            state = 'discharge_observed_not_established'
        self.previous_time, self.previous_count = t, count
        return dict(time_s=t, discharged_count=count, remaining_count=remaining,
                    observed_state=state, crossing_increment=change, has_observed_discharge=count>0,
                    flow_established_now=bool(established),
                    established_at_last_crossing=bool(self.established_at_last_crossing),
                    pause_observed=paused, pause_observed_s=self.pause_start_s,
                    seconds_since_observed_crossing=age, resumed_now=resumed,
                    no_particle_remaining=remaining==0)


def observe_history(times, counts, remaining, gate_open_s=.05, definition=None):
    if not len(times) or not (len(times)==len(counts)==len(remaining)):
        raise ValueError('Aligned nonempty observations required')
    monitor = OperationalMonitor(gate_open_s, definition)
    rows = [monitor.observe(t,n,r) for t,n,r in zip(times,counts,remaining)]
    return rows, monitor.resumptions


def annotate_outcomes(observed_rows, confirmed_arches, numerical_valid=True):
    """Future-confirmed outcomes ONLY for research analysis, never online state."""
    arches = []
    for event in confirmed_arches:
        onset = float(event['onset_time_s'])
        index = next((i for i,r in enumerate(observed_rows) if abs(r['time_s']-onset)<1e-10), None)
        if index is None:
            raise ValueError('Confirmed onset does not align with observed trajectory')
        row = observed_rows[index]
        preceding = observed_rows[index-1] if index else None
        established = bool(preceding and preceding['established_at_last_crossing'])
        startup = row['discharged_count']==0
        arches.append(dict(kind='startup_blockage' if startup else 'post_discharge_arch',
                           onset_time_s=onset, confirmation_time_s=float(event['confirmation_time_s']),
                           prior_observed_crossings=row['discharged_count'],
                           crossing_in_onset_frame=bool(row['crossing_increment']),
                           established_flow_interruption=bool(not startup and established)))
    last = observed_rows[-1]
    completed = bool(last['no_particle_remaining'])
    unresolved = bool(numerical_valid and not completed and not arches)
    return dict(taxonomy_version='operational-observation-v1', arches=arches,
                startup_blockage=sum(a['kind']=='startup_blockage' for a in arches),
                post_discharge_arch=sum(a['kind']=='post_discharge_arch' for a in arches),
                established_flow_arch=sum(a['established_flow_interruption'] for a in arches),
                completed_discharge=completed, unresolved_or_censored=unresolved,
                numerical_failure=not numerical_valid,
                interpretation='Descriptive outcomes; established-flow arches are a subset of post-discharge arches.')
