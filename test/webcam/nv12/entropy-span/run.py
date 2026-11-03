#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,statistics,hashlib,sys
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-entropy-span')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
mutations=[Path('/tmp/mjpeg-quantizer-cache')/f'changed-q{i}.jpg' for i in (1,2)];assert all(p.exists() for p in mutations)
def save(n,v):(here/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def executable(name):
 if name=='selected':return Path('/tmp/mjpeg-memset-call/nv12')
 return work/'identical' if name=='identical' else work/name/'nv12'
def run(name,*args):
 p=subprocess.run(['taskset','-c','0',str(executable(name)),*map(str,args)],capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr;return json.loads(p.stdout)
if '--timing-only' not in sys.argv:
 expected=json.loads((here.parent/'memset-call/validation.json').read_text());validation={}
 for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures],('changing-tables',[frames[60],mutations[0],*fixtures,mutations[1],frames[60],*fixtures[::-1],frames[60]])]:
  a=run('control','validate',*inputs);b=run('span','validate',*inputs);assert a==b,label
  if label!='changing-tables':assert a==expected[label]['avx2'],label
  validation[label]=b
 save('validation',validation);print('Independently profiled entropy variants match retained selected output.',flush=True)
 # Untimed independent coefficient-API decodes: compare the serialized bytes,
 # not just hashes, before discarding large traces. Keep compact SHA evidence.
 base=Path('/tmp/mjpeg-pgo-lto/clang-pgo-lto');source=work/'control-source/src'
 subprocess.run(['g++','-O3','-DNDEBUG','-std=c++17','-I'+str(base),'-I'+str(source),'-c',str(here/'coefficients.cc'),'-o',str(work/'coefficients.o')],check=True)
 build=json.loads((here/'build-summary.json').read_text())['cases']
 for name in ('control','span'):
  flags=build[name]['flags']
  subprocess.run(['clang++','-fuse-ld=gold','-flto=thin',*flags,str(work/'coefficients.o'),str(work/name/'libjpeg.a'),'-lm','-o',str(work/(name+'-coefficients'))],check=True)
 records=[]
 for frame in [*frames,*fixtures,*mutations]:
  values=[]
  for name in ('control','span'):
   p=subprocess.run(['taskset','-c','0',str(work/(name+'-coefficients')),str(frame)],capture_output=True);p.check_returncode();assert not p.stderr,p.stderr;values.append(p.stdout)
  assert values[0]==values[1],str(frame)
  records.append({'input':str(frame),'serialized_bytes':len(values[0]),'sha256':hashlib.sha256(values[0]).hexdigest()})
 save('coefficients',{'method':'Literal byte-for-byte comparison of every serialized coefficient and quantizer table, separate control/candidate processes; hashes saved only after equality. Native endian, same host.','frames':records})
 print('All coefficient bytes match on 120 captures, six fixtures and two DQT mutations.',flush=True)
rows=[];brackets=[]
for trial in range(5):
 for candidate in (('span','identical','selected') if trial%2==0 else ('selected','identical','span')):
  group=[]
  for name in ('control',candidate,'control'):
   r=run(name,'fast',2,3,*frames[30:]);r.update(trial=trial,variant=name,candidate=candidate);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append(dict(trial=trial,variant=candidate,control_ms=a,candidate_ms=b,change_percent=100*(b/a-1)))
  save('results',dict(records=rows,brackets=brackets));print(brackets[-1],flush=True)
summary={}
for name in ('span','identical','selected'):
 group=[r for r in brackets if r['variant']==name];a=statistics.mean(r['control_ms'] for r in group);b=statistics.mean(r['candidate_ms'] for r in group)
 summary[name]=dict(control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),improving_brackets=sum(r['change_percent']<0 for r in group),brackets=group)
save('summary',{'cases':summary,'method':'CPU 0; five control/candidate/control brackets each for span and identical-binary noise control; alternating order; 90 preloaded held-out frames, three passes after warmup. Each entropy source independently trained on same first 30 frames through selected inline-clear/register-Y/reduced-UV pipeline, accurate+fast. Native entropy objects avoid conflicting fresh/retained ThinLTO ProfileSummary metadata; other profiles and bytes preserved. Selected-binary comparison checks whether the changed object/profile regime regresses the actual preferred pipeline.'})
print(json.dumps(summary,indent=2))
