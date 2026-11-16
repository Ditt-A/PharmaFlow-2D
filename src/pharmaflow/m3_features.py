"""Causal frame observations and trailing-window features; never read labels."""
import numpy as np
from .geometry import hopper_walls,segment_contacts
from .m3_events import spans


def observations(position,velocity,radius,active,config,time_s):
    n=len(radius);graph=np.zeros((n+2,n+2),dtype=bool)
    remaining=active & (position[:,1]>=0)
    near=remaining & (position[:,1]<.025)
    delta=np.linalg.norm(position[:,None]-position[None,:],axis=2)
    adjacency=(delta<radius[:,None]+radius[None,:]) & active[:,None]&active[None,:]
    np.fill_diagonal(adjacency,False)
    graph[:n,:n]=adjacency & near[:,None]&near[None,:]
    wd,_,_=segment_contacts(position,hopper_walls(config,max(time_s,config.gate_open_time_s))[:2])
    for wall in (0,1):
        touched=near & (wd[:,wall]<radius)
        graph[:n,n+wall]=touched;graph[n+wall,:n]=touched
    speed=np.linalg.norm(velocity,axis=1)
    width_top=min(config.width_m,config.outlet_width_m+2*.025*np.tan(np.arctan((config.width_m-config.outlet_width_m)/(2*config.funnel_height_m))))
    area=.025*(config.outlet_width_m+width_top)/2
    count=int(near.sum())
    means=lambda a:float(np.mean(a)) if len(a) else 0.
    row=dict(active_count=int(active.sum()),remaining_count=int(remaining.sum()),near_count=count,
             near_occupancy_estimate=float(np.sum(np.pi*radius[near]**2)/area),
             speed_mean_m_s=means(speed[active]),speed_p50_m_s=float(np.median(speed[active])) if active.any() else 0.,
             speed_p95_m_s=float(np.quantile(speed[active],.95)) if active.any() else 0.,
             near_vx_mean_m_s=means(velocity[near,0]),near_vy_mean_m_s=means(velocity[near,1]),
             near_speed_mean_m_s=means(speed[near]),near_max_speed_m_s=float(np.max(speed[near])) if count else 0.,
             near_stationary_fraction=means(speed[near]<=.003),
             near_coordination_mean=means(adjacency.sum(axis=1)[near]),
             near_coordination_p95=float(np.quantile(adjacency.sum(axis=1)[near],.95)) if count else 0.,
             spanning_arch_now=int(spans(graph)),near_missing=int(count==0),active_missing=int(not active.any()))
    return row,graph


def extract_features(trace,config,packing_family):
    time=np.asarray(trace['time_s']);counts=np.asarray(trace['discharged_count']);rows=[]
    last_cross=None
    for i,t in enumerate(time):
        row={key:float(np.asarray(trace[key])[i]) for key in FRAME_FIELDS}
        row.update(frame_index=i,time_s=float(t),discharged_fraction=float(counts[i]/config.n_particles),
                   outlet_ratio=config.outlet_width_m/(2*config.particle_radius_m),friction=config.friction,
                   wall_friction=config.wall_friction,wall_angle_deg=float(np.degrees(np.arctan((config.width_m-config.outlet_width_m)/(2*config.funnel_height_m)))),
                   initial_particle_count=config.n_particles,particle_radius_m=config.particle_radius_m,
                   normal_stiffness_n_m=config.normal_stiffness_n_m,tangential_stiffness_n_m=config.tangential_stiffness_n_m,
                   packing_family=packing_family)
        if i>0 and counts[i]>counts[i-1]:last_cross=float(t)
        row['since_last_crossing_s']=float(t-(last_cross if last_cross is not None else time[0]))
        row['has_observed_crossing']=int(last_cross is not None)
        for window,name in ((.05,'50ms'),(.10,'100ms')):
            start=int(np.searchsorted(time,t-window,side='left'))
            before=int(np.searchsorted(time,t-window,side='right')-1)
            duration=min(window,float(t-time[0]))
            baseline=counts[before] if before>=0 else counts[0]
            row['flow_rate_'+name+'_particles_s']=float((counts[i]-baseline)/duration) if duration>0 else 0.
            velocity=np.asarray(trace['near_speed_mean_m_s'])[start:i+1]
            row['near_speed_rolling_mean_'+name+'_m_s']=float(np.mean(velocity))
            row['near_speed_rolling_std_'+name+'_m_s']=float(np.std(velocity))
            row['occupancy_change_'+name]=float(trace['near_occupancy_estimate'][i]-trace['near_occupancy_estimate'][start])
            row['history_coverage_'+name+'_s']=duration
        row['recent_interruption_50ms']=int(last_cross is not None and t-last_cross>=.05-1e-12 and row['remaining_count']>0)
        rows.append(row)
    return rows


FRAME_FIELDS=('active_count','remaining_count','near_count','near_occupancy_estimate','speed_mean_m_s','speed_p50_m_s','speed_p95_m_s',
              'near_vx_mean_m_s','near_vy_mean_m_s','near_speed_mean_m_s','near_max_speed_m_s','near_stationary_fraction',
              'near_coordination_mean','near_coordination_p95','spanning_arch_now','near_missing','active_missing')


def feature_dictionary():
    example={k:np.zeros(1) for k in FRAME_FIELDS};example.update(time_s=np.array([0.]),discharged_count=np.array([0]))
    from .config import HopperConfig
    fields=extract_features(example,HopperConfig(),'staggered')[0]
    result={}
    for key in fields:
        unit='dimensionless'
        if key.endswith('_m_s'):unit='m/s'
        elif key.endswith('_particles_s'):unit='particles/s'
        elif key.endswith('_s'):unit='s'
        elif key.endswith('_deg'):unit='degrees from vertical'
        elif key.endswith('_n_m'):unit='N/m'
        elif key.endswith('_m'):unit='m'
        elif 'count' in key or 'coordination' in key:unit='particles' if 'count' in key else 'contacts/particle'
        if key=='packing_family':unit='category'
        result[key]={'units':unit,'meaning':key.replace('_',' '),'availability':'at or before time_s',
                     'window_s':.05 if '50ms' in key else (.10 if '100ms' in key else 0),
                     'missing_policy':'zero for empty regions/zero history; use near_missing, active_missing and history_coverage flags',
                     'role':'identifier_not_predictor' if key in ('frame_index',) else 'predictor'}
        if key in ('packing_family','outlet_ratio','friction','wall_friction','wall_angle_deg','initial_particle_count',
                   'particle_radius_m','normal_stiffness_n_m','tangential_stiffness_n_m'):
            result[key].update(availability='static experiment configuration',missing_policy='required configuration value; never imputed')
    result['near_occupancy_estimate']['meaning']='Center-assigned disk area / actual 0–0.025 m trapezoid area; not exact packing or 3D solid fraction'
    result['spanning_arch_now']['meaning']='Instantaneous geometric contact path connecting both sloped walls; not future-confirmed arch label'
    return result
