#!/usr/bin/env python3
"""All camera resolutions: preselected exact-fast candidates versus stock."""
from pathlib import Path
import sys, math, statistics, os, time
here=Path(__file__).resolve().parent
sys.path.insert(0,str(here.parent/'next-round'))
from common import *

camera_build=json.loads((here.parent/'multi-camera/build-summary.json').read_text())
restart_build=json.loads((here.parent/'restart-tu/build-summary.json').read_text())
segment_build=json.loads((here.parent/'restart-segment/build-summary.json').read_text())
assert all(not b['pgo'] and not b['explicit_tune'] for b in (camera_build,restart_build,segment_build))
selected={
 'Logitech':{'clang':camera_build['records']['clang-exact'],'gcc':camera_build['records']['gcc-deferred']},
 'LifeCam':{'clang':segment_build['records']['clang'],'gcc':restart_build['records']['gcc-tu-fast']}}
stock={cc:camera_build['records'][cc+'-stock'] for cc in ('clang','gcc')}
for record in [*stock.values(),*[r for c in selected.values() for r in c.values()]]:
 assert sha(record['binary'])==record['sha256']
 for p,digest in record['archives'].items():assert sha(p)==digest
protocol=dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),baseline='Stock fast-IDCT JPEG to NV12, geometry-aware driver; measure command',candidate='Preselected best stock-fast-exact path; fast 3 command',selection=selected,stock=stock,cpu=0,trials=3,order='stock/candidate/stock, reverse case order in middle round',passes='max(20, ceil(4000000 / pixels))',pgo=False,explicit_CPU_tune=False,core_LTO=True,inputs=[])
cases=[]
for camera in json.loads((here.parent/'multi-camera/inventory.json').read_text()):
 tag='LifeCam' if 'Microsoft' in camera['camera'] else 'Logitech'
 for size,g in sorted(camera['groups'].items(),key=lambda kv:(kv[1]['width']*kv[1]['height'],kv[1]['width'])):
  mode=max(g['modes'],key=lambda m:float(m['requested']['fps']));files=sorted(Path(mode['directory']).glob('frame_*.jpg'));assert len(files)==12
  entry=dict(camera=camera['camera'],tag=tag,size=size,batch=camera['batch'],requested_fps=mode['requested']['fps'],passes=max(20,math.ceil(4_000_000/(g['width']*g['height']))),files={str(p):sha(p) for p in files})
  protocol['inputs'].append(entry)
  for cc in ('clang','gcc'):cases.append((entry,cc,files))
save(here/'protocol.json',protocol)
records=[];brackets=[]
for trial in range(3):
 for entry,cc,files in (cases if trial%2==0 else cases[::-1]):
  group=[]
  for role in ('stock','best','stock'):
   record=stock[cc] if role=='stock' else selected[entry['tag']][cc]
   args=['measure',entry['passes']] if role=='stock' else ['fast',3,entry['passes']]
   env=os.environ.copy();env['MJPEG_SEGMENT']='1'
   p=run(['taskset','-c','0',record['binary'],*args,*files],text=True,env=env);assert not p.stderr,p.stderr
   r=json.loads(p.stdout);r.update(camera=entry['camera'],size=entry['size'],compiler=cc,trial=trial,role=role,binary=record['binary']);records.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1,(entry['camera'],entry['size'],cc)
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  bracket=dict(camera=entry['camera'],size=entry['size'],compiler=cc,trial=trial,stock_ms=a,best_ms=b,time_reduction_percent=100*(1-b/a));brackets.append(bracket)
  save(here/'results.json',dict(records=records,brackets=brackets))
  print(f"{trial+1}/3 {entry['tag']} {entry['size']} {cc}: {a:.4f} -> {b:.4f} ms ({bracket['time_reduction_percent']:+.2f}% less time)",flush=True)
summary=[]
for entry,cc,files in cases:
 rr=[r for r in brackets if r['camera']==entry['camera'] and r['size']==entry['size'] and r['compiler']==cc]
 a=statistics.mean(r['stock_ms'] for r in rr);b=statistics.mean(r['best_ms'] for r in rr)
 summary.append(dict(camera=entry['camera'],tag=entry['tag'],size=entry['size'],compiler=cc,stock_ms=a,best_ms=b,time_reduction_percent=100*(1-b/a),speedup=a/b,stock_decode_fps=1000/a,best_decode_fps=1000/b,minimum_bracket_reduction_percent=min(r['time_reduction_percent'] for r in rr),maximum_bracket_reduction_percent=max(r['time_reduction_percent'] for r in rr),brackets=rr))
save(here/'summary.json',summary)
print('Completed 29 camera/resolution groups, both compilers; all 174 brackets match stock output hashes.',flush=True)
