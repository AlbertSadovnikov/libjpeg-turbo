#!/usr/bin/env python3
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
B=WORK/'bin';validation={}
extra=sorted(Path('/tmp/mjpeg-paired-fast-chroma').glob('independent-q*.jpg'))
for host in ('clang','gcc'):
 validation[host]={}
 for label,files in [('capture',FRAMES),('boundaries',[*FIXTURES,*extra,FRAMES[60]])]:
  reference=execute(B/(host+'-uv-paired'),'validate',*files)
  for entropy in ('clang','gcc'):
   r=execute(B/(host+'-gap-'+entropy),'validate',*files);assert r==reference,(host,entropy,label)
  validation[host][label]=reference
 print(host,'crossed objects preserve all output contracts.',flush=True)
save(here/'validation.json',validation)
rows=[];brackets=[]
for trial in range(5):
 for host in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  group=[]
  for entropy in ('clang','gcc','clang'):
   r=execute(B/(host+'-gap-'+entropy),'fast',3,6,*FRAMES[30:]);r.update(host=host,entropy=entropy,trial=trial);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append({'host':host,'trial':trial,'clang_entropy_ms':a,'gcc_entropy_ms':b,'gcc_extra_ms':b-a,'gcc_change_percent':100*(b/a-1)})
  save(here/'results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for host in ('clang','gcc'):
 r=[v for v in brackets if v['host']==host];a=statistics.mean(v['clang_entropy_ms'] for v in r);b=statistics.mean(v['gcc_entropy_ms'] for v in r)
 summary[host]={'clang_entropy_ms':a,'gcc_entropy_ms':b,'gcc_extra_ms':b-a,'gcc_change_percent':100*(b/a-1),'brackets':r}
save(here/'summary.json',summary)
