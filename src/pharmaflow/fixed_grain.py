"""Separate fixed-grain numerical analogue; legacy wedge modules are unchanged."""
from dataclasses import dataclass
import math
import numpy as np
from .dem import DEMSystem,ParticleState
from .geometry import hopper_walls


@dataclass(frozen=True)
class FixedGrain:
    center_m: tuple
    radius_m: float
    friction: float=.4

    def __post_init__(self):
        object.__setattr__(self,'center_m',tuple(float(v) for v in self.center_m))
        if len(self.center_m)!=2 or not all(math.isfinite(v) for v in (*self.center_m,self.radius_m,self.friction)):
            raise ValueError('Finite circular-obstacle geometry required')
        if self.radius_m<=0 or self.friction<0:raise ValueError('Positive obstacle radius and nonnegative friction required')


def flat_floor_walls(config,time_s):
    """Ideal zero-thickness floor and vertical sides, with an explicitly timed gate."""
    w,o,h=config.width_m/2,config.outlet_width_m/2,config.height_m
    segments=[((-w,0),(-o,0)),((o,0),(w,0)),((-w,h),(-w,0)),((w,0),(w,h))]
    if time_s<config.gate_open_time_s:segments.append(((-o,0),(o,0)))
    return np.asarray(segments,float)


def obstacle_at_outlet(config,position_over_diameter,radius_m=.0037,friction=.4):
    """Chosen analogue frame: left edge, positive distance OUTWARD, circle on floor.

    y=R is an ideal tangent-floor convention, not a recovered raw wall coordinate.
    """
    q=float(position_over_diameter)
    if not math.isfinite(q) or q<0:raise ValueError('Nonnegative finite edge-distance ratio required')
    body=FixedGrain((-config.outlet_width_m/2-q*2*radius_m,radius_m),radius_m,friction)
    if abs(body.center_m[0])+radius_m>=config.width_m/2:
        raise ValueError('Fixed grain intersects the outer sidewall')
    return body


class FixedGrainSystem(DEMSystem):
    """The obstacle has no dynamical state, velocity or integration update.

    Mobile contacts use the same linear/Coulomb response and torque convention as
    legacy disk contacts. External support balances the obstacle reaction.
    """
    def __init__(self,config,state,obstacle=None,geometry='flat_floor',**kwargs):
        if geometry not in ('flat_floor','wedge'):raise ValueError('Unknown selectable geometry')
        if obstacle is not None and not isinstance(obstacle,FixedGrain):raise ValueError('Expected immutable FixedGrain')
        self.geometry=geometry;self.obstacle=obstacle;self.obstacle_history={}
        self.obstacle_reaction_force_n=np.zeros(2);self.obstacle_reaction_torque_nm=0.
        self.obstacle_contact_ids=np.empty(0,dtype=int)
        super().__init__(config,state,**kwargs)
        self.check_obstacle()

    @property
    def walls(self):
        if self.fixed_walls is not None:return self.fixed_walls
        return flat_floor_walls(self.config,self.time_s) if self.geometry=='flat_floor' else hopper_walls(self.config,self.time_s)

    def obstacle_geometry(self):
        s=self.state
        if self.obstacle is None:return np.empty(0,dtype=int),np.empty(0),np.empty(0),np.empty((0,2))
        ids=np.flatnonzero(s.active);delta=s.position[ids]-self.obstacle.center_m
        distance=np.linalg.norm(delta,axis=1);overlap=s.radius[ids]+self.obstacle.radius_m-distance
        keep=overlap>0;ids,distance,delta,overlap=ids[keep],distance[keep],delta[keep],overlap[keep]
        if np.any(distance<1e-15):raise RuntimeError('Coincident fixed-grain/mobile center')
        return ids,overlap,distance,delta/np.maximum(distance[:,None],1e-30)

    def check_obstacle(self):
        ids,overlap,distance,normal=self.obstacle_geometry()
        if len(ids):
            ratio=float(np.max(overlap/np.minimum(self.state.radius[ids],self.obstacle.radius_m)))
            self.max_overlap_ratio=max(self.max_overlap_ratio,ratio)
            if ratio>self.config.max_overlap_ratio:
                raise RuntimeError(f'Fixed-grain excessive overlap {ratio:.6g} (limit {self.config.max_overlap_ratio})')
        return ids,overlap,distance,normal

    def forces(self):
        force,torque=super().forces()
        s,c=self.state,self.config;ids,overlap,_,normal=self.check_obstacle()
        self.obstacle_contact_ids=ids
        self.obstacle_reaction_force_n=np.zeros(2);self.obstacle_reaction_torque_nm=0.
        if not len(ids):self.obstacle_history={};return force,torque
        tangent=np.column_stack((-normal[:,1],normal[:,0]))
        lever=s.radius[ids]-overlap/2
        vn=np.sum(s.velocity[ids]*normal,axis=1)
        vt=np.sum(s.velocity[ids]*tangent,axis=1)-s.omega[ids]*lever
        old=np.array([self.obstacle_history.get(int(i),(0.,0.)) for i in ids])
        history=np.sum(old*tangent,axis=1)
        fn,ft,xi=self.response(overlap,vn,vt,history,np.full(len(ids),self.obstacle.friction),c.dt_s,
            c.normal_stiffness_n_m,c.tangential_stiffness_n_m,c.normal_damping_kg_s,c.tangential_damping_kg_s)
        contact=fn[:,None]*normal+ft[:,None]*tangent
        force[ids]+=contact;torque[ids]-=lever*ft
        self.obstacle_reaction_force_n=-contact.sum(axis=0)
        self.obstacle_reaction_torque_nm=float(np.sum(-(self.obstacle.radius_m-overlap/2)*ft))
        self.obstacle_history={int(i):v for i,v in zip(ids,xi[:,None]*tangent)}
        if self.monitor is not None and hasattr(self.monitor,'obstacle_contacts'):
            self.monitor.obstacle_contacts(self,overlap,np.minimum(s.radius[ids],self.obstacle.radius_m),fn,vn,ft*vt)
        return force,torque

    def step(self):
        super().step()
        self.check_obstacle()  # post-integration guard, including the final step


