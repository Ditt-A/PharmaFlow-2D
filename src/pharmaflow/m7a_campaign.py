"""Frozen, single-worker pilot ledger. Every solver attempt is charged before launch."""
from dataclasses import asdict
from datetime import datetime,timezone
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import numpy as np
from .config import HopperConfig
from .m6b_data import atomic_json,file_hash,acquisition_lock
from .m7a_simulation import simulate_fixed_grain
from .run import save_run


def now():return datetime.now(timezone.utc).isoformat()
def signature(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def source_hashes(root):
    names=['src/pharmaflow/'+n for n in ('fixed_grain.py','m7a_simulation.py','m7a_campaign.py','config.py','contact.py','dem.py','geometry.py','neighbors.py','taichi_backend.py')]+['scripts/run_m7a.py']
    return {n:file_hash(Path(root)/n) for n in names}


def tasks(design):
    result=[]
    for seed in design['seeds']:
        for q in design['positions_over_dFG']:
            parameters=dict(design['common']);parameters['config']=dict(parameters['config'],seed=seed)
            parameters['position_over_dFG']=q
            tag='control' if q is None else 'q'+str(round(q*100)).zfill(3)
            result.append(dict(run_id=f'm7a_{tag}_s{seed}',parameters=parameters))
    if len(result)>12 or len({r['run_id'] for r in result})!=len(result):raise ValueError('Invalid/excessive frozen design')
    return result


def freeze(root=Path('.')):
    root=Path(root).resolve();base=root/'data/simulated/m7a';base.mkdir(parents=True,exist_ok=True)
    design=json.loads((root/'configs/m7a/pilot.json').read_text())
    if design['budget']!=dict(maximum_attempts=12,maximum_worker_hours=6,maximum_wall_s_per_attempt=1800,workers=3):raise ValueError('Hard M7A limits cannot be changed')
    proof_path=root/'docs/results/m7a/prepilot_verification.json';geometry_path=root/'docs/results/m7a/geometry_gate.json'
    if json.loads(proof_path.read_text())['status']!='PASS' or not json.loads(geometry_path.read_text())['numerical_geometry_representable']:
        raise ValueError('Physics/geometry verification must pass BEFORE pilot freeze')
    entries=tasks(design)
    for entry in entries:HopperConfig(**entry['parameters']['config']).validate()
    path=base/'design_freeze.json'
    stable=dict(design_sha256=signature(design),source_sha256=source_hashes(root),entries=entries,
        prepilot_verification_sha256=file_hash(proof_path),geometry_gate_sha256=file_hash(geometry_path))
    if path.exists():
        old=json.loads(path.read_text())
        if any(old[k]!=v for k,v in stable.items()):raise ValueError('Frozen design/source/verification changed')
        return old
    value=dict(stable,frozen_utc=now(),starting_commit='e9e0d4ae642fe5b36e84aa5cc45b345f43a87308')
    atomic_json(path,value);return value


def connect_ledger(root):
    con=sqlite3.connect(Path(root)/'data/simulated/m7a/attempts.sqlite3')
    con.execute('CREATE TABLE IF NOT EXISTS attempts (run_id TEXT PRIMARY KEY,status TEXT,parameters TEXT,started_utc TEXT,finished_utc TEXT,wall_s REAL,error TEXT)')
    con.commit();return con


def reserve(con,entry):
    with con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM attempts WHERE run_id=?',(entry['run_id'],)).fetchone():return False
        if con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]>=12:raise ValueError('12-attempt budget exhausted')
        con.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?)',(entry['run_id'],'reserved',json.dumps(entry['parameters'],sort_keys=True),now(),None,None,None))
    return True


