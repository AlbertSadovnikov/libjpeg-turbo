#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,statistics,sys
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-paired-idct')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
def run(name,*args):
 r=subprocess.run(['taskset','-c','0',str(work/name),*map(str,args)],capture_output=True,text=True);r.check_returncode();assert not r.stderr,r.stderr;return json.loads(r.stdout)
validation={}
for label,inputs in ([] if '--timing-only' in sys.argv else [('capture',frames),*[(p.stem,[p]) for p in sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'))]]):
 control=run('control','validate',*inputs);paired=run('paired','validate',*inputs)
 assert control==paired,label
 validation[label]=paired
if validation:
 (here/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');print('NV12 validation passed.',flush=True)
prefix='confirm-' if '--timing-only' in sys.argv else ''
rows=[];brackets=[]
for t in range(5):
 bracket=[]
 for name in ('control','paired','control'):
  r=run(name,'fast',2,3,*frames[30:]);r.update(variant=name,trial=t);rows.append(r);bracket.append(r)
 assert len({r['hash'] for r in bracket})==1
 c=statistics.mean([bracket[0]['mean_ms'],bracket[2]['mean_ms']]);p=bracket[1]['mean_ms']
 brackets.append(dict(trial=t,control_ms=c,paired_ms=p,change_percent=100*(p/c-1)))
 print(brackets[-1],flush=True)
 (here/(prefix+'results.json')).write_text(json.dumps(rows,indent=2)+'\n')
c=statistics.mean(r['control_ms'] for r in brackets);p=statistics.mean(r['paired_ms'] for r in brackets)
summary=dict(control_ms=c,paired_ms=p,change_percent=100*(p/c-1),brackets=brackets,method='CPU 0, five control/paired/control brackets, 90 preloaded held-out frames, 3 passes after warmup, same fused chroma path and codec archives')
(here/(prefix+'summary.json')).write_text(json.dumps(summary,indent=2)+'\n');print(summary)