def mixture_packing(config,diameters_m=(.006,.0074,.0086),bottom_m=.025):
    """Equal-count species is an explicit assumption; source fractions are unknown.

    Seed changes species ordering, row order and jitter. All obstacle conditions
    at the same seed receive byte-identical mobile initial states.
    """
    d=np.asarray(diameters_m,float)
    if d.ndim!=1 or not len(d) or np.any(d<=0) or not np.isfinite(d).all():raise ValueError('Finite positive diameters required')
    if bottom_m<=float(d.max()):raise ValueError('Initial packing must clear the obstacle/floor region')
    rng=np.random.default_rng(config.seed);rmax=float(d.max()/2);spacing=2.25*rmax
    radii=np.resize(d/2,config.n_particles);rng.shuffle(radii)
    points=[]
    for row,y in enumerate(np.arange(bottom_m,config.height_m-2*rmax,spacing)):
        xs=np.arange(-config.width_m/2+2*rmax,config.width_m/2-2*rmax,spacing)+(row%2)*spacing/2
        for x in rng.permutation(xs):
            if abs(x)>config.width_m/2-1.5*rmax:continue
            points.append(np.array([x,y])+rng.uniform(-.015*rmax,.015*rmax,2))
            if len(points)==config.n_particles:
                mass=config.density_kg_m3*np.pi*radii**2*config.thickness_m
                state=ParticleState.create(points,radii,mass);state.validate()
                if config.dt_s>config.timestep_limit_s(float(mass.min())):raise ValueError('Timestep fails smallest species mass')
                return state
    raise ValueError('Requested mixture does not fit the flat-floor fill')


def elastic_collision_metrics():
    """Tiny analytic physics verification cases, separate from the pilot campaign."""
    from .config import HopperConfig
    results=[]
    for dt in (1e-5,5e-6,2.5e-6):
        c=HopperConfig(n_particles=1,dt_s=dt,gravity_m_s2=0,gate_open_time_s=0,
            normal_damping_kg_s=0,tangential_damping_kg_s=0,friction=0)
        s=ParticleState.create([[.0042,0]],.002,c.particle_mass_kg,[[-.1,0]])
        system=FixedGrainSystem(c,s,FixedGrain((0,0),.002,0),walls=(),track_outlet=False)
        initial=.5*s.mass[0]*.1**2;maximum=0.;impulse=np.zeros(2);p0=s.mass[0]*s.velocity[0].copy()
        for _ in range(round(.006/dt)):
            system.step();impulse+=system.obstacle_reaction_force_n*dt
            overlap=system.obstacle_geometry()[1]
            energy=float(.5*np.sum(s.mass[:,None]*s.velocity**2)+.5*c.normal_stiffness_n_m*np.sum(overlap**2))
            maximum=max(maximum,abs(energy/initial-1))
        results.append(dict(dt_s=dt,duration_s=.006,maximum_relative_energy_error=maximum,
            final_relative_kinetic_error=float(abs(.5*s.mass[0]*np.sum(s.velocity[0]**2)/initial-1)),
            final_velocity_x_m_s=float(s.velocity[0,0]),mobile_plus_obstacle_impulse_residual_kg_m_s=float(np.linalg.norm(s.mass[0]*s.velocity[0]-p0+impulse)),
            maximum_overlap_over_radius=system.max_overlap_ratio))
    return results
