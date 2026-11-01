#!/usr/bin/env python3
"""NV12-only correctness, quality delta, and matched end-to-end measurements."""
from pathlib import Path
import json
import statistics
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-fused-chroma')
all_frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(all_frames)==120
frames=all_frames[30:]
def run(cmd):return subprocess.run(list(map(str,cmd)),check=True,capture_output=True,text=True)
result=run(['taskset','-c','0',work/'fused','validate',*all_frames]);assert not result.stderr,result.stderr
validation=json.loads(result.stdout)
(here/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print('All 120 frames: exact hashes, luma invariance, UV deltas, padded strides checked.',flush=True)
records=[];summary={}
for mode in ('accurate','fast'):
    names=['baseline','exact','reduced'] if mode=='accurate' else ['baseline','reduced']
    for trial in range(3):
        order=names[trial:]+names[:trial]
        if trial%2:order.reverse()
        for name in order:
            binary=work/('baseline' if name=='baseline' else 'fused');kind={'baseline':0,'exact':1,'reduced':2}[name]
            result=run(['taskset','-c','0',binary,mode,str(kind),'3',*frames]);assert not result.stderr,result.stderr
            row=json.loads(result.stdout);row.update(idct=mode,variant=name,trial=trial);records.append(row)
            (here/'results.json').write_text(json.dumps(records,indent=2)+'\n')
        print(mode,trial,'complete',flush=True)
    summary[mode]={}
    for name in names:
        rows=[r for r in records if r['idct']==mode and r['variant']==name]
        summary[mode][name]=dict(mean_ms=statistics.mean(r['mean_ms'] for r in rows))
    base=summary[mode]['baseline']['mean_ms']
    for row in summary[mode].values():row['time_change_percent']=100*(row['mean_ms']/base-1)
(here/'summary.json').write_text(json.dumps(dict(cases=summary,validation=validation,
    method='Matched GCC O3 non-PGO archives; three rotated/reversed rounds; 90 held-out preloaded frames, three passes after full warmup; CPU 0'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
