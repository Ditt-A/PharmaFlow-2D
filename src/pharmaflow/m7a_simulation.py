"""Passive fixed-grain diagnostics and bounded numerical-analogue trajectories."""
from dataclasses import asdict
import hashlib
import math
import time
import numpy as np
from .fixed_grain import FixedGrainSystem,obstacle_at_outlet,mixture_packing
from .config import HopperConfig
from .geometry import segment_contacts
from .validation import PhysicsMonitor
from .m3_events import detect_events

LABEL='Uncalibrated 2D DEM — exploratory fixed-grain numerical analogue.'


def near_outlet(system):
    s,c=system.state,system.config
    return s.active&(s.position[:,1]>=0)&(s.position[:,1]<=2*c.outlet_width_m)&(abs(s.position[:,0])<c.outlet_width_m/2+5*float(s.radius.max()))


def contact_graph(system,pairs=None):
    """Last two nodes are outlet-left/right floor supports; extra node is obstacle.

    Passive geometry query, never advances contact memory or forces.
    """
    s,c=system.state,system.config;n=len(s.mass);g=np.zeros((n+3,n+3),bool);near=near_outlet(system)
    if pairs is None:
        i,j=np.triu_indices(n,1)
        keep=near[i]&near[j]&(np.linalg.norm(s.position[i]-s.position[j],axis=1)<s.radius[i]+s.radius[j])
        i,j=i[keep],j[keep]
        wd,_,_=segment_contacts(s.position,system.walls)
        wi,wall=np.nonzero((wd<s.radius[:,None])&near[:,None])
    else:
        a,b=pairs;pp=b>=0;i,j=a[pp],b[pp]
        keep=near[i]&near[j];i,j=i[keep],j[keep]
        wi=a[~pp];wall=-b[~pp]-1;keep=near[wi];wi,wall=wi[keep],wall[keep]
    g[i,j]=True;g[j,i]=True
    for anchor in (0,1):
        ids=wi[wall==anchor];g[ids,n+1+anchor]=True;g[n+1+anchor,ids]=True
    if system.obstacle is not None:
        ids=system.obstacle_geometry()[0];ids=ids[near[ids]]
        g[ids,n]=True;g[n,ids]=True
        x,y=system.obstacle.center_m;r=system.obstacle.radius_m
        if abs(y-r)<1e-12 and abs(x)>=c.outlet_width_m/2:
            anchor=n+1 if x<0 else n+2;g[n,anchor]=g[anchor,n]=True
    return g


class FixedGrainMonitor(PhysicsMonitor):
    def __init__(self,config):
        super().__init__(config)
        self.current_graph=None;self.common=None;self.interval_speed=0.;self.interval_remaining=config.n_particles
        self.graphs=[];self.commons=[];self.speeds=[];self.remaining=[];self.interval_speeds=[];self.interval_counts=[]
        self.obstacle_steps=0;self.max_reaction=0.

    def contact_pairs(self,system,i,j):self.current_graph=contact_graph(system,(i,j))

    def obstacle_contacts(self,system,overlap,radius,fn,vn,tangential_power):
        self.hist+=np.histogram(overlap/radius,self.bins)[0]
        self.max_force=max(self.max_force,float(fn.max()))
        self.normal_loss+=float(system.config.normal_damping_kg_s*np.sum(np.minimum(vn,0)**2)*system.config.dt_s)
        self.tangential_work+=float(np.sum(tangential_power)*system.config.dt_s)
        self.obstacle_steps+=len(overlap)

    def after_step(self,system,force,torque):
        super().after_step(system,force,torque)
        # Contacts are pre-integration, every-step samples. Their intersection is
        # deliberately conservative; instantaneous sample graphs use current positions.
        graph=self.current_graph
        self.common=graph if self.common is None else self.common&graph
        s=system.state;near=near_outlet(system)
        self.interval_speed=max(self.interval_speed,float(np.linalg.norm(s.velocity[near],axis=1).max()) if near.any() else 0.)
        self.interval_remaining=min(self.interval_remaining,int(np.sum(s.active&(s.position[:,1]>=0))))
        self.max_reaction=max(self.max_reaction,float(np.linalg.norm(system.obstacle_reaction_force_n)))

    def sample(self,system):
        s,c=system.state,system.config;near=near_outlet(system);graph=contact_graph(system)
        self.graphs.append(graph);self.commons.append(graph if self.common is None else self.common.copy())
        speed=float(np.linalg.norm(s.velocity[near],axis=1).max()) if near.any() else 0.
        rem=int(np.sum(s.active&(s.position[:,1]>=0)))
        self.speeds.append(speed);self.remaining.append(rem)
        self.interval_speeds.append(self.interval_speed);self.interval_counts.append(self.interval_remaining)
        self.common=None;self.interval_speed=0.;self.interval_remaining=rem
        active=s.active
        kinetic=float(np.sum(.5*s.mass[active]*np.sum(s.velocity[active]**2,axis=1)+.5*s.inertia[active]*s.omega[active]**2))
        potential=float(np.sum(s.mass[active]*c.gravity_m_s2*s.position[active,1]))
        i,j=np.triu_indices(len(s.mass),1)
        ov=s.radius[i]+s.radius[j]-np.linalg.norm(s.position[i]-s.position[j],axis=1)
        keep=active[i]&active[j]&(ov>0);overlap2=float(np.sum(ov[keep]**2))
        wd,_,_=segment_contacts(s.position,system.walls)
        wi,wall=np.nonzero((wd<s.radius[:,None])&active[:,None])
        overlap2+=float(np.sum((s.radius[wi]-wd[wi,wall])**2))
        overlap2+=float(np.sum(system.obstacle_geometry()[1]**2))
        tangent2=sum(float(np.dot(v,v)) for v in (*system.history.values(),*system.obstacle_history.values()))
        self.leak_samples+=int(np.sum(active&(s.position[:,1]>0)&(abs(s.position[:,0])>c.width_m/2+1e-12)))
        self.series.append(dict(kinetic_j=kinetic,gravity_j=potential,normal_spring_j=.5*c.normal_stiffness_n_m*overlap2,
            tangent_spring_j=.5*c.tangential_stiffness_n_m*tangent2,exported_j=self.exported))


