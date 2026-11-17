"""Audit public metadata/small text only; archive downloads and fitting are forbidden."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile
import pandas as pd
import requests
from pharmaflow.m4_data import digest,write_json
from pharmaflow.m6_benchmarks import delft_file_inventory,delft_acquisition_info,quantitative_eligibility

ALLOWED_HOSTS={'datadryad.org','data.4tu.nl','zenodo.org','arxiv.org'}
ARCHIVES=('.zip','.7z','.numbers','.gz','.tar')


def bounded_fetch(url, maximum_bytes, session=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ALLOWED_HOSTS or parsed.path.lower().endswith(ARCHIVES):
        raise ValueError('URL is outside the metadata/small-file allowlist')
    if not 0<maximum_bytes<=1000000:raise ValueError('Per-file download cap exceeded')
    session=session or requests
    with session.get(url,stream=True,timeout=40) as response:
        content=bytearray()
        for block in response.iter_content(min(8192,maximum_bytes+1)):
            content.extend(block)
            if len(content)>maximum_bytes:raise ValueError('Stream exceeds the download cap')
        return response.status_code,bytes(content)


def checksum_ok(raw, expected):
    if expected is None:return None
    algorithm,value=expected.split(':',1)
    return hashlib.new(algorithm,raw).hexdigest()==value


def obtain(config,root,fetch=False):
    base=root/'data/raw/m6';manifest=base/'download_manifest.json'
    previous=json.loads(manifest.read_text()) if manifest.exists() else {'artifacts':[]}
    by_id={r['id']:r for r in previous['artifacts']};records=[];transfer=0
    for a in config['artifacts']:
        path=(base/a['path']).resolve()
        if base.resolve() not in path.parents:raise ValueError('Unsafe raw-data path')
        expected=a['published_checksum'];cap=a['maximum_bytes']
        if cap>1000000 or (a['expected_bytes'] is not None and a['expected_bytes']>cap):raise ValueError('Forbidden artifact size')
        old=by_id.get(a['id'])
        if path.exists():
            raw=path.read_bytes()
            if len(raw)>cap or checksum_ok(raw,expected) is False:raise ValueError('Cached source checksum failed: '+a['id'])
            if old and digest(path)!=old['sha256']:raise ValueError('Metadata cache changed: '+a['id'])
            records.append(dict(a,state='cached_verified',http_status=200,bytes=len(raw),sha256=digest(path),
                                published_checksum_verified=checksum_ok(raw,expected)))
        elif not fetch:
            if old and old['state']=='access_failed':records.append(old)
            else:raise FileNotFoundError('Run --fetch-small first: '+a['id'])
        else:
            try:
                status,raw=bounded_fetch(a['url'],min(cap,config['download_policy']['maximum_total_new_bytes']-transfer))
                transfer+=len(raw)
                if status!=200:
                    records.append(dict(a,state='access_failed',http_status=status,response_bytes=len(raw),
                                        bytes=0,sha256=None,published_checksum_verified=False))
                    continue
                if a['expected_bytes'] is not None and len(raw)!=a['expected_bytes']:raise ValueError('Published size differs: '+a['id'])
                if checksum_ok(raw,expected) is False:raise ValueError('Published checksum failed: '+a['id'])
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                records.append(dict(a,state='downloaded',http_status=status,bytes=len(raw),sha256=digest(path),
                                    published_checksum_verified=checksum_ok(raw,expected)))
            except requests.RequestException as exc:
                records.append(dict(a,state='access_failed',http_status=None,error=type(exc).__name__,
                                    bytes=0,sha256=None,published_checksum_verified=False))
    result=dict(version=config['version'],retrieved_utc=datetime.now(timezone.utc).isoformat(),
                transferred_bytes_this_invocation=transfer,
                first_fetch_transferred_bytes=previous.get('first_fetch_transferred_bytes',
                    previous.get('transferred_bytes_this_invocation',transfer)),artifacts=records)
    write_json(manifest,result)
    return result


def audit(config,root,manifest):
    base=root/'data/raw/m6';out=root/'docs/results/m6';out.mkdir(parents=True,exist_ok=True)
    records=manifest['artifacts'];good={a['id']:base/a['path'] for a in records if a['http_status']==200}
    inventory=[];acquisition=[]
    dry=json.loads(good['dryad_files'].read_text())
    for f in dry['_embedded']['stash:files']:
        inventory.append(dict(source='dryad',dataset='376462',name=f['path'],bytes=f['size'],
                              published_checksum='sha256:'+f['digest'],content_inspected=False,
                              url='https://datadryad.org'+f['_links']['stash:download']['href']))
    child=[a for a in records if a['source']=='delft' and a['path'].endswith('/record.html') and a['http_status']==200]
    for item in child:
        page=(base/item['path']).read_text();identifier=item['path'].split('/')[1]
        files=delft_file_inventory(page,item['url'])
        if len(files)!=8:raise ValueError('Reviewed Delft inventory changed; inspect source before updating protocol')
        for f in files:
            content=base/'delft'/identifier/f['name']
            inventory.append(dict(source='delft',dataset=identifier,**f,content_inspected=content.exists()))
            if f['name'].startswith('info') and content.exists():
                angle=float(re.search(r'alp_([\d.]+)_d_',f['name']).group(1))
                plain=re.sub('<[^>]+>',' ',page)
                frequency=re.search(r'Recording frequency:\s*([\d.]+)\s*Hz',plain)
                catalog=float(frequency.group(1)) if frequency else None
                for row in delft_acquisition_info(content.read_text()):
                    acquisition.append(dict(dataset=identifier,nominal_angle_deg=angle,angle_reference='unresolved',
                        outlet_m=.1,catalog_sampling_hz=catalog,**row,
                        catalog_conflict=bool(row['header_verified'] and catalog and row['sampling_hz']!=catalog)))
    zen=json.loads(good['zenodo_record'].read_text())
    cached=[]
    for f in zen['files']:
        path=root/'data/raw/zenodo_20554446'/f['key']
        verified=False
        if path.exists():
            assert path.stat().st_size==f['size'] and checksum_ok(path.read_bytes(),f['checksum'])
            with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
            verified=True;cached.append(dict(path=str(path.relative_to(root)),bytes=f['size'],sha256=digest(path),md5=f['checksum']))
        inventory.append(dict(source='yogi',dataset='20554446',name=f['key'],bytes=f['size'],
            published_checksum=f['checksum'],content_inspected=verified,url=f['links']['self']))
    schema=json.loads((root/'docs/results/m2/reference_audit.json').read_text())
    experiment=next(f for f in schema['files'] if f['file']=='quasi2D-expt.numbers')
    experimental_tables=[dict(sheet=t['sheet'],table=t['table'],rows=t['rows'],
        columns=[c['name'] for c in t['columns']],units_verified=False,
        parseable_fractions={c['name']:c['numeric_fraction_of_data_rows'] for c in t['columns']}) for t in experiment['tables']]
    pd.DataFrame(inventory).to_csv(out/'file_inventory.csv',index=False,lineterminator='\n')
    pd.DataFrame(acquisition).to_csv(out/'acquisition_metadata.csv',index=False,lineterminator='\n')
    collection=(base/'delft/collection.html').read_text()
    plain=re.sub('<[^>]+>',' ',collection)
    rows=re.findall(r'(20|30|45|60|75|82,5|90) degrees,\s*(50|75|100|150|200)\s*mm,\s*(\d+) experiments',plain)
    listed=sum(int(r[2]) for r in rows)
    raw_bytes=sum(a['bytes'] for a in records if a['http_status']==200)
    summary=dict(decision='M6A_LIMITED_COMPARISON_ONLY',solver_attempts=0,parameter_fitting=False,ml_training=False,
        first_fetch_transferred_bytes=manifest['first_fetch_transferred_bytes'],
        raw_cached_bytes=raw_bytes,small_delft_text_bytes=sum(a['bytes'] for a in records if a['source']=='delft' and a['role']!='metadata'),
        dryad_content_bytes=sum(a['bytes'] for a in records if a['source']=='dryad' and a['role']!='metadata'),
        access_failures=[dict(id=a['id'],status=a['http_status']) for a in records if a['state']=='access_failed'],
        archive_downloads=0,reused_zenodo_bytes=sum(a['bytes'] for a in cached),
        delft_linked_children=len(child),delft_files=sum(f['source']=='delft' for f in inventory),
        collection_claimed_experiments=201,collection_listed_rows=len(rows),collection_listed_repetitions=listed,
        verified_acquisition_rows=sum(a['header_verified'] for a in acquisition),
        provisional_acquisition_rows=sum(not a['header_verified'] for a in acquisition),
        catalog_acquisition_conflicts=sum(a['catalog_conflict'] for a in acquisition),
        quantitative_matched_comparisons=0,calibration_performed=False)
    if len(rows)!=35 or listed!=231:raise ValueError('Collection-count evidence changed; do not silently assume repetitions')
    write_json(out/'source_audit_summary.json',summary)
    write_json(out/'provenance_manifest.json',dict(**manifest,cached_reference_files=cached,
        source_config_sha256=digest(root/'configs/m6/external_sources.json'),
        benchmark_protocol_sha256=digest(root/'configs/m6/benchmark_protocol.json'),
        unchanged_m5_taxonomy_config_sha256=digest(root/'configs/m5/operational_events.json'),
        historical_schema_path='docs/results/m2/reference_audit.json',historical_schema_sha256=digest(root/'docs/results/m2/reference_audit.json'),
        reuse_note='MD5/ZIP reverified; historical table audit reused without rewriting it',experimental_tables=experimental_tables))
    statuses={
        'dryad':['conditional_raw_access','conditional_raw_access','conditional_raw_access','definition_mismatch','startup_denominator_unknown','friction_not_characterized','conditional_raw_access'],
        'delft':['mass_series_not_located','mass_series_not_located','requires_PIV_and_calibration','definition_mismatch','not_annotated','angle_reference_unknown','requires_full_recording_review'],
        'yogi':['no_rate_table','no_time_series','native_units_unresolved','fraction_definition_unresolved','no_events_or_time','parameters_unresolved','no_time_series']}
    protocol=json.loads((root/'configs/m6/benchmark_protocol.json').read_text())
    matrix=[]
    for source,states in statuses.items():
        for b,state in zip(protocol['benchmarks'],states):
            matrix.append(dict(source=source,benchmark=b['id'],status=state,
                quantitative_validation_allowed=quantitative_eligibility({})['quantitative_validation_allowed'],
                calibration_allowed=False))
    pd.DataFrame(matrix).to_csv(out/'compatibility_matrix.csv',index=False,lineterminator='\n')
    scope={
      'dryad':['Startup/vibration coverage and sampling denominator unverified',
               'Flow-ending clogs reported; 5s exit-stop definition differs from M3',
               'Potential with raw crossing histories and reconciled boundaries; not yet established',
               'Metastable pauses reported; original ML cleaning excludes some static flow frames',
               'External Emptied is not an empty hopper; recirculating operation',
               'Raw duration and truncated/nonclogging inclusion need inspection'],
      'delft':['Requires full startup images plus retained-grain evidence',
               'No event annotations or interior 3D contact graph supplied',
               'PIV surface flow alone does not establish individual crossing criterion',
               'Potential in complete videos after timing/calibration verification',
               'Requires full fill/mass history; outlet ROI alone is insufficient',
               'Coverage and observation endpoints unresolved'],
      'yogi':['Not observable from static profiles/maps']*6}
    categories=['startup_blockage','post_discharge_arch','established_flow_arch','temporary_interruption',
                'completed_discharge','unresolved_or_censored']
    pd.DataFrame([dict(source=s,category=k,observability=note,observed_event_count=None,
        definition='M5 operational-observation-v1 unchanged; no external relabeling performed')
        for s,notes in scope.items() for k,note in zip(categories,notes)]).to_csv(
            out/'operational_event_scope.csv',index=False,lineterminator='\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--fetch-small',action='store_true',help='Allow only the frozen bounded small-file/metadata list')
    args=parser.parse_args();root=args.root.resolve()
    config=json.loads((root/'configs/m6/external_sources.json').read_text())
    audit(config,root,obtain(config,root,args.fetch_small))
