#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,statistics,hashlib,sys
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-quantizer-cache')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
def save(n,v):(here/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def run(name,*args):
 p=subprocess.run(['taskset','-c','0',str(work/name),*map(str,args)],capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr;return json.loads(p.stdout)
# Keep entropy payload unchanged while making genuine per-frame Y DQT changes.
mutations=[]
for seed in (1,2):
 data=bytearray(frames[60].read_bytes());pos=2;changes=[]
 while pos<len(data):
  assert data[pos]==255
  while data[pos]==255:pos+=1
  marker=data[pos];pos+=1
  if marker==0xda:break
  length=int.from_bytes(data[pos:pos+2],'big');end=pos+length
  if marker==0xdb:
   q=pos+2
   while q<end:
    tag=data[q];q+=1;size=2 if tag>>4 else 1
    if tag&15==0:
     for i in range(64):
      off=q+i*size;old=int.from_bytes(data[off:off+size],'big');value=1+(old+seed*(i%5+1))%((1<<(8*size))-1)
      data[off:off+size]=value.to_bytes(size,'big');changes.append([off,old,value])
    q+=64*size
  pos=end
 assert len(changes)==64
 path=work/f'changed-q{seed}.jpg';path.write_bytes(data);mutations.append(path)
 save('changed-q'+str(seed),{'source':str(frames[60]),'output':str(path),'changes':changes,'sha256':hashlib.sha256(data).hexdigest(),'entropy_payload':'unchanged'})
if '--timing-only' not in sys.argv:
 check=run('check');check['kind_mapping']={'0':'two upstream SSE2','1':'register-rewritten paired baseline','2':'expanded quantizer memory operands'};check['additional_validation']='For each of 10000 synthetic coefficient pairs, also check changed full-range multiplier table and an in-place mutation at the same pointer.';save('kernel',check);print('Captured/synthetic kernel and quantizer-change validation passed.',flush=True)
 validation={};expected=json.loads((here.parent/'memset-call/validation.json').read_text())
 for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures],('changing-tables',[frames[60],mutations[0],*fixtures,mutations[1],frames[60],mutations[0],frames[60]])]:
  a=run('control','validate',*inputs);b=run('cached','validate',*inputs);assert a==b,label
  if label!='changing-tables':assert a==expected[label]['avx2'],label
  validation[label]=b
 save('validation',validation);print('120 captures, six fixtures and mixed changing-table sequence match exactly.',flush=True)
rows=[];brackets=[]
for trial in range(5):
 for name in (('cached','identical') if trial%2==0 else ('identical','cached')):
  group=[]
  for variant in ('control',name,'control'):
   r=run(variant,'fast',2,3,*frames[30:]);r.update(trial=trial,variant=variant,candidate=name);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append(dict(trial=trial,variant=name,control_ms=a,candidate_ms=b,change_percent=100*(b/a-1)))
  save('results',dict(records=rows,brackets=brackets));print(brackets[-1],flush=True)
summary={}
for name in ('cached','identical'):
 group=[r for r in brackets if r['variant']==name];a=statistics.mean(r['control_ms'] for r in group);b=statistics.mean(r['candidate_ms'] for r in group)
 summary[name]=dict(control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),improving_brackets=sum(r['change_percent']<0 for r in group),brackets=group)
save('summary',{'cases':summary,'method':'CPU 0; five control/candidate/control brackets each for cached quantizers and identical-binary noise control, alternating order; 90 preloaded held-out frames, three passes after warmup; selected inline AVX2 clear and register-rewritten Y in both; cache lookup/setup included in full NV12 clocks.'})
print(json.dumps(summary,indent=2))
