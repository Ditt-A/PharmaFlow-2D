"""Bounded explicit DEM demo jobs, separate from historical research releases."""
from pathlib import Path
from datetime import datetime,timezone
import json
import math
import os
import sqlite3
import subprocess
import sys
import uuid
from .m3_packing import physical_config
from .m4_data import digest,write_json


def limits(root=Path('.')):
    return json.loads((Path(root)/'configs/m5/demo_limits.json').read_text())


def validate_request(request, configuration):
    keys={'outlet_ratio','friction','wall_friction','wall_angle_deg','n_particles','packing_family','seed','duration_s'}
    if set(request)!=keys:raise ValueError('Supply exactly the eight demo inputs')
    for key in keys-{'packing_family'}:
        if not isinstance(request[key],(int,float)) or isinstance(request[key],bool) or not math.isfinite(request[key]):
            raise ValueError('Inputs must be finite numbers: '+key)
    if request['packing_family'] not in ('staggered','hexagonal','random_sequential'):raise ValueError('Unknown packing family')
    if not 2<=request['outlet_ratio']<=6:raise ValueError('Outlet ratio must be between 2 and 6')
    if not 28<=request['wall_angle_deg']<=42:raise ValueError('Angle must be 28-42 degrees from vertical')
    if not all(.15<=request[k]<=.65 for k in ('friction','wall_friction')):raise ValueError('Friction must be .15-.65')
    if int(request['n_particles'])!=request['n_particles'] or not 30<=request['n_particles']<=100:raise ValueError('Use 30-100 disks')
    if int(request['seed'])!=request['seed'] or not 0<=request['seed']<2**32:raise ValueError('Invalid initial-state seed')
    duration=request['duration_s'];dt=configuration['numerical']['dt_s']
    if not configuration['minimum_duration_s']<=duration<=configuration['maximum_duration_s']:raise ValueError('Demo duration must be .10-.80 seconds')
    if abs(duration/configuration['sample_interval_s']-round(duration/configuration['sample_interval_s']))>1e-8:
        raise ValueError('Duration must align with the .005s sample interval')
    work=round(duration/dt)*int(request['n_particles'])**2
    if work>configuration['maximum_work_units']:
        raise ValueError('Demo work limit exceeded: reduce duration or particle count (100 disks permit up to .20s)')
    physical={k:request[k] for k in ('outlet_ratio','friction','wall_friction','wall_angle_deg','n_particles')}
    physical['n_particles']=int(request['n_particles'])
    c=physical_config(physical,configuration['numerical'],int(request['seed']))
    c.validate()  # includes contact timestep guard; it is never relaxed
    return dict(request,n_particles=int(request['n_particles']),seed=int(request['seed']))


def connect(root):
    folder=Path(root)/'outputs/demos/m5';folder.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(folder/'budget.sqlite3',timeout=5)
    con.execute('CREATE TABLE IF NOT EXISTS attempts (run_id TEXT PRIMARY KEY, request_json TEXT, status TEXT, created_utc TEXT, error TEXT)')
    return con


def jobs(root=Path('.')):
    con=connect(root)
    result=[dict(run_id=r[0],request=json.loads(r[1]),status=r[2],created_utc=r[3],error=r[4])
            for r in con.execute('SELECT * FROM attempts ORDER BY created_utc')]
    con.close();return result


def reserve_demo(request, root=Path('.')):
    root=Path(root);configuration=limits(root);request=validate_request(request,configuration)
    con=connect(root)
    try:
        con.execute('BEGIN IMMEDIATE')
        old=list(con.execute('SELECT request_json,status FROM attempts'))
        if len(old)>=configuration['maximum_attempts']:raise ValueError('The six-attempt demo budget is exhausted')
        if any(status in ('reserved','running','integrating') for _,status in old):raise ValueError('A demo is already running')
        if sum(json.loads(r)['duration_s'] for r,_ in old)+request['duration_s']>configuration['maximum_total_simulated_s']+1e-12:
            raise ValueError('The cumulative three-second demo budget would be exceeded')
        run_id='m5_demo_'+uuid.uuid4().hex
        con.execute('INSERT INTO attempts VALUES (?,?,?,?,?)',(run_id,json.dumps(request,sort_keys=True),'reserved',datetime.now(timezone.utc).isoformat(),None))
        con.commit()
    except Exception:
        con.rollback();raise
    finally:con.close()
    folder=root/'outputs/demos/m5'/run_id;folder.mkdir(parents=True)
    write_json(folder/'request.json',dict(request=request,scope='unevaluated_demo',limits=configuration))
    return run_id


