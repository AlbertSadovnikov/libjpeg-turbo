#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,statistics
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-memset-call')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
names=['control','direct-libc','inline','avx2']
def save(n,v):(here/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def run(name,*args):
 p=subprocess.run(['taskset','-c','0',str(work/name/'nv12'),*map(str,args)],capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr;return json.loads(p.stdout)
expected=json.loads((here.parent/'coefficient-cost/variant-validation.json').read_text())['cases']
validation={}
for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures]]:
 validation[label]={}
 for name in names:
  r=run(name,'validate',*inputs);assert r==expected[label],(name,label);validation[label][name]=r
  if label=='capture':print(name,'matches retained best output on all 120 captures.',flush=True)
save('validation',validation);print('Capture and six-fixture validation passed, both IDCT methods and output padding.',flush=True)
rows=[];brackets=[];candidates=names[1:]
for trial in range(5):
 order=candidates[trial%3:]+candidates[:trial%3]
 if trial%2:order=order[::-1]
 for candidate in order:
  group=[]
  for name in ('control',candidate,'control'):
   r=run(name,'fast',2,3,*frames[30:]);r.update(trial=trial,variant=name,candidate=candidate);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append(dict(trial=trial,variant=candidate,control_ms=a,candidate_ms=b,change_percent=100*(b/a-1)))
  save('results',dict(records=rows,brackets=brackets));print(brackets[-1],flush=True)
summary={}
for name in candidates:
 group=[r for r in brackets if r['variant']==name];a=statistics.mean(r['control_ms'] for r in group);b=statistics.mean(r['candidate_ms'] for r in group)
 summary[name]=dict(control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),improving_brackets=sum(r['change_percent']<0 for r in group),brackets=group)
save('summary',dict(cases=summary,method='CPU 0, five control/candidate/control brackets per variant; rotated candidate order; 90 preloaded held-out frames, three passes after complete warmup; same register-rewritten paired Y and reduced UV; only controller clear changes, all other codec objects retain identical bytes and profiles'))
print(json.dumps(summary,indent=2))