def worker(root,run_id):
    _limit_worker()
    root=Path(root).resolve();frozen=freeze(root)
    entry=next(e for e in frozen['entries'] if e['run_id']==run_id)
    con=connect_ledger(root)
    row=con.execute('SELECT status FROM attempts WHERE run_id=?',(run_id,)).fetchone()
    if row is None or row[0]!='reserved':raise ValueError('Worker requires a single charged reservation')
    with con:con.execute('UPDATE attempts SET status=? WHERE run_id=?',('running',run_id))
    con.close()
    outcome=root/'data/simulated/m7a/failures'/(run_id+'.json')
    try:
        arrays,meta=simulate_fixed_grain(entry['parameters'],1785)
        meta.update(run_id=run_id,source_sha256=frozen['source_sha256'],design_sha256=frozen['design_sha256'],
                    source_git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_git_dirty=True)
        target=root/'data/simulated/m7a/trajectories'/(run_id+'.npz')
        if target.exists():raise FileExistsError('Never overwrite an existing attempt trajectory')
        save_run(target,arrays,meta)
        atomic_json(target.with_suffix('.receipt.json'),dict(sha256=file_hash(target),run_id=run_id))
    except Exception as exc:
        atomic_json(outcome,dict(run_id=run_id,status='failed',parameters=entry['parameters'],reason=type(exc).__name__+': '+str(exc),source_sha256=frozen['source_sha256']))
        if hasattr(exc,'partial_arrays'):
            np.savez_compressed(outcome.with_suffix('.npz'),**exc.partial_arrays)
        raise


def _limit_worker():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(1790,1790))


def dispatch(root=Path('.'),profile_only=False):
    if os.name!='posix':raise RuntimeError('Use the POSIX JupyterHub environment for enforced CPU/wall pilot limits')
    root=Path(root).resolve();frozen=freeze(root);base=root/'data/simulated/m7a'
    with acquisition_lock(base):
        con=connect_ledger(root)
        selected=frozen['entries'][:1] if profile_only else frozen['entries']
        if not profile_only:
            first=frozen['entries'][0]['run_id']
            row=con.execute('SELECT status FROM attempts WHERE run_id=?',(first,)).fetchone()
            if row is None or row[0]!='success':raise ValueError('Run and review the single profile attempt first')
            profile=json.loads((base/'trajectories'/(first+'.json')).read_text())
            # Prespecified stop, not an outcome-dependent change to the observable.
            if profile['completed_discharge'] and profile.get('time_to_empty_s',float('inf'))<=.5*profile['duration_actual_s']:
                raise ValueError('Profile immediately exhausts finite fill; do not dispatch the remaining pilot')
            if profile['wall_time_s']*len(frozen['entries'])>21600:raise ValueError('Profile projects beyond six worker-hours')
        con.close()
        async def batch():
            semaphore=asyncio.Semaphore(1 if profile_only else 3)
            async def execute(entry):
                async with semaphore:
                    connection=connect_ledger(root)
                    if not reserve(connection,entry):connection.close();return
                    run_id=entry['run_id'];start=time.perf_counter();error=None;status='failed'
                    log=root/'outputs/metrics/m7a'/(run_id+'.log')
                    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
                    process=None;interruption=None
                    try:
                        with log.open('wb') as stream:
                            process=await asyncio.create_subprocess_exec(sys.executable,'scripts/run_m7a.py','--worker',run_id,
                                cwd=root,stdout=stream,stderr=subprocess.STDOUT,env=env)
                            try:
                                code=await asyncio.wait_for(process.wait(),timeout=1795)
                                status='success' if code==0 else 'failed';error=None if code==0 else 'Worker exit '+str(code)
                            except asyncio.TimeoutError:
                                process.kill();await asyncio.wait_for(process.wait(),4);error='Hard 1800s attempt deadline'
                    except BaseException as exc:
                        if process is not None and process.returncode is None:
                            process.kill();await asyncio.wait_for(process.wait(),4)
                        error=type(exc).__name__+': '+str(exc)
                        if isinstance(exc,(KeyboardInterrupt,SystemExit,asyncio.CancelledError)):interruption=exc
                    elapsed=time.perf_counter()-start
                    with connection:connection.execute('UPDATE attempts SET status=?,finished_utc=?,wall_s=?,error=? WHERE run_id=?',(status,now(),elapsed,error,run_id))
                    connection.close()
                    if status!='success' and not (base/'failures'/(run_id+'.json')).exists():
                        atomic_json(base/'failures'/(run_id+'.json'),dict(run_id=run_id,parameters=entry['parameters'],reason=error,wall_s=elapsed))
                    print(run_id,status,round(elapsed,3),flush=True)
                    if interruption is not None:raise interruption
            await asyncio.gather(*(execute(e) for e in selected))
        asyncio.run(batch())
