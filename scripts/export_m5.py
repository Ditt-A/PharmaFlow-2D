"""Recreate three genuine historical scenes, offline viewers, PNG/GIF exports."""
from pathlib import Path
import json
import numpy as np
from pharmaflow.dashboard_data import historical_registry,load_bundle
from pharmaflow.dashboard_visuals import screenshot_bytes,export_gif
from pharmaflow.notebook_viewer import export_html
from pharmaflow.m4_data import digest,write_json

if __name__=='__main__':
    root=Path('.');records=historical_registry(root)
    selected=json.loads((root/'docs/results/m5/representative_scenes.json').read_text())['scenes']
    manifest=[]
    for scene,run_id in selected.items():
        b=load_bundle(next(r for r in records if r['run_id']==run_id),require_ml=True)
        if scene=='startup':center=b.annotations['arches'][0]['onset_time_s']+.10
        elif scene=='resumed':center=b.logs['resumptions'][0]['resume_observed_s']
        else:center=.18
        index=min(len(b.features)-1,int(np.searchsorted(b.arrays['time_s'],center)))
        prefix=root/'docs/results/m5'/scene
        prefix.with_suffix('.png').write_bytes(screenshot_bytes(b,index))
        start=max(0,int(np.searchsorted(b.arrays['time_s'],max(0,center-.35))))
        end=min(len(b.features)-1,start+round(.65/b.record['sample_interval_s']))
        animation=export_gif(b,prefix.with_suffix('.gif'),start,end,max_frames=30)
        offline=export_html(b,root/'outputs/dashboard/m5/exports'/(scene+'.html'))
        manifest.append(dict(scene=scene,run_id=run_id,trajectory_sha256=b.record['npz_sha256'],
            screenshot_frame=index,screenshot_time_s=float(b.arrays['time_s'][index]),animation=animation,
            png_sha256=digest(prefix.with_suffix('.png')),gif_sha256=digest(prefix.with_suffix('.gif')),offline_path=str(offline),
            annotations='No future truth in these exports; instantaneous diagnostics and chronological frozen scores only'))
    write_json(root/'docs/results/m5/visualization_manifest.json',dict(scenes=manifest,solver_attempts=0))
    print('Exported three real-state PNG/GIF/offline HTML scenes')
