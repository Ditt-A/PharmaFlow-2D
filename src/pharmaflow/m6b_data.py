"""Bounded legitimate acquisition and immutable, non-interpreting schema recovery.

No DEM, fitting or training imports. Author Python/notebook cells are TEXT ONLY.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit, urljoin
import requests

HOSTS={'datadryad.org','zenodo.org','data.4tu.nl','raw.githubusercontent.com'}
DENIED={401,403,429}
CATALOG_MAXIMUM_RESERVED_BYTES=4032768


def utc():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path,algorithm='sha256'):
    h=hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def within(base,relative):
    base=Path(base).resolve();path=(base/relative).resolve()
    if base not in path.parents:raise ValueError('Path must stay inside the intended directory')
    return path


def check_artifact(a,plan):
    url=urlsplit(a['url'])
    if url.scheme!='https' or url.hostname not in HOSTS or url.username or url.password:
        raise ValueError('Only reviewed official HTTPS endpoints are permitted')
    if not a.get('provider_supported'):raise ValueError('Provider support/approval must be recorded')
    if url.path.lower().endswith(('.zip','.7z','.tar','.gz')):raise ValueError('Archive/mirroring requests are outside this milestone')
    cap=a['maximum_bytes'];budget=plan['budget']
    if not isinstance(cap,int) or isinstance(cap,bool) or not 0<cap<=budget['maximum_per_file_bytes']<=200000000:
        raise ValueError('Invalid file cap')
    if a['role']=='metadata' and cap>budget['maximum_metadata_file_bytes']:raise ValueError('Metadata cap exceeded')
    if a.get('expected_bytes') is not None and not 0<a['expected_bytes']<=cap:raise ValueError('Published size exceeds cap')
    if a['role']!='metadata' and not a.get('published_checksum'):raise ValueError('A reviewed payload needs a provider checksum')


def verified(path,a):
    if a.get('expected_bytes') is not None and Path(path).stat().st_size!=a['expected_bytes']:
        return False
    if a.get('published_checksum'):
        algorithm,digest=a['published_checksum'].split(':',1)
        if file_hash(path,algorithm)!=digest:return False
    return True


@contextmanager
def acquisition_lock(base):
    """A crash retains the lock and charged reservations; never silently retry."""
    lock=Path(base)/'.acquisition.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:raise RuntimeError('Another/interrupted acquisition owns the lock; inspect it before any continuation') from exc
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:yield
    finally:lock.unlink()


def request_small(url,cap,session=None,maximum_redirects=5):
    """No credentials, Range headers, proxy evasion, automatic retry or status bypass."""
    client=session or requests.Session()
    current=url
    for redirect in range(maximum_redirects+1):
        parsed=urlsplit(current)
        if parsed.scheme!='https' or parsed.hostname not in HOSTS:raise ValueError('Unreviewed redirect destination')
        with client.get(current,stream=True,timeout=40,allow_redirects=False,
                        headers={'Accept-Encoding':'identity'}) as response:
            if response.status_code in (301,302,303,307,308):
                if redirect==maximum_redirects:raise ValueError('Redirect limit exceeded')
                current=urljoin(current,response.headers['Location']);continue
            data=bytearray()
            for chunk in response.iter_content(min(8192,cap+1)):
                data.extend(chunk)
                if len(data)>cap:raise ValueError('Response exceeded its reserved transfer cap')
            return response.status_code,bytes(data),redirect
    raise ValueError('Redirect limit exceeded')


def acquire(plan,root=Path('.'),session=None):
    budget=plan['budget']
    if not 0<budget['maximum_transfer_bytes']<=200000000 or not 0<budget['maximum_curated_files_including_code_docs_reuse_and_failed_reservations']<=12:
        raise ValueError('Milestone hard acquisition limits cannot be enlarged')
    root=Path(root).resolve();base=root/'data/raw/m6b';base.mkdir(parents=True,exist_ok=True)
    signature=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    path=base/'acquisition_ledger.json'
    with acquisition_lock(base):
        ledger=json.loads(path.read_text()) if path.exists() else dict(version=plan['version'],plan_sha256=signature,
            attempts=[],denied_payload_hosts=[],reserved_transfer_ceiling_bytes=0,observed_response_payload_bytes=0)
        if ledger['plan_sha256']!=signature:raise ValueError('Plan changed; never reset a charged acquisition ledger')
        existing={a['id']:a for a in ledger['attempts']}
        for a in plan['artifacts']:
            check_artifact(a,plan);destination=within(base,a['path'])
            if a['id'] in existing:
                old=existing[a['id']]
                if old['state']=='complete':
                    if not destination.exists() or file_hash(destination)!=old['sha256'] or not verified(destination,a):
                        raise ValueError('Immutable raw input changed: '+a['id'])
                continue  # denied, failed and interrupted reservations are never silently retried
            curated=a['role']!='metadata'
            count=sum(r['curated_reservation'] for r in ledger['attempts'])
            if curated and count>=plan['budget']['maximum_curated_files_including_code_docs_reuse_and_failed_reservations']:
                raise ValueError('Twelve-file curated reservation budget exhausted')
            host=urlsplit(a['url']).hostname
            cached=within(root,a['reuse_path']) if a.get('reuse_path') else None
            reuse=bool(cached and cached.is_file())
            # Even an oversized-stream failure is charged for one terminal read
            # chunk. Its body must never escape the global reserved upper bound.
            cap=0 if reuse else a['maximum_bytes']+8192
            if (ledger['reserved_transfer_ceiling_bytes']+cap>plan['budget']['maximum_transfer_bytes']
                    or ledger['reserved_transfer_ceiling_bytes']+cap+CATALOG_MAXIMUM_RESERVED_BYTES>200000000):
                raise ValueError('200MB transfer reservation budget would be exceeded')
            if destination.exists():raise FileExistsError('Unregistered raw file; do not overwrite '+a['path'])
            entry=dict(a,state='reserved',curated_reservation=curated,started_utc=utc(),
                reserved_transfer_bytes=cap,transfer_bytes=None,bytes=0,sha256=None,
                provider_checksum_verified=False,reused=reuse,http_status=None)
            ledger['attempts'].append(entry);ledger['reserved_transfer_ceiling_bytes']+=cap
            atomic_json(path,ledger)  # charge BEFORE any I/O; failures remain charged
            try:
                if host in ledger['denied_payload_hosts'] and curated:
                    entry.update(state='blocked_by_prior_denial',reason='No further payload requests to this provider')
                    continue
                if reuse:
                    if not verified(cached,a):raise ValueError('Published checksum/size failed for historical source cache')
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with destination.open('xb') as stream, cached.open('rb') as source:shutil.copyfileobj(source,stream)
                    entry.update(http_status=200,transfer_bytes=0)
                else:
                    status,data,redirects=request_small(a['url'],a['maximum_bytes'],session,plan['budget']['maximum_redirects'])
                    ledger['observed_response_payload_bytes']+=len(data)
                    entry.update(http_status=status,transfer_bytes=len(data),redirects=redirects)
                    if status!=200:
                        entry.update(state='access_failed',reason='Provider HTTP '+str(status),
                                     response_sha256=hashlib.sha256(data).hexdigest())
                        if status in DENIED:
                            ledger['denied_payload_hosts']=sorted(set(ledger['denied_payload_hosts'])|{host})
                        continue
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with destination.open('xb') as stream:stream.write(data)
                if not verified(destination,a):
                    entry.update(state='integrity_failed',reason='Published size/checksum mismatch',sha256=file_hash(destination))
                    continue
                entry.update(state='complete',bytes=destination.stat().st_size,sha256=file_hash(destination),
                    provider_checksum_verified=bool(a.get('published_checksum')))
            except (requests.RequestException,ValueError,FileExistsError,OSError) as exc:
                entry.update(state='failed',reason=type(exc).__name__+': '+str(exc).split('?')[0])
            finally:
                entry['completed_utc']=utc();atomic_json(path,ledger)
        return ledger


def author_schema_evidence(path):
    """Static text/JSON inspection. Never import, exec, run or trust notebook outputs as raw trajectories."""
    path=Path(path)
    if path.suffix=='.ipynb':
        notebook=json.loads(path.read_text(encoding='utf-8'))
        cells=[''.join(c.get('source',[])) for c in notebook.get('cells',[]) if c.get('cell_type') in ('code','markdown')]
        code='\n\n'.join(cells)
        outputs=sum(len(c.get('outputs',[])) for c in notebook.get('cells',[]))
    else:code=path.read_text(encoding='utf-8');outputs=0
    evidence=[]
    for number,line in enumerate(code.splitlines(),1):
        if any(token.lower() in line.lower() for token in ('loadmat','pix','mm','frame','fps','position','velocity','radius','radii','outlet','mass','species')):
            evidence.append(dict(source_line=number,text=line[:240]))
    return dict(file=path.name,sha256=file_hash(path),artifact_type='author_code_not_experimental_measurements',
                executed=False,notebook_outputs_not_parsed_as_measurements=outputs,evidence=evidence)


def parse_delft_info(path):
    """Header-supported acquisition fields only. Pixel/calibration meanings remain unresolved."""
    from .m6_benchmarks import delft_acquisition_info
    rows=delft_acquisition_info(Path(path).read_text())
    for r in rows:
        r.update(source_sha256=file_hash(path),kind='acquisition_metadata_not_flow',
                 timestamp_s=None,particle_id=None,mass_discharge_kg_s=None,velocity_m_s=None,
                 coordinate_units=None)
    return rows


def parse_yogi_profiles(path):
    """Literal column labels, nullable native numbers and exact strings; no repaired units/values."""
    import math
    from numbers_parser import Document
    doc=Document(str(path));schema=[];profiles=[];source_hash=file_hash(path)
    def numeric(value):
        if value is None or isinstance(value,bool):return None
        try:
            x=float(value);return x if math.isfinite(x) else None
        except (ValueError,TypeError):return None
    for sheet in doc.sheets:
        for table in sheet.tables:
            rows=table.rows(values_only=True);headers=[str(v) if v is not None else '' for v in rows[0]]
            schema.append(dict(sheet=sheet.name,table=table.name,rows=len(rows),columns=headers,
                time_or_particle_ids_supplied=any(h.lower() in ('time','time_s','frame','particle_id','id') for h in headers),
                physical_units_verified=False,coordinate_origin_sign=None))
            if 'uy' not in headers:continue
            for index,row in enumerate(rows[1:],1):
                record=dict(source_row=index,sheet=sheet.name,table=table.name,units_verified=False,
                            source_sha256=source_hash)
                for field,value in zip(headers,row):
                    record[field+'_raw']=str(value) if value is not None else None
                    record[field+'_native']=numeric(value)
                record['native_y_uy_parseable']=record['y_native'] is not None and record['uy_native'] is not None
                profiles.append(record)
    return schema,profiles


COMPARISON_GATES=('measurement_accessible','units_and_coordinates_verified',
    'geometry_and_boundaries_documented','observable_definition_matched',
    'repeats_or_uncertainty_limitations_explicit','model_form_considered')


def compatibility_gate(pair):
    """Evaluate explicit evidence, never infer units or compute an agreement score."""
    evidence=pair['gates']
    missing=[key for key in COMPARISON_GATES if evidence.get(key) is not True]
    if evidence.get('measurement_accessible') is not True:
        status='BLOCKED_BY_MISSING_INFORMATION'
    elif pair.get('fatal_unmatched_model_form') is True:
        status='INCOMPATIBLE_MODEL_FORM'
    elif not missing:
        status='QUANTITATIVELY_COMPARABLE'
    elif pair.get('native_qualitative_interpretation_supported') is True:
        status='QUALITATIVE_ONLY'
    else:
        status='BLOCKED_BY_MISSING_INFORMATION'
    return dict(id=pair['id'],source=pair['source'],observable=pair['observable'],
                classification=status,unmet_gates=missing,
                agreement_score_allowed=status=='QUANTITATIVELY_COMPARABLE',
                calibration_claim_allowed=False)


def verify_acquisition(plan,root=Path('.')):
    """Offline check of every successful raw input against ledger AND provider checksum."""
    root=Path(root);base=root/'data/raw/m6b'
    ledger=json.loads((base/'acquisition_ledger.json').read_text())
    signature=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if signature!=ledger['plan_sha256']:raise ValueError('Plan does not match charged ledger')
    if len({a['id'] for a in ledger['attempts']})!=len(ledger['attempts']):raise ValueError('Duplicate acquisition IDs')
    for a in ledger['attempts']:
        check_artifact(a,plan)
        if a['state']=='complete':
            p=within(base,a['path'])
            if not p.is_file() or file_hash(p)!=a['sha256'] or not verified(p,a):
                raise ValueError('Raw input integrity failure: '+a['id'])
    count=sum(a['curated_reservation'] for a in ledger['attempts'])
    reserved=sum(a['reserved_transfer_bytes'] for a in ledger['attempts'])
    if count>min(12,plan['budget']['maximum_curated_files_including_code_docs_reuse_and_failed_reservations']) or reserved>min(200000000,plan['budget']['maximum_transfer_bytes']):
        raise ValueError('Acquisition budget exceeded')
    if reserved!=ledger['reserved_transfer_ceiling_bytes']:raise ValueError('Transfer reservation mismatch')
    return ledger


def discover_delft_metadata(root=Path('.'),session=None):
    """Four bounded public catalog requests, matching the provider's search UI.

    Metadata only, <=4,032,768 reserved bytes in addition to the frozen plan.
    This does not download the listed experimental payloads or private APIs.
    """
    parent=Path(root)/'data/raw/m6b'
    acquisition_path=parent/'acquisition_ledger.json'
    if acquisition_path.exists():
        prior=json.loads(acquisition_path.read_text())
        if prior['reserved_transfer_ceiling_bytes']+CATALOG_MAXIMUM_RESERVED_BYTES>200000000:
            raise ValueError('Combined acquisition/catalog transfer budget would be exceeded')
    base=parent/'catalog';base.mkdir(parents=True,exist_ok=True)
    path=base/'ledger.json'
    client=session or requests.Session()
    calls=[('hopper_search','POST','https://data.4tu.nl/v3/datasets/search','hopper discharge'),
           ('author_search','POST','https://data.4tu.nl/v3/datasets/search','Fransen'),
           ('outlet150','GET','https://data.4tu.nl/v2/articles/ea3e3e6e-67ce-4629-a889-be0b04c735dd',None),
           ('outlet200','GET','https://data.4tu.nl/v2/articles/4fc30415-6463-490b-ba87-032ae94b39d1',None)]
    with acquisition_lock(base):
        ledger=json.loads(path.read_text()) if path.exists() else dict(attempts=[],maximum_requests=4,maximum_reserved_bytes=4032768)
        for key,method,url,query in calls:
            previous=next((a for a in ledger['attempts'] if a['id']==key),None)
            destination=base/(key+'.json')
            if previous:
                if previous['state']=='complete' and file_hash(destination)!=previous['sha256']:raise ValueError('Catalog snapshot changed')
                continue
            if any(a.get('status') in DENIED for a in ledger['attempts']):break
            body=dict(search_for=query,search_scope=['title','description','tag','author'],search_operator='AND',page_size=20,page=1,is_latest=1) if query else None
            entry=dict(id=key,url=url,method=method,request_json=body,state='reserved',reserved_bytes=1008192,started_utc=utc())
            ledger['attempts'].append(entry);atomic_json(path,ledger)
            try:
                with client.request(method,url,json=body,stream=True,timeout=40,allow_redirects=False,
                                    headers={'Accept-Encoding':'identity'}) as response:
                    content=bytearray()
                    for chunk in response.iter_content(8192):
                        content.extend(chunk)
                        if len(content)>1000000:raise ValueError('Catalog metadata cap exceeded')
                    entry.update(status=response.status_code,transfer_bytes=len(content))
                    if response.status_code!=200:
                        entry.update(state='access_failed');continue
                    json.loads(content)  # catalog JSON only; no listed downloads followed
                    with destination.open('xb') as stream:stream.write(content)
                    entry.update(state='complete',sha256=file_hash(destination),path=destination.name)
            except (requests.RequestException,ValueError,OSError) as exc:
                entry.update(state='failed',reason=type(exc).__name__+': '+str(exc).split('?')[0])
            finally:
                entry['completed_utc']=utc();atomic_json(path,ledger)
    return ledger
