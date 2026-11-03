#!/usr/bin/env python3
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
w=Path('/tmp/mjpeg-paired-fast-chroma');B=WORK/'bin'
# Change component quantizer selection without changing entropy-coded bytes.
extra=[]
for comp in (1,2):
 data=bytearray(FRAMES[60].read_bytes());pos=2;changed=False
 while pos<len(data):
  assert data[pos]==255
  while data[pos]==255:pos+=1
  marker=data[pos];pos+=1
  if marker==0xda:break
  n=int.from_bytes(data[pos:pos+2],'big')
  if marker==0xc0:
   off=pos+10+3*comp;assert data[off] in (1,2);data[off]=0;changed=True
  pos+=n
 assert changed
 path=w/f'independent-q{comp}.jpg';path.write_bytes(data);extra.append(path)
save(here/'fixture-hashes.json',{str(p):sha(p) for p in extra})
validation={}
for cc in ('clang','gcc'):
 validation[cc]={}
 for label,files in [('capture',FRAMES),*[(p.stem,[p]) for p in FIXTURES],('independent-q',extra),('mixed',[FRAMES[60],*extra,*FIXTURES,FRAMES[60],*extra[::-1],FRAMES[60]])]:
  a=execute(B/(cc+'-uv-control'),'validate',*files);b=execute(B/(cc+'-uv-paired'),'validate',*files)
  assert a==b,(cc,label)
  stock=execute(BASE/cc/'stock/nv12','validate',1,*files)
  exact=next(r for r in b['cases'] if r['idct']=='fast' and r['mode']==3)
  assert exact['output_hash']==stock['hash'],(cc,label,'public stock fast')
  assert exact['UV_vs_same_idct']['max_abs']==0
  validation[cc][label]=b
 print(cc,'fast-exact mode is byte-exact to public stock-fast NV12; reduced and accurate contracts unchanged.',flush=True)
save(here/'validation.json',validation)
rows=[];brackets=[]
for trial in range(5):
 for cc in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  for comparison in (('reduced','stock') if trial%2==0 else ('stock','reduced')):
   group=[]
   for name in ('control','exact','control'):
    if name=='control' and comparison=='stock':r=execute(BASE/cc/'stock/nv12','measure',3,*FRAMES[30:])
    else:r=execute(B/(cc+('-uv-paired' if name=='exact' else '-uv-control')),'fast',3 if name=='exact' else 2,3,*FRAMES[30:])
    r.update(trial=trial,compiler=cc,comparison=comparison,variant=name);rows.append(r);group.append(r)
   if comparison=='stock':assert len({v['hash'] for v in group})==1
   else:assert group[0]['hash']==group[2]['hash']
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);v=group[1]['mean_ms']
   brackets.append({'trial':trial,'compiler':cc,'comparison':comparison,'control_ms':a,'exact_ms':v,'change_percent':100*(v/a-1)})
   save(here/'results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc in ('clang','gcc'):
 summary[cc]={}
 for name in ('reduced','stock'):
  r=[v for v in brackets if v['compiler']==cc and v['comparison']==name];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['exact_ms'] for v in r)
  summary[cc][name]={'control_ms':a,'exact_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(here/'summary.json',summary)
