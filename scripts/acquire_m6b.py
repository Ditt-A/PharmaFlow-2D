"""Bounded M6B-A acquisition only; failed/denied requests are never silently retried."""
import argparse
import json
from pathlib import Path
from pharmaflow.m6b_data import acquire,discover_delft_metadata

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--delft-catalog',action='store_true',help='Four official public metadata calls; no experimental payloads')
    args=p.parse_args();root=args.root.resolve()
    plan=json.loads((root/'configs/m6b/acquisition_plan.json').read_text())
    ledger=acquire(plan,root)
    for r in ledger['attempts']:print(r['id'],r['state'],r['http_status'],r['bytes'])
    print('Charged curated reservations:',sum(r['curated_reservation'] for r in ledger['attempts']))
    print('Observed payload bytes:',ledger['observed_response_payload_bytes'])
    print('Reserved upper-bound transfer bytes:',ledger['reserved_transfer_ceiling_bytes'])
    if args.delft_catalog:
        catalog=discover_delft_metadata(root)
        print('Catalog:',[(a['id'],a['state'],a.get('transfer_bytes')) for a in catalog['attempts']])
