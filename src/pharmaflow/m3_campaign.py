"""Budgeted DEM generation with independent packings, long observation and checksums."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from . import __version__
from .dem import DEMSystem
from .run import save_run,hardware_info
from .validation import PhysicsMonitor
from .m3_packing import physical_config,make_packing
from .m3_features import observations
from .m3_events import detect_events,DEFAULT_PROTOCOL


def digest_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def solver_hash():
    """Exclude downstream label/feature processing so relabeling need not rerun DEM."""
    names=('__init__.py','config.py','contact.py','dem.py','geometry.py','neighbors.py','taichi_backend.py',
           'validation.py','m3_packing.py','m3_campaign.py')
    h=hashlib.sha256()
    for name in names:
        h.update(name.encode());h.update(Path(__file__).with_name(name).read_bytes())
    return h.hexdigest()


def stable_id(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class M3Monitor(PhysicsMonitor):
    def __init__(self,config):
        super().__init__(config)
        self.common=None;self.interval_max_speed=0.;self.interval_min_remaining=config.n_particles
        self.records=[];self.graphs=[];self.interval_graphs=[];self.interval_speeds=[];self.interval_remaining=[]

    def contact_pairs(self,system,i,j):
        s=system.state;n=len(s.mass)
        near=s.active & (s.position[:,1]>=0)&(s.position[:,1]<.025)
        graph=np.zeros((n+2,n+2),dtype=bool)
        pp=j>=0
        a,b=i[pp],j[pp]
        keep=near[a]&near[b]
        graph[a[keep],b[keep]]=True;graph[b[keep],a[keep]]=True
        for wall in (0,1):
            a=i[j==-wall-1];a=a[near[a]]
            graph[a,n+wall]=True;graph[n+wall,a]=True
        self.common=graph if self.common is None else self.common & graph

    def after_step(self,system,force,torque):
        super().after_step(system,force,torque)
        s=system.state
        remaining=s.active & (s.position[:,1]>=0)
        near=remaining & (s.position[:,1]<.025)
        value=float(np.max(np.linalg.norm(s.velocity[near],axis=1))) if near.any() else 0.
        self.interval_max_speed=max(self.interval_max_speed,value)
        self.interval_min_remaining=min(self.interval_min_remaining,int(remaining.sum()))

    def sample(self,system):
        super().sample(system)
        s=system.state
        row,graph=observations(s.position,s.velocity,s.radius,s.active,self.config,system.time_s)
        self.records.append(row);self.graphs.append(graph)
        self.interval_graphs.append(graph.copy() if self.common is None else self.common & graph)
        self.interval_speeds.append(max(self.interval_max_speed,row['near_max_speed_m_s']))
        self.interval_remaining.append(min(self.interval_min_remaining,row['remaining_count']))
        self.common=None;self.interval_max_speed=0.;self.interval_min_remaining=self.config.n_particles

    def arrays(self):
        result=super().arrays()
        result.update({k:np.asarray([r[k] for r in self.records]) for k in self.records[0]})
        result.update(contact_graph=np.asarray(self.graphs,dtype=bool),
                      interval_common_contacts=np.asarray(self.interval_graphs,dtype=bool),
                      interval_max_near_speed_m_s=np.asarray(self.interval_speeds),
                      interval_min_remaining=np.asarray(self.interval_remaining))
        return result


def simulate_task(task):
    start=time.perf_counter();c=physical_config(task['physical'],task['numerical'],task['seed'])
    state,initial_hash=make_packing(c,task['packing_family'])
    system=DEMSystem(c,state);monitor=M3Monitor(c);system.monitor=monitor
    interval=task['sample_interval_s'];every=round(interval/c.dt_s)
    if every<1 or not np.isclose(every*c.dt_s,interval,atol=1e-12,rtol=0):raise ValueError('sample interval must align with dt')
    arrays={k:[] for k in ('time_s','position_m','velocity_m_s','angle_rad','omega_rad_s','active','discharged_count')}
    def sample():
        arrays['time_s'].append(system.time_s)
        for key,value in (('position_m',state.position),('velocity_m_s',state.velocity),('angle_rad',state.angle),('omega_rad_s',state.omega),('active',state.active)):
            arrays[key].append(value.copy())
        arrays['discharged_count'].append(int(np.isfinite(system.crossing_time).sum()))
        monitor.sample(system)
    def assembled():
        result={k:np.asarray(v) for k,v in arrays.items()};result.update(monitor.arrays());return result
    sample();integrated=0;fast_forward=0
    def advance_to(duration):
        nonlocal integrated,fast_forward
        target=round(duration/c.dt_s)
        if not np.isclose(target*c.dt_s,duration,atol=1e-12,rtol=0) or target%every:raise ValueError('duration must align with samples')
        while system.step_index<target:
            if not state.active.any():
                jump=min(every-(system.step_index%every),target-system.step_index)
                system.step_index+=jump;fast_forward+=jump
            else:
                system.step();integrated+=1
            if system.step_index%every==0:sample()
    advance_to(task['duration_s'])
    preliminary=assembled();events=detect_events(preliminary,c.gate_open_time_s,task['protocol'])
    continued=False
    if task.get('max_duration_s',task['duration_s'])>task['duration_s'] and not events and preliminary['remaining_count'][-1]>0:
        advance_to(task['max_duration_s']);continued=True
    history=system.history.copy();system.monitor=None;system.forces();system.history=history
    result=assembled()
    result.update(radius_m=state.radius.copy(),mass_kg=state.mass.copy(),particle_id=np.arange(c.n_particles),crossing_time_s=system.crossing_time.copy())
    for key in ('position_m','velocity_m_s','angle_rad','omega_rad_s'):
        if not np.isfinite(result[key]).all():raise RuntimeError('nonfinite exported '+key)
    if monitor.leak_samples:raise RuntimeError('boundary leak samples detected')
    if np.any((~state.active)&np.isnan(system.crossing_time)):raise RuntimeError('removal without outlet crossing')
    events=detect_events(result,c.gate_open_time_s,task['protocol'])
    count=int(np.isfinite(system.crossing_time).sum());remaining=int(result['remaining_count'][-1])
    gaps=np.diff(system.crossing_time[np.argsort(np.nan_to_num(system.crossing_time,nan=np.inf))])
    pause=bool(np.any(gaps[np.isfinite(gaps)]>=.06))
    if remaining==0 and count==c.n_particles:flow='completed_discharge'
    elif events and events[-1]['persistent_to_observation_end']:flow='persistent_arch_observed'
    elif pause:flow='intermittent_flow'
    elif count>=3 and result['time_s'][-1]-np.nanmax(system.crossing_time)<.06:flow='continuous_flow'
    else:flow='unresolved_right_censored'
    fingerprint=hashlib.sha256()
    for key in sorted(result):fingerprint.update(key.encode());fingerprint.update(result[key].tobytes())
    metadata=dict(task,config=asdict(c),solver_version=__version__,solver_source_sha256=solver_hash(),
                  initial_state_sha256=initial_hash,packing_id=stable_id(dict(family=task['packing_family'],seed=task['seed'],initial_hash=initial_hash))[:20],
                  observation_duration_s=system.time_s,continued=continued,integrated_steps=integrated,
                  absorbing_empty_fast_forward_steps=fast_forward,trajectory_sha256=fingerprint.hexdigest(),
                  runtime_s=time.perf_counter()-start,hardware=hardware_info(),events=events,flow_state=flow,
                  censored_run=not events and remaining>0,permanent_clogging_claimed=False,
                  status='ok',numerical_valid=True,checks=dict(max_overlap_over_radius=system.max_overlap_ratio,
                  overlap_limit=c.max_overlap_ratio,max_step_over_radius=system.max_step_ratio,
                  particle_conservation=int(state.active.sum())+int((~state.active).sum())==c.n_particles,
                  final_discharged=count,final_remaining=remaining,wall_tunneling=False),physics=monitor.summary())
    return result,metadata


def run_task(task,root):
    root=Path(root);folder=root/task['phase']/task['run_id'];folder.mkdir(parents=True,exist_ok=True)
    path=folder/'trajectory.npz';summary=folder/'run.json'
    signature=stable_id(dict(task=task,solver=solver_hash()))
    if summary.exists():
        old=json.loads(summary.read_text())
        if old.get('signature')!=signature:raise RuntimeError('Existing run signature differs; use a new campaign/run ID instead of overwriting')
        if old['status']=='ok' and (not path.exists() or digest_file(path)!=old['npz_sha256']):raise RuntimeError('Cached trajectory checksum mismatch')
        return old
    started=time.perf_counter()
    try:
        arrays,meta=simulate_task(task)
        meta['signature']=signature;meta['created_utc']=datetime.now(timezone.utc).isoformat()
        save_run(path,arrays,meta)
        meta['npz_sha256']=digest_file(path);meta['trajectory_path']=str(path)
    except Exception as error:
        meta=dict(task,signature=signature,status='failed',numerical_valid=False,
                  error=f'{type(error).__name__}: {error}',runtime_s=time.perf_counter()-started,
                  solver_version=__version__,solver_source_sha256=solver_hash(),created_utc=datetime.now(timezone.utc).isoformat())
        failure=root/'failures'/(task['run_id']+'.json');failure.parent.mkdir(parents=True,exist_ok=True)
        failure.write_text(json.dumps(meta,indent=2,allow_nan=False)+'\n')
    tmp=summary.with_suffix('.tmp');tmp.write_text(json.dumps(meta,indent=2,allow_nan=False)+'\n');tmp.replace(summary)
    return meta


def tasks_from_plan(plan):
    tasks=[]
    for case in plan['cases']:
        config_id=stable_id(case['physical'])[:16]
        for replicate in plan['replicates']:
            run_id=f"{plan['phase']}_{config_id}_{replicate['packing_family']}_s{replicate['seed']}"
            allow=replicate['packing_family']=='random_sequential' and case.get('allow_continuation',False)
            tasks.append(dict(run_id=run_id,configuration_id=config_id,case_name=case['name'],phase=plan['phase'],
                              physical=case['physical'],numerical=plan['numerical'],seed=replicate['seed'],packing_family=replicate['packing_family'],
                              duration_s=plan['duration_s'],max_duration_s=plan.get('max_duration_s',plan['duration_s']) if allow else plan['duration_s'],
                              sample_interval_s=plan['sample_interval_s'],protocol=dict(DEFAULT_PROTOCOL,**plan.get('protocol',{}))))
    if len(tasks)>plan['max_attempts'] or len({t['run_id'] for t in tasks})!=len(tasks):raise ValueError('attempt budget or duplicate run IDs')
    if sum(t['max_duration_s'] for t in tasks)>plan['max_simulated_seconds']+1e-12:raise ValueError('physical-time campaign budget exceeded')
    return tasks


def run_campaign(plan_path,root,jobs=1):
    plan=json.loads(Path(plan_path).read_text());tasks=tasks_from_plan(plan)
    root=Path(root);(root/'manifests').mkdir(parents=True,exist_ok=True)
    manifest=root/'manifests'/(plan['phase']+'_campaign.json')
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['plan']!=plan:raise RuntimeError('Campaign plan changed; preserve the prior campaign and choose a new phase')
    manifest.write_text(json.dumps(dict(plan=plan,state='running',attempt_budget=plan['max_attempts']),indent=2)+'\n')
    records=[]
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures=[executor.submit(run_task,t,str(root)) for t in tasks]
        for future in as_completed(futures):
            result=future.result();records.append(result)
            print(result['run_id'],result['status'],result.get('flow_state'),len(result.get('events',[])),flush=True)
    report=dict(plan=plan,state='complete',attempt_budget=plan['max_attempts'],records=sorted(records,key=lambda r:r['run_id']))
    manifest.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report
