#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,statistics
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-coefficient-cost')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
def run(binary,*args):
 p=subprocess.run(['taskset','-c','0',str(binary),*map(str,args)],capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr;return json.loads(p.stdout)
def save(name,x):(here/(name+'.json')).write_text(json.dumps(x,indent=2)+'\n')
# Verify the existing matched baseline before attributing costs to it.
validation={}
for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures]]:
 a=run('/tmp/mjpeg-paired-idct/control','validate',*inputs);b=run('/tmp/mjpeg-paired-idct/paired','validate',*inputs);assert a==b,label;validation[label]=b
save('baseline-validation',validation);print('Existing paired baseline: all captures and fixtures match.',flush=True)
counts=run(work/'probe','count',*frames);assert counts['mcus']==120*16200;assert counts['cleared_bytes']==120*16200*512
save('counters',counts);print('Counters collected.',flush=True)
# The diagnostic pass above also checks every MCU coefficient against a
# separate ordinary coefficient-API decode before accumulating its counters.
rows=[]
for trial in range(3):
 # Bracket the isolated stage by the full current NV12 pipeline; these cannot
 # be subtracted as an exact reconstruction cost.
 before=run('/tmp/mjpeg-paired-idct/paired','fast',2,3,*frames[30:])
 entropy=run(work/'probe','entropy',*frames[30:])
 kernels=run(work/'probe','kernels',frames[60])
 after=run('/tmp/mjpeg-paired-idct/paired','fast',2,3,*frames[30:]);assert before['hash']==after['hash']
 rows.append(dict(trial=trial,full_before=before,entropy=entropy,kernels=kernels,full_after=after));save('stages',rows)
 print('Stage batch',trial,flush=True)
summary={}
summary['full_nv12_ms']=dict(mean=statistics.mean(r[k]['mean_ms'] for r in rows for k in ('full_before','full_after')),rounds=[r[k]['mean_ms'] for r in rows for k in ('full_before','full_after')])
summary['entropy_controller_ms']=dict(mean=statistics.mean(v for r in rows for v in r['entropy']['rounds']),rounds=[v for r in rows for v in r['entropy']['rounds']])
for key in rows[0]['kernels']['rounds'][0]:
 vals=[v[key] for r in rows for v in r['kernels']['rounds']]
 summary[key]=dict(mean=statistics.mean(vals),min=min(vals),max=max(vals),ms_frame=statistics.mean(vals)*16200/1e6)
save('summary',summary);print(json.dumps(summary,indent=2))
