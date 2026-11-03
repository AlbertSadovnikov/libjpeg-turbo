#!/usr/bin/env python3
from common import *
import statistics
B=WORK/'bin';expected=json.loads((HERE.parent/'no-mtune/validation.json').read_text())
extra=sorted(Path('/tmp/mjpeg-paired-fast-chroma').glob('independent-q*.jpg'))
yq=[Path('/tmp/mjpeg-quantizer-cache')/f'changed-q{i}.jpg' for i in (1,2)]
if not (HERE/'cd-validation.json').exists():
 validation={}
 for cc in ('clang','gcc'):
  validation[cc]={}
  for label,files in [('capture',FRAMES),*[(p.stem,[p]) for p in FIXTURES],('mixed',[FRAMES[60],*extra,*yq,*FIXTURES,FRAMES[60]])]:
   a=execute(B/(cc+'-control'),'validate',*files)
   if label!='mixed':assert a==expected[cc]['current'][label]
   for name in ('control-word','zero-groups'):
    r=execute(B/(cc+'-'+name),'validate',*files);assert a==r,(cc,name,label)
   validation[cc][label]=a
  print(cc,'metadata/zero candidates preserve all NV12 contracts and padding.',flush=True)
 save(HERE/'cd-validation.json',validation)
# Literal coefficient equality for the entropy representation change.
source=HERE.parent/'entropy-span/coefficients.cc';obj=WORK/'coefficients.o'
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',source,'-o',obj])
coefficients={}
for cc in ('clang','gcc'):
 cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
 for name,folder in [('reference',BASE/cc/'current'),('control-word',WORK/(cc+'-control-word'))]:
  run([cxx,'-O3',lto,'-fuse-ld=gold',obj,folder/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',B/(cc+'-'+name+'-coefficients')])
 coefficients[cc]=[]
 for frame in [*FRAMES,*FIXTURES,*extra,*yq]:
  streams=[]
  for name in ('reference','control-word'):
   p=run(['taskset','-c','0',B/(cc+'-'+name+'-coefficients'),frame]);assert not p.stderr,p.stderr;streams.append(p.stdout)
  assert streams[0]==streams[1],(cc,str(frame))
  coefficients[cc].append({'input':str(frame),'serialized_bytes':len(streams[0]),'sha256':hashlib.sha256(streams[0]).hexdigest()})
 save(HERE.parent/'entropy-control-word/coefficients.json',coefficients)
 print(cc,'literal coefficient/table equality passed for control-word change.',flush=True)
save(HERE.parent/'entropy-control-word/coefficients.json',coefficients)
# Optional read-only counters. Failure is recorded, never escalated.
try:
 p=subprocess.run(['perf','stat','-e','cycles,instructions,branches,branch-misses','taskset','-c','0',str(B/'clang-control'),'fast','2','1',str(FRAMES[60])],capture_output=True,text=True)
 save(HERE/'phase-a-perf.json',{'available':p.returncode==0,'returncode':p.returncode,'stderr':p.stderr})
except FileNotFoundError:save(HERE/'phase-a-perf.json',{'available':False,'reason':'perf not installed'})
rows=[];brackets=[]
for trial in range(5):
 for cc in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  for candidate in (('control-word','zero-groups','control') if trial%2==0 else ('control','zero-groups','control-word')):
   group=[]
   for name in ('control',candidate,'control'):
    r=execute(B/(cc+'-'+name),'fast',2,3,*FRAMES[30:]);r.update(trial=trial,compiler=cc,variant=name,candidate=candidate);rows.append(r);group.append(r)
   assert len({r['hash'] for r in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
   brackets.append({'trial':trial,'compiler':cc,'variant':candidate,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
   save(HERE/'cd-results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc in ('clang','gcc'):
 summary[cc]={}
 for name in ('control-word','zero-groups','control'):
  r=[v for v in brackets if v['compiler']==cc and v['variant']==name];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
  summary[cc][name]={'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(HERE/'cd-summary.json',summary)
# Dense/sparse same-output smoke timing cohorts, preloaded and warmed.
scenes={}
for cc in ('clang','gcc'):
 scenes[cc]={}
 for scene in ('dense','zeroac'):
  frame=next(p for p in FIXTURES if p.stem==scene);scenes[cc][scene]=[]
  for trial in range(3):
   group=[]
   for name in ('control','zero-groups','control'):
    r=execute(B/(cc+'-'+name),'fast',2,100,frame);r.update(variant=name);group.append(r)
   assert len({r['hash'] for r in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms'];scenes[cc][scene].append({'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
  print(cc,scene,'zero-group timings retained.',flush=True)
save(HERE.parent/'chroma-zero-groups/scene-results.json',scenes)
