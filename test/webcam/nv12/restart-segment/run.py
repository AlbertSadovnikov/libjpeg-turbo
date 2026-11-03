#!/usr/bin/env python3
from common_segment import *
import argparse,statistics
p=argparse.ArgumentParser();p.add_argument('--confirm',action='store_true');args=p.parse_args()
assert (here/'suspension.json').exists() and (here/'coefficients.json').exists()
inv=json.loads((HERE.parent/'multi-camera/inventory.json').read_text());cases=[]
for c in inv:
 life='Microsoft' in c['camera']
 for size in (('640x480','1280x720','1920x1080') if life else ('640x480','1920x1080')):
  mode=max(c['groups'][size]['modes'],key=lambda m:float(m['requested']['fps']));files=sorted(Path(mode['directory']).glob('frame_*.jpg'))
  for cc in ('clang','gcc'):
   for comp in ('segment','reference'):
    if args.confirm and size!='1920x1080':continue
    cases.append((c,size,cc,comp,files))
 if life and not args.confirm:
  mode=max(c['groups']['1920x1080']['modes'],key=lambda m:float(m['requested']['fps']))
  for cc in ('clang','gcc'):cases.append((c,'1920x1080',cc,'noise',sorted(Path(mode['directory']).glob('frame_*.jpg'))))
rows=[];brackets=[]
for trial in range(3):
 for c,size,cc,comp,files in (cases if trial%2==0 else cases[::-1]):
  group=[]
  for role in ('control','candidate','control'):
   if comp=='reference' and role=='control':r=execute_reference(cc,'fast',3,60 if args.confirm else 20,*files)
   else:r=execute_segment(cc,role=='candidate' and comp!='noise','fast',3,60 if args.confirm else 20,*files)
   r.update(trial=trial,camera=c['camera'],size=size,compiler=cc,comparison=comp,role=role);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms'];brackets.append({'trial':trial,'camera':c['camera'],'size':size,'compiler':cc,'comparison':comp,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
  save(here/('confirm-results.json' if args.confirm else 'results.json'),{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary=[]
for c,size,cc,comp,files in cases:
 r=[v for v in brackets if v['camera']==c['camera'] and v['size']==size and v['compiler']==cc and v['comparison']==comp];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r);summary.append({'camera':c['camera'],'size':size,'compiler':cc,'comparison':comp,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r})
save(here/('confirm-summary.json' if args.confirm else 'summary.json'),summary)
