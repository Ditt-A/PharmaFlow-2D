"""Read-only historical runs and portable portfolio bundles; no simulator side effects."""
from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
from .config import HopperConfig
from .run import load_run
from .m3_features import extract_features
from .m4_data import digest, write_json
from .monitoring import frozen_specs, frozen_ml_scores, monitor_features
from .operational_events import observe_history, annotate_outcomes


@dataclass
class ReplayBundle:
    record: dict
    arrays: dict
    config: HopperConfig
    features: pd.DataFrame
    monitoring: pd.DataFrame
    logs: dict
    annotations: dict
    specs: dict

    def frame(self, index):
        if not isinstance(index, (int,np.integer)) or not 0 <= index < len(self.features):
            raise ValueError('Frame index outside the stored trajectory')
        return dict(index=int(index), time_s=float(self.arrays['time_s'][index]),
                    positions=self.arrays['position_m'][index], velocities=self.arrays['velocity_m_s'][index],
                    radius=self.arrays['radius_m'], active=self.arrays['active'][index],
                    observed=self.monitoring.iloc[index].to_dict())


def historical_registry(root=Path('.')):
    root=Path(root); records=[]
    split_path=root/'data/processed/m4b/development/split_manifest.json'
    splits=json.loads(split_path.read_text())['assignments'] if split_path.exists() else {}
    for cohort,phases in [('m3',('pilot','production')),('m4b',('pilot','adaptive','locked'))]:
        for phase in phases:
            for path in sorted((root/f'data/simulated/{cohort}'/phase).glob('*/run.json')):
                r=json.loads(path.read_text())
                if r['status']!='ok':continue
                r.update(cohort=cohort,source='historical',membership=('locked' if phase=='locked' else splits.get(r['run_id'],'historical')))
                r['trajectory_path']=str((path.parent/'trajectory.npz').relative_to(root))
                records.append(r)
    if not records:
        catalog=root/'outputs/dashboard/m5/portfolio/catalog.json'
        if catalog.exists():records=json.loads(catalog.read_text())['records']
    for path in sorted((root/'outputs/demos/m5').glob('*/run.json')):
        r=json.loads(path.read_text())
        if r.get('status')=='ok':
            r.update(source='demo',cohort='m5_demo',membership='unevaluated')
            r['trajectory_path']=str((path.parent/'trajectory.npz').relative_to(root))
            records.append(r)
    return records


def load_bundle(record, root=Path('.'), require_ml=False):
    root=Path(root).resolve();path=(root/record['trajectory_path']).resolve()
    if root not in path.parents:raise ValueError('Trajectory must be inside the project')
    if digest(path)!=record['npz_sha256']:
        raise ValueError('Stored trajectory checksum mismatch')
    arrays,embedded=load_run(path)
    if embedded['config']!=record['config'] or embedded.get('run_id')!=record['run_id']:
        raise ValueError('Trajectory metadata does not match the replay record')
    config=HopperConfig(**record['config'])
    if len(arrays['time_s'])<2 or np.any(np.diff(arrays['time_s'])<=0):
        raise ValueError('Invalid replay chronology')
    if not np.isfinite(arrays['position_m']).all() or arrays['position_m'].shape[:2]!=arrays['active'].shape:
        raise ValueError('Invalid replay particle states')
    features=pd.DataFrame(extract_features(arrays,config,record['packing_family']))
    specs=frozen_specs(root)
    cache_path=root/'outputs/dashboard/m5/monitor_cache'/(record['run_id']+'.json')
    if cache_path.exists():
        cache=json.loads(cache_path.read_text())
        if (cache['npz_sha256']!=record['npz_sha256'] or cache['specs']!=specs
                or cache['times_s']!=arrays['time_s'].tolist()):
            raise ValueError('Monitoring cache provenance mismatch')
        ml_scores=cache['ml_scores']
    else:
        try:ml_scores=frozen_ml_scores(features,specs['ml'],root)
        except FileNotFoundError:
            if require_ml:raise
            ml_scores=None
    monitored,logs=monitor_features(features,arrays['discharged_count'],specs,ml_scores,
                                     config.gate_open_time_s,float(record['sample_interval_s']))
    observed,_=observe_history(arrays['time_s'],arrays['discharged_count'],arrays['remaining_count'],config.gate_open_time_s)
    annotations=annotate_outcomes(observed,record.get('events',[]))
    for value in arrays.values():value.setflags(write=False)
    return ReplayBundle(record,arrays,config,features,pd.DataFrame(monitored),logs,annotations,specs)


def save_monitor_cache(bundle, root=Path('.')):
    path=Path(root)/'outputs/dashboard/m5/monitor_cache'/(bundle.record['run_id']+'.json')
    values=bundle.monitoring.ml_score
    write_json(path,dict(npz_sha256=bundle.record['npz_sha256'],times_s=bundle.arrays['time_s'].tolist(),
               specs=bundle.specs,ml_scores=values.tolist() if not values.isna().all() else None))


def prepare_portfolio(records, selected, root=Path('.')):
    """Portable real states plus verified frozen-score cache, kept OUT of Git."""
    root=Path(root);target=root/'outputs/dashboard/m5/portfolio';output=[]
    for scene,run_id in selected.items():
        r=next(r for r in records if r['run_id']==run_id)
        bundle=load_bundle(r,root,require_ml=True);save_monitor_cache(bundle,root)
        folder=target/run_id;folder.mkdir(parents=True,exist_ok=True)
        source=root/r['trajectory_path']
        shutil.copyfile(source,folder/'trajectory.npz')
        shutil.copyfile(source.with_suffix('.json'),folder/'trajectory.json')
        portable=dict(r,trajectory_path=str((folder/'trajectory.npz').relative_to(root)),scene=scene)
        output.append(portable)
    write_json(target/'catalog.json',dict(records=output,scope='Actual historical portfolio states; no new simulations or training'))
    return output