def set_status(root,run_id,status,error=None):
    con=connect(root);con.execute('UPDATE attempts SET status=?,error=? WHERE run_id=?',(status,error,run_id));con.commit();con.close()


def launch_demo(request, root=Path('.')):
    root=Path(root).resolve();run_id=reserve_demo(request,root)
    log=(root/'outputs/demos/m5'/run_id/'worker.log').open('w')
    try:
        options=dict(cwd=str(root),stdout=log,stderr=subprocess.STDOUT)
        if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW
        else:options['start_new_session']=True
        subprocess.Popen([sys.executable,str(root/'scripts/run_demo.py'),'--worker',run_id,'--root',str(root)],**options)
    except Exception as exc:
        set_status(root,run_id,'failed','Launch failed: '+str(exc));raise
    finally:log.close()
    return run_id


def integrate_demo(root,run_id):
    from .m3_campaign import simulate_task
    from .run import save_run
    root=Path(root);con=connect(root)
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT request_json,status FROM attempts WHERE run_id=?',(run_id,)).fetchone()
        if row is None or row[1]!='running':raise ValueError('Integrator requires a unique claimed reservation; no retry')
        con.execute('UPDATE attempts SET status=? WHERE run_id=?',('integrating',run_id));con.commit()
    finally:con.close()
    p=json.loads(row[0]);saved=json.loads((root/'outputs/demos/m5'/run_id/'request.json').read_text())
    configuration=saved['limits']
    if saved['request']!=p or configuration!=limits(root):raise ValueError('Demo reservation configuration changed')
    validate_request(p,configuration)
    task=dict(run_id=run_id,configuration_id='unevaluated_demo',phase='m5_demo',
              physical={k:p[k] for k in ('outlet_ratio','friction','wall_friction','wall_angle_deg','n_particles')},
              numerical=configuration['numerical'],seed=p['seed'],packing_family=p['packing_family'],
              duration_s=p['duration_s'],max_duration_s=p['duration_s'],sample_interval_s=configuration['sample_interval_s'],
              protocol=dict(persistence_s=.4,stationary_speed_m_s=.003,gate_buffer_s=.02,minimum_remaining=2))
    arrays,meta=simulate_task(task)
    meta.update(source='demo',cohort='m5_demo',membership='unevaluated',not_for_training_or_evaluation=True)
    folder=root/'outputs/demos/m5'/run_id;path=folder/'trajectory.npz'
    save_run(path,arrays,meta)
    meta['npz_sha256']=digest(path);meta['trajectory_path']=str(path)
    write_json(folder/'run.json',meta)


def supervise_demo(root,run_id):
    root=Path(root);con=connect(root)
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT status FROM attempts WHERE run_id=?',(run_id,)).fetchone()
        if row is None or row[0]!='reserved':raise ValueError('Demo already claimed; no retry')
        con.execute('UPDATE attempts SET status=? WHERE run_id=?',('running',run_id));con.commit()
    finally:con.close()
    try:
        subprocess.run([sys.executable,str(root/'scripts/run_demo.py'),'--integrate',run_id,'--root',str(root)],
                       cwd=root,check=True,timeout=limits(root)['wall_timeout_s'])
        set_status(root,run_id,'complete')
    except Exception as exc:
        reason=type(exc).__name__+': '+str(exc)
        set_status(root,run_id,'failed',reason)
        write_json(root/'outputs/demos/m5/failures'/(run_id+'.json'),dict(run_id=run_id,error=reason,charged_attempt=True))
