"""Frozen acceptance checker. Keep this file and original input data unchanged."""
from pathlib import Path
import hashlib, json, sys
from decision import evaluate
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'frozen.sha256.json').read_text())
changed=[p for p,h in manifest.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
if changed:
    print('STOP: original check/input files changed:', ', '.join(changed)); sys.exit(2)
print('Original inputs and checker unchanged')
expected={'a':['READY','BLOCKED','UNKNOWN','BLOCKED','READY','UNKNOWN'],
          'b':['READY','READY','READY','BLOCKED','READY','UNKNOWN']}
passed=0; total=0; reports={}
for snap in ['a','b']:
    rows=json.loads((ROOT/f'data/snapshot_{snap}.json').read_text()); results=[]
    for row,want in zip(rows,expected[snap]):
        total+=1
        try:
            got=evaluate(row)
            ok=(got['status']==want and got['policy_id']=='POLICY-2'
                and got['source_id']==row['source'] and got['snapshot']==row['snapshot']
                and got['execution']=='none' and isinstance(got['reason'],str) and bool(got['reason'].strip()))
        except Exception as e:
            got={'error':str(e)};ok=False
        passed+=int(ok)
        print(('PASS' if ok else 'FAIL'),row['snapshot'],row['id'],'expected',want,'got',got.get('status',got))
        results.append(dict(id=row['id'],feature=row['feature'],owner=row['owner'],**got))
    reports[snap]=results
print(f'{passed}/{total} cases passed')
out=ROOT/'results';out.mkdir(exist_ok=True)
for snap,report in reports.items():
    (out/f'report_{snap}.json').write_text(json.dumps(report,indent=2))
    lines=[f'SNAPSHOT-{snap.upper()} | local computed results | synthetic',f'Overall acceptance score: {passed}/{total}']
    lines += [json.dumps(r) for r in report]
    (out/f'report_{snap}.txt').write_text('\n'.join(lines)+'\n')
sys.exit(0 if passed==total else 1)