def simulate_fixed_grain(parameters,wall_deadline_s=1800):
    c=HopperConfig(**parameters['config']);c.validate()
    duration=parameters['duration_s'];sample_every=parameters['sample_every']
    if not math.isfinite(duration) or duration<=0 or not isinstance(sample_every,int) or sample_every<1:raise ValueError('Invalid observation/sampling')
    state=mixture_packing(c,parameters['diameters_m'],parameters['packing_bottom_m'])
    initial=hashlib.sha256(state.position.tobytes()+state.radius.tobytes()+state.mass.tobytes()).hexdigest()
    q=parameters['position_over_dFG']
    obstacle=None if q is None else obstacle_at_outlet(c,q,parameters['fixed_radius_m'],parameters['fixed_friction'])
    system=FixedGrainSystem(c,state,obstacle,backend='cpu');monitor=FixedGrainMonitor(c);system.monitor=monitor
    fields=('time_s','position_m','velocity_m_s','omega_rad_s','angle_rad','active','discharged_count','ejected_mass_kg')
    arrays={k:[] for k in fields};start=time.perf_counter();cpu_start=time.process_time()
    def sample():
        s=system.state;crossed=np.isfinite(system.crossing_time)
        for key,value in [('time_s',system.time_s),('position_m',s.position.copy()),('velocity_m_s',s.velocity.copy()),
            ('omega_rad_s',s.omega.copy()),('angle_rad',s.angle.copy()),('active',s.active.copy()),
            ('discharged_count',int(crossed.sum())),('ejected_mass_kg',float(s.mass[crossed].sum()))]:arrays[key].append(value)
        monitor.sample(system)
    sample();steps=int(math.ceil(duration/c.dt_s-1e-10))
    try:
        for index in range(1,steps+1):
            system.step()
            if index%sample_every==0 or index==steps:
                sample()
                if time.perf_counter()-start>wall_deadline_s:raise TimeoutError('M7A per-attempt wall deadline')
    except Exception as exc:
        # The runner stores this explicit partial physical trajectory, never retries.
        if arrays['time_s'][-1]!=system.time_s:sample()
        exc.partial_arrays={k:np.asarray(v) for k,v in arrays.items()}
        raise
    arrays={k:np.asarray(v) for k,v in arrays.items()}
    arrays.update(radius_m=state.radius.copy(),mass_kg=state.mass.copy(),particle_id=np.arange(c.n_particles),
        crossing_time_s=system.crossing_time.copy(),contact_graph=np.asarray(monitor.graphs),
        interval_common_contacts=np.asarray(monitor.commons),near_max_speed_m_s=np.asarray(monitor.speeds),
        remaining_count=np.asarray(monitor.remaining),interval_max_near_speed_m_s=np.asarray(monitor.interval_speeds),
        interval_min_remaining=np.asarray(monitor.interval_counts))
    arrays.update(monitor.arrays())
    events=detect_events(arrays,c.gate_open_time_s)
    if not all(np.isfinite(arrays[k]).all() for k in fields if k!='active'):raise RuntimeError('Nonfinite recorded trajectory')
    assert len(state.mass)==c.n_particles and int(state.active.sum())+int((~state.active).sum())==c.n_particles
    assert np.all(np.isfinite(system.crossing_time[~state.active]))
    mass=float(arrays['ejected_mass_kg'][-1]);count=int(arrays['discharged_count'][-1]);total=float(state.mass.sum())
    first=events[0] if events else None
    arch_mass=float(state.mass[np.isfinite(system.crossing_time)&(system.crossing_time<=first['onset_time_s'])].sum()) if first else None
    metadata=dict(schema_version='m7a-fixed-grain-v1',label=LABEL,parameters=parameters,config=asdict(c),
        initial_state_sha256=initial,geometry='flat_floor_ideal_segments',obstacle=asdict(obstacle) if obstacle else None,
        steps=steps,duration_actual_s=system.time_s,wall_time_s=time.perf_counter()-start,cpu_time_s=time.process_time()-cpu_start,
        ejected_count=count,ejected_mass_kg=mass,initial_mass_kg=total,mass_fraction=mass/total,
        completed_discharge=count==c.n_particles and arrays['remaining_count'][-1]==0,
        time_to_empty_s=float(np.nanmax(system.crossing_time)) if count==c.n_particles and arrays['remaining_count'][-1]==0 else None,
        events=events,startup_blockage=bool(first and arrays['discharged_count'][first['onset_frame']]==0),
        first_finite_arch_mass_kg=arch_mass,event_protocol='m7a-finite-arch-0.4s-v1',source_five_second_protocol_matched=False,
        max_overlap_over_radius=system.max_overlap_ratio,max_step_over_radius=system.max_step_ratio,
        timestep_limit_smallest_mass_s=c.timestep_limit_s(float(state.mass.min())),
        physics=monitor.summary(),obstacle_contact_step_observations=monitor.obstacle_steps,
        maximum_obstacle_reaction_n=monitor.max_reaction,support_work_j=0.,
        obstacle_immobile_by_construction=True,physical_agreement_score=None)
    return arrays,metadata
