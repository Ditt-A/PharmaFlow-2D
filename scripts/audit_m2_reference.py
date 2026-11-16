"""Audit all downloaded Numbers tables; leave unsupported unit assignments unknown."""
import argparse
import json
from pathlib import Path
import re
import numpy as np
from numbers_parser import Document
from inspect_reference import inspect


def numeric(value):
    if value is None or isinstance(value,bool):return None
    try:
        result=float(value)
        return result if np.isfinite(result) else None
    except (ValueError,TypeError):return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('data/raw/zenodo_20554446'))
    parser.add_argument('--output',type=Path,default=Path('outputs/metrics/m2/reference_audit.json'))
    args=parser.parse_args();reports=[]
    for path in sorted(args.directory.glob('*.numbers')):
        base=inspect(path)
        doc=Document(str(path));tables=[]
        for sheet in doc.sheets:
            for table in sheet.tables:
                rows=table.rows(values_only=True)
                header=[str(v) if v is not None else '' for v in rows[0]]
                columns=[]
                for index,name in enumerate(header):
                    converted=[numeric(row[index]) for row in rows[1:]]
                    values=np.array([v for v in converted if v is not None])
                    text_labels=sorted({str(row[index])[:100] for row in rows[1:] if row[index] not in (None,'') and numeric(row[index]) is None})[:8]
                    columns.append({'name':name,'numeric_count':len(values),'minimum':float(values.min()) if len(values) else None,
                                    'maximum':float(values.max()) if len(values) else None,'median':float(np.median(values)) if len(values) else None,
                                    'numeric_fraction_of_data_rows':len(values)/(len(rows)-1),
                                    'units':None,'units_status':'unverified: headers and available primary metadata do not define units/normalization',
                                    'nondimensional':None,'nonnumeric_examples':text_labels,
                                    'fragment_warning':any(re.search(r'\d\s+[\d.\-]',v) for v in text_labels),
                                    'quality_note':'Whitespace-separated numeric fragments are not silently joined or reassigned; parseable subset may be biased.'})
                match=re.search(r'D\s*=\s*([\d.]+)\s*cm',sheet.name)
                tables.append({'sheet':sheet.name,'table':table.name,'rows':table.num_rows,'columns':columns,
                               'outlet_label_m':float(match.group(1))*.01 if match else None,
                               'has_particle_id_or_time_header':any(h.lower() in ('t','time','time_s','particle_id','id') for h in header),
                               'compatible_observable_candidates':[h for h in header if h in ('phi','uy','vx','vy','ay')],
                               'comparison_status':'Qualitative profiles only until units, axes, averaging and geometry are independently verified'})
        reports.append({'file':path.name,'md5':base['md5'],'bytes':base['bytes'],'zip_crc_ok':True,'tables':tables})
        print(path.name,len(tables),'tables audited',flush=True)
    report={'record_url':'https://zenodo.org/records/20554446','paper_doi':'10.1103/1ryw-6q89',
            'files':reports,'full_paper_access':'Publisher abstract accessible; PDF returned 401 during this audit. No inferred units from numerical magnitude.',
            'reproduction_claim':False,'geometry_limit':'Published quasi-2D 3D particles/front-back walls versus strict 2D disks.',
            'licenses':'No license inferred; raw files retained locally and not redistributed.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Saved',args.output)

if __name__=='__main__':main()
