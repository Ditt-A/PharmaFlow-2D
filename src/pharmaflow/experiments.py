"""Configurable, resumable independent DEM experiments (no prediction models)."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .config import HopperConfig
from .dem import initial_state
from .run import simulate, save_run
from .validation import PhysicsMonitor, flow_metrics


def source_hash():
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def build_tasks(suite):
    tasks = []
    for case in suite['cases']:
        for seed in suite['seeds']:
            for factor in suite.get('dt_factors', [1]):
                values = dict(suite.get('base', {}), **case.get('parameters', {}), seed=seed)
                if 'outlet_ratio' in case:
                    values['outlet_width_m'] = 2 * values.get('particle_radius_m', .002) * case['outlet_ratio']
                values['dt_s'] = values.get('dt_s', 1e-5) / factor
                config = HopperConfig(**values)
                config.validate()
                duration = case.get('duration_s', suite['duration_s'])
                interval = suite['sample_interval_s']
                steps_per_sample = round(interval / config.dt_s)
                if not np.isclose(steps_per_sample * config.dt_s, interval, atol=1e-12, rtol=0):
                    raise ValueError('sampling interval must divide by every dt exactly')
                if not np.isclose(round(duration / config.dt_s) * config.dt_s, duration, atol=1e-12, rtol=0):
                    raise ValueError('duration must divide by every dt exactly')
                run_id = f"{case['name']}_seed{seed}_dt{factor}"
                tasks.append(dict(run_id=run_id, case=case['name'], seed=seed, dt_factor=factor,
                                  config=asdict(config), duration_s=duration, sample_every=steps_per_sample,
                                  backend=suite.get('backend', 'cpu')))
    if len({t['run_id'] for t in tasks}) != len(tasks):
        raise ValueError('duplicate run ids')
    return tasks


def run_experiment(task, output, resume=True):
    output = Path(output)
    folder = output / task['run_id']
    folder.mkdir(parents=True, exist_ok=True)
    summary_path = folder / 'summary.json'
    signature = hashlib.sha256(json.dumps(task, sort_keys=True).encode() + source_hash().encode()).hexdigest()
    if resume and summary_path.exists():
        previous = json.loads(summary_path.read_text())
        if previous.get('signature') == signature and previous.get('status') == 'ok':
            return previous
    started = time.perf_counter()
    result = dict(task, signature=signature, source_sha256=source_hash())
    try:
        config = HopperConfig(**task['config'])
        state = initial_state(config)
        initial_hash = hashlib.sha256(state.position.tobytes() + state.velocity.tobytes() + state.radius.tobytes() + state.mass.tobytes()).hexdigest()
        arrays, metadata = simulate(config, task['duration_s'], task['sample_every'], task['backend'], PhysicsMonitor(config))
        save_run(folder / 'trajectory.npz', arrays, metadata)
        metrics = flow_metrics(arrays, config, metadata['duration_actual_s'])
        checks = metadata['accuracy_checks']
        if metadata['physics_monitor']['boundary_center_leak_samples']:
            raise RuntimeError('boundary center leak detected')
        if not checks['finite'] or not checks['particle_accounting'] or not checks['removed_have_crossing']:
            raise RuntimeError('invalid finite state or conservation')
        result.update(status='ok', initial_state_sha256=initial_hash, trajectory_sha256=metadata['trajectory_sha256'],
                      runtime_s=metadata['wall_time_s'], metrics=metrics, accuracy=checks,
                      physics=metadata['physics_monitor'], hardware=metadata['hardware'])
    except Exception as error:
        result.update(status='failed', error=f'{type(error).__name__}: {error}', runtime_s=time.perf_counter() - started)
    temporary = summary_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    temporary.replace(summary_path)
    return result


def run_suite(suite_path, output, jobs=1, resume=True):
    suite = json.loads(Path(suite_path).read_text())
    tasks = build_tasks(suite)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'suite.json').write_text(json.dumps(suite, indent=2) + '\n')
    results = []
    if jobs == 1:
        for task in tasks:
            result = run_experiment(task, output, resume)
            results.append(result)
            print(result['run_id'], result['status'], result.get('metrics', {}).get('flow_state'), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            pending = [executor.submit(run_experiment, task, str(output), resume) for task in tasks]
            for future in as_completed(pending):
                result = future.result()
                results.append(result)
                print(result['run_id'], result['status'], result.get('metrics', {}).get('flow_state'), flush=True)
    (output / 'results.json').write_text(json.dumps(sorted(results, key=lambda r:r['run_id']), indent=2, allow_nan=False) + '\n')
    return results
