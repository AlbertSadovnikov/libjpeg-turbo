#!/usr/bin/env python3
"""Fixed-build, sequential resolution sweep; previous cohorts stay untouched."""
from common_segment import *
import math, statistics, time

build=json.loads((here/'build-summary.json').read_text())['records']
for cc,r in build.items():
 assert sha(r['binary'])==r['sha256']
 for path,digest in r['archives'].items():assert sha(path)==digest
previous=json.loads((here.parent/'restart-tu/candidates.json').read_text())
for cc,r in previous.items():assert sha(r['target'])==r['sha256']
assert all(v['entropy']['same_normalized_instructions'] and v['coefficient']['same_normalized_instructions'] for v in json.loads((here/'audit.json').read_text()).values())
inv=json.loads((here.parent/'multi-camera/inventory.json').read_text())
cases=[];inputs=[]
for camera in inv:
 for size,g in sorted(camera['groups'].items(),key=lambda item:(item[1]['width']*item[1]['height'],item[1]['width'])):
  mode=max(g['modes'],key=lambda m:float(m['requested']['fps']))
  files=sorted(Path(mode['directory']).glob('frame_*.jpg'));assert len(files)==12
  passes=max(20,math.ceil(4_000_000/(g['width']*g['height'])))
  # Match the install guard; only LifeCam has restart-bearing camera frames.
  eligible=('Microsoft' in camera['camera'] and g['width']%16==0 and g['height']%8==0)
  entry=dict(camera=camera['camera'],batch=camera['batch'],size=size,width=g['width'],height=g['height'],requested_fps=mode['requested']['fps'],passes=passes,segment_eligible=eligible,files={str(p):sha(p) for p in files})
  inputs.append(entry)
  for cc in ('clang','gcc'):cases.append((entry,cc,files))
protocol=dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),cpu=0,trials=3,order='control/candidate/control; case order reversed in odd trials',contract='fast 3: stock-fast-exact NV12',comparison='frozen restart-tu vs restart-segment enabled',selection='highest requested FPS mode per captured resolution; twelve frames per mode',passes='max(20, ceil(4000000 / image_pixels))',pgo=False,explicit_CPU_tune=False,core_LTO=True,inputs=inputs,binaries={cc:{'reference':previous[cc]['sha256'],'candidate':build[cc]['sha256']} for cc in build})
save(here/'all-resolutions-protocol.json',protocol)
records=[];brackets=[]
for trial in range(3):
 for entry,cc,files in (cases if trial%2==0 else cases[::-1]):
  group=[]
  for role in ('control','candidate','control'):
   result=(execute_reference if role=='control' else lambda compiler,*args:execute_segment(compiler,True,*args))(cc,'fast',3,entry['passes'],*files)
   result.update(trial=trial,camera=entry['camera'],size=entry['size'],compiler=cc,role=role)
   records.append(result);group.append(result)
  assert len({r['hash'] for r in group})==1,(entry['size'],cc)
  control=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);candidate=group[1]['mean_ms']
  bracket=dict(trial=trial,camera=entry['camera'],size=entry['size'],compiler=cc,control_ms=control,candidate_ms=candidate,change_percent=100*(candidate/control-1))
  brackets.append(bracket)
  save(here/'all-resolutions-results.json',dict(records=records,brackets=brackets))
  print(f"{trial+1}/3 {entry['camera'].split()[0]} {entry['size']} {cc}: {control:.4f} -> {candidate:.4f} ms ({bracket['change_percent']:+.2f}%)",flush=True)
summary=[]
for entry,cc,files in cases:
 rr=[r for r in brackets if r['camera']==entry['camera'] and r['size']==entry['size'] and r['compiler']==cc]
 a=statistics.mean(r['control_ms'] for r in rr);b=statistics.mean(r['candidate_ms'] for r in rr)
 summary.append(dict(camera=entry['camera'],size=entry['size'],compiler=cc,segment_eligible=entry['segment_eligible'],passes=entry['passes'],control_ms=a,candidate_ms=b,candidate_decode_fps=1000/b,change_percent=100*(b/a-1),bracket_min_percent=min(r['change_percent'] for r in rr),bracket_max_percent=max(r['change_percent'] for r in rr),brackets=rr))
save(here/'all-resolutions-summary.json',summary)
print('All 29 camera/resolution groups, both compilers, three brackets passed output-hash checks.',flush=True)
