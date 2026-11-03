#!/usr/bin/env python3
from pathlib import Path
import sys,statistics,os,time
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
assert (here/'suspension.json').exists() and (here/'diagnostics.json').exists()
build=json.loads((here/'build-summary.json').read_text())['records'];old=json.loads((here.parent/'multi-camera/build-summary.json').read_text())['records']
for cc,r in build.items():assert sha(r['binary'])==r['sha256']
inv=json.loads((here.parent/'multi-camera/inventory.json').read_text());camera=next(c for c in inv if 'Logitech' in c['camera']);cases=[];inputs=[]
for size in ('320x180','424x240','480x270','960x540','640x480','1920x1080'):
 g=camera['groups'][size];mode=max(g['modes'],key=lambda m:float(m['requested']['fps']));files=sorted(Path(mode['directory']).glob('frame_*.jpg'));assert len(files)==12
 inputs.append(dict(size=size,requested_fps=mode['requested']['fps'],files={str(p):sha(p) for p in files}))
 for cc in ('clang','gcc'):
  for comparison in ('previous','stock'):cases.append((size,cc,comparison,files))
save(here/'protocol.json',dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),camera=camera['camera'],cpu=0,trials=3,passes=60,order='control/candidate/control, reverse cases in middle round',contract='stock-fast-exact NV12',pgo=False,explicit_tune=False,core_LTO=True,inputs=inputs,candidate=build,controls={cc:{name:old[cc+'-'+name] for name in ('stock', 'exact' if cc=='clang' else 'deferred')} for cc in ('clang','gcc')}))
records=[];brackets=[]
for trial in range(3):
 for size,cc,comparison,files in (cases if trial%2==0 else cases[::-1]):
  group=[]
  for role in ('control','candidate','control'):
   if role=='candidate':binary=build[cc]['binary'];args=['fast',3,60]
   else:
    variant='stock' if comparison=='stock' else ('exact' if cc=='clang' else 'deferred')
    binary=old[cc+'-'+variant]['binary'];assert sha(binary)==old[cc+'-'+variant]['sha256'];args=['measure',60] if comparison=='stock' else ['fast',3,60]
   r=execute(binary,*args,*files);r.update(size=size,compiler=cc,comparison=comparison,role=role,trial=trial);group.append(r);records.append(r)
  assert len({r['hash'] for r in group})==1,(size,cc,comparison)
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms'];r=dict(size=size,compiler=cc,comparison=comparison,trial=trial,control_ms=a,candidate_ms=b,time_reduction_percent=100*(1-b/a));brackets.append(r)
  save(here/'results.json',dict(records=records,brackets=brackets));print(f"{trial+1}/3 {size} {cc} vs {comparison}: {a:.4f} -> {b:.4f} ms ({r['time_reduction_percent']:+.2f}% less time)",flush=True)
summary=[]
for size,cc,comparison,files in cases:
 rr=[r for r in brackets if r['size']==size and r['compiler']==cc and r['comparison']==comparison];a=statistics.mean(r['control_ms'] for r in rr);b=statistics.mean(r['candidate_ms'] for r in rr)
 summary.append(dict(size=size,compiler=cc,comparison=comparison,control_ms=a,candidate_ms=b,time_reduction_percent=100*(1-b/a),brackets=rr))
save(here/'summary.json',summary);print('All edge and full-MCU control benchmarks completed with output hash equality.',flush=True)
