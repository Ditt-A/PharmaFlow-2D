"""M4B immutable design, charged attempt ledger and delayed locked-cohort access."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import time

from .m3_campaign import run_task, stable_id, solver_hash, digest_file
from .m3_packing import physical_config, make_packing
from .m3_dataset import physical_group
from .m3_events import DEFAULT_PROTOCOL
from .m4_data import write_json, digest


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def campaign_lock(root):
    """One local ledger writer; Linux flock releases even if the parent crashes."""
    import fcntl
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.campaign.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    write_json(tmp, obj)
    os.replace(tmp, path)


def tasks(cases, phase, design):
    result = []
    for case in cases:
        config_id = stable_id(case['physical'])[:16]
        for family in design['packing_families']:
            seed = design[phase + '_seed_start'] + len(result)
            result.append(dict(run_id=f'm4b_{phase}_{config_id}_{family}_s{seed}',
                               configuration_id=config_id, case_name=case['name'], phase=phase,
                               physical=case['physical'], numerical=design['numerical'], seed=seed,
                               packing_family=family, duration_s=design['duration_s'],
                               max_duration_s=design['max_duration_s'], sample_interval_s=design['sample_interval_s'],
                               protocol=dict(DEFAULT_PROTOCOL, **design['protocol'])))
    if len(result) > design['allocation'][phase]:
        raise ValueError('Phase attempt allocation exceeded')
    return result


def group_for_task(task):
    from dataclasses import asdict
    return physical_group(asdict(physical_config(task['physical'], task['numerical'], task['seed'])))


def freeze_design(design_path='configs/m4b/design.json', root='data/simulated/m4b'):
    import pandas as pd
    design = json.loads(Path(design_path).read_text())
    root = Path(root)
    path = root / 'manifests/design_freeze.json'
    with campaign_lock(root):
        if path.exists():
            old = json.loads(path.read_text())
            if old['design'] != design or old['solver_sha256'] != solver_hash() or old['campaign_source_sha256'] != digest(__file__):
                raise ValueError('Frozen design/solver changed; never overwrite the release')
            return old
        pilot, locked = tasks(design['pilot_cases'], 'pilot', design), tasks(design['locked_cases'], 'locked', design)
        assert (len(pilot), len(locked), design['maximum_attempts']) == (12, 12, 48)
        old = pd.read_parquet('data/processed/m3/run_metadata.parquet')
        used = set(old.initial_state_sha256)
        locked_groups = {group_for_task(t) for t in locked}
        if len(locked_groups) != 4 or locked_groups & set(old.physical_group_id) or locked_groups & {group_for_task(t) for t in pilot}:
            raise ValueError('Locked cohort must contain four genuinely unseen physical groups')
        initial = {}
        for task in pilot + locked:
            _, sha = make_packing(physical_config(task['physical'], task['numerical'], task['seed']), task['packing_family'])
            if sha in used:
                raise ValueError('Duplicate historical/planned initial packing')
            used.add(sha)
            initial[task['run_id']] = sha
        frozen = dict(design=design, pilot_tasks=pilot, locked_tasks=locked,
                      locked_physical_groups=sorted(locked_groups), initial_sha256=initial,
                      solver_sha256=solver_hash(), campaign_source_sha256=digest(__file__), frozen_utc=now(),
                      design_sha256=digest(design_path), no_outcomes_inspected=True)
        atomic_json(path, frozen)
        return frozen


def reserve(ledger, proposed, allocation, maximum=48):
    """Reserved/dispatched failures and interruptions consume a slot; no silent retry."""
    entries = ledger.setdefault('attempts', {})
    new = [t for t in proposed if t['run_id'] not in entries]
    if len(entries) + len(new) > maximum:
        raise ValueError('Global 48-attempt ceiling exceeded')
    for phase, limit in allocation.items():
        count = sum(r['task']['phase'] == phase for r in entries.values()) + sum(t['phase'] == phase for t in new)
        if count > limit:
            raise ValueError('Phase attempt ceiling exceeded')
    for task in proposed:
        if task['run_id'] in entries and entries[task['run_id']]['task'] != task:
            raise ValueError('Attempt task changed')
    for task in new:
        entries[task['run_id']] = dict(task=task, state='reserved', reserved_utc=now())
    return new


def locked_gate(root, freeze_path):
    path = Path(freeze_path)
    if not path.exists():
        raise ValueError('Locked cohort unavailable before model/policy freeze')
    frozen = json.loads(path.read_text())
    design = Path(root) / 'manifests/design_freeze.json'
    if frozen['design_freeze_sha256'] != digest(design) or frozen.get('locked_outcomes_seen', True):
        raise ValueError('Invalid preregistered evaluation gate')
    for item in frozen['candidates']:
        if digest(item['artifact_path']) != item['artifact_sha256']:
            raise ValueError('Frozen model artifact changed')
    return frozen


def run_phase(phase, root='data/simulated/m4b', design_path='configs/m4b/design.json',
              adaptive_path='configs/m4b/adaptive.json', jobs=4,
              model_freeze='outputs/metrics/m4b/model_and_policy_freeze.json'):
    frozen = freeze_design(design_path, root)
    design, root = frozen['design'], Path(root)
    with campaign_lock(root):
        if phase == 'locked':
            locked_gate(root, model_freeze)
            proposed = frozen['locked_tasks']
        elif phase == 'pilot':
            proposed = frozen['pilot_tasks']
        elif phase == 'adaptive':
            if not (root / 'manifests/pilot_campaign.json').exists():
                raise ValueError('Pilot review required before adaptive phase')
            adaptive = json.loads(Path(adaptive_path).read_text())
            if not adaptive.get('pilot_review'):
                raise ValueError('Document a pilot review first')
            proposed = tasks(adaptive['cases'], phase, design)
            if {group_for_task(t) for t in proposed} & set(frozen['locked_physical_groups']):
                raise ValueError('Development includes a locked physical configuration')
        else:
            raise ValueError(phase)
        manifest = root / 'manifests' / (phase + '_campaign.json')
        if manifest.exists() and json.loads(manifest.read_text())['tasks'] != proposed:
            raise ValueError('Phase plan changed after dispatch')
        if manifest.exists() and json.loads(manifest.read_text())['state'] == 'complete':
            previous = json.loads(manifest.read_text())
            for record in previous['records']:
                if record['status'] == 'ok' and digest(record['trajectory_path']) != record['npz_sha256']:
                    raise ValueError('Cached trajectory changed')
            return previous
        if phase == 'locked':
            atomic_json(root / 'manifests/locked_access_receipt.json',
                        dict(model_freeze_sha256=digest(model_freeze),
                             design_freeze_sha256=digest(root / 'manifests/design_freeze.json'), opened_utc=now()))
        ledger_path = root / 'manifests/attempts.json'
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else dict(maximum=48, attempts={})
        old_ids = set(ledger['attempts'])
        new = reserve(ledger, proposed, design['allocation'], design['maximum_attempts'])
        # Validate no initial-state reuse without integrating the solver.
        known = set(frozen['initial_sha256'].values())
        for record in ledger['attempts'].values():
            if record.get('result', {}).get('initial_state_sha256'):
                known.add(record['result']['initial_state_sha256'])
        if phase == 'adaptive':
            for task in new:
                _, sha = make_packing(physical_config(task['physical'], task['numerical'], task['seed']), task['packing_family'])
                if sha in known:
                    raise ValueError('Development packing reused')
                known.add(sha)
        atomic_json(ledger_path, ledger)  # charge before solver dispatch
        for task in proposed:
            entry = ledger['attempts'][task['run_id']]
            if task['run_id'] in old_ids and entry['state'] == 'reserved':
                summary = root / phase / task['run_id'] / 'run.json'
                if summary.exists():
                    result = json.loads(summary.read_text())
                else:
                    result = dict(task, status='failed', numerical_valid=False, runtime_s=0.,
                                  error='Interrupted reserved attempt; not retried', solver_source_sha256=solver_hash())
                    atomic_json(root / 'failures' / (task['run_id'] + '.json'), result)
                    atomic_json(summary, result)
                entry.update(state='finished', result=result)
        start = time.perf_counter()
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            pending = {executor.submit(run_task, task, str(root)): task for task in new}
            for future in as_completed(pending):
                task = pending[future]
                result = future.result()
                ledger['attempts'][task['run_id']].update(state='finished', result=result)
                atomic_json(ledger_path, ledger)
                print(task['run_id'], result['status'], result.get('flow_state'), len(result.get('events', [])), flush=True)
        records = [ledger['attempts'][t['run_id']]['result'] for t in proposed]
        report = dict(phase=phase, tasks=proposed, records=records, state='complete',
                      cumulative_charged_attempts=len(ledger['attempts']), phase_wall_s=time.perf_counter() - start)
        atomic_json(manifest, report)
        return report
