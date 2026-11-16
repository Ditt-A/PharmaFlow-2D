"""Controlled analytic-energy and strict CPU/CUDA benchmarks for M2."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
from pharmaflow.config import HopperConfig
from pharmaflow.dem import DEMSystem, ParticleState
from pharmaflow.run import hardware_info


def energy(system):
    s,c=system.state,system.config
    overlap=max(0.,s.radius.sum()-np.linalg.norm(s.position[0]-s.position[1]))
    spring=.5*c.normal_stiffness_n_m*overlap**2
    spring+=.5*c.tangential_stiffness_n_m*sum(float(np.dot(x,x)) for x in system.history.values())
    return float(np.sum(.5*s.mass*np.sum(s.velocity**2,axis=1)+.5*s.inertia*s.omega**2)+spring)


def controlled_pair(dt, dissipative=False, backend='cpu', duration=.005):
    c=replace(HopperConfig(),gravity_m_s2=0,dt_s=dt,normal_damping_kg_s=.15 if dissipative else 0,
              tangential_damping_kg_s=.03 if dissipative else 0, friction=.4 if dissipative else 0)
    if dissipative:
        x=[[-.00195,0],[.00195,0]];v=[[.03,.08],[-.03,-.02]]
    else:
        x=[[-.0021,0],[.0021,0]];v=[[.1,0],[-.1,0]]
    state=ParticleState.create(x,c.particle_radius_m,c.particle_mass_kg,v)
    system=DEMSystem(c,state,walls=(),backend=backend,track_outlet=False)
    energies=[energy(system)];positions=[state.position.copy()];velocities=[state.velocity.copy()];omegas=[state.omega.copy()]
    for _ in range(round(duration/dt)):
        system.step()
        energies.append(energy(system));positions.append(state.position.copy());velocities.append(state.velocity.copy());omegas.append(state.omega.copy())
    e=np.asarray(energies)
    exact_x=-c.particle_radius_m-.1*(duration-.001-c.contact_time_s)
    result={'dt_s':dt,'duration_s':duration,'backend':system.backend,'initial_energy_j':float(e[0]),
            'final_energy_j':float(e[-1]),'final_energy_fraction':float(e[-1]/e[0]),
            'max_energy_change_fraction':float(np.max(abs(e-e[0]))/e[0]),
            'final_position_error_m':abs(float(state.position[0,0]-exact_x)) if not dissipative else None,
            'max_omega_rad_s':float(np.max(np.abs(omegas))), 'max_overlap_over_radius':system.max_overlap_ratio}
    return result,dict(time_s=np.arange(len(e))*dt,energy_j=e,position=np.asarray(positions),velocity=np.asarray(velocities),omega=np.asarray(omegas))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('outputs/metrics/m2/benchmarks'))
    parser.add_argument('--cuda',action='store_true',help='Require strict CUDA; failures are fatal')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    report={'hardware':hardware_info(),'elastic':[],'damped_frictional':[],'free_fall':[]}
    for factor in (1,2,4):
        dt=1e-5/factor
        for dissipative,key in ((False,'elastic'),(True,'damped_frictional')):
            metrics,trace=controlled_pair(dt,dissipative)
            report[key].append(metrics)
            np.savez_compressed(args.output/f'{key}_dt{factor}.npz',**trace)
        c=replace(HopperConfig(),n_particles=1,dt_s=dt)
        s=ParticleState.create([[0,1]],c.particle_radius_m,c.particle_mass_kg)
        system=DEMSystem(c,s,walls=(),track_outlet=False)
        system.advance(round(.02/dt))
        error=abs(float(s.position[0,1]-(1-.5*c.gravity_m_s2*.02**2)))
        report['free_fall'].append({'dt_s':dt,'position_error_m':error})
    if args.cuda:
        cpu,cpu_trace=controlled_pair(1e-5,True,duration=.004)
        gpu,gpu_trace=controlled_pair(1e-5,True,backend='cuda',duration=.004)
        tolerances={'position':1e-10,'velocity':1e-8,'omega':1e-6}
        comparison={'backend':gpu['backend'],'duration_s':.004,'steps':400,'passed':True,'absolute_tolerances':tolerances}
        for name,tol in tolerances.items():
            error=float(np.max(np.abs(cpu_trace[name]-gpu_trace[name])))
            comparison[name+'_max_abs_error']=error
            if error>tol:raise RuntimeError(f'CPU/CUDA {name} error {error} > {tol}')
        report['cpu_cuda']=comparison
    (args.output/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__':main()
