#!/usr/bin/env python3
"""NV12 output checks and paired loop scheduling comparisons."""
from pathlib import Path
import json
import statistics
import subprocess
import argparse

here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-lut-pipeline')
config=json.loads((here/'experiment.json').read_text())
prefix=''
variants=('base','unroll4','special4','special-loop')
names=[c+'-'+k for c in ('gcc','clang') for k in variants]
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if r.returncode:print(r.stderr,flush=True)
    r.check_returncode();assert not r.stderr,r.stderr
    return json.loads(r.stdout)
fixtures=sorted((work/'fixtures').glob('*.jpg'));assert len(fixtures)==6
validation={}
for mode in ('accurate','fast'):
    validation[mode]={}
    # The existing sequence driver expects at least two frame arguments.
    for label,inputs in [('capture',frames),*[(p.stem,[p,p]) for p in fixtures]]:
        ref=None
        for name in names:
            row=run(['taskset','-c','0',config[name]['sequence_binary'],mode,'1',*inputs])
            if ref is None:ref=row['hash']
            else:assert row['hash']==ref,(mode,label,name,row)
        validation[mode][label]=dict(frames=len(inputs),matching_hash=ref)
(here/(prefix+'validation.json')).write_text(json.dumps(validation,indent=2)+'\n')
print('All NV12 hashes match: 120 camera frames and 6 boundary/table/restart fixtures, both IDCT modes.',flush=True)
records=[];hashes={}
for mode in ('accurate','fast'):
    for trial in range(3):
        order=names[trial:]+names[:trial]
        if trial%2:order.reverse()
        for name in order:
            row=run(['taskset','-c','0',config[name]['sequence_binary'],mode,'3',*frames[30:]])
            if mode in hashes:assert row['hash']==hashes[mode]
            else:hashes[mode]=row['hash']
            row.update(mode=mode,variant=name,trial=trial);records.append(row)
            (here/(prefix+'results.json')).write_text(json.dumps(records,indent=2)+'\n')
        print(mode,trial,'complete',flush=True)
summary={}
for name in names:
    summary[name]={mode+'_ms':statistics.mean(r['mean_ms'] for r in records if r['variant']==name and r['mode']==mode) for mode in ('accurate','fast')}
for compiler in ('gcc','clang'):
    base=summary[compiler+'-base']
    for kind in variants[1:]:
        row=summary[compiler+'-'+kind]
        row['time_change_percent']={mode:100*(row[mode+'_ms']/base[mode+'_ms']-1) for mode in ('accurate','fast')}
(here/(prefix+'summary.json')).write_text(json.dumps(dict(cases=summary,validation=validation,
    method='Matched archives, no PGO/LTO; three rotated/reversed rounds; 90 held-out preloaded frames, 3 passes after full warmup; CPU 0; JPEG to NV12 only'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
