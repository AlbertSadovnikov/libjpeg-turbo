#!/usr/bin/env python3
from common import *
import statistics
B=WORK/'bin';rows=[];brackets=[]
# Separate cohort, longer passes, compare zero-skipping with the previously
# selected reduced contract and exact-fast UV with public stock fast output.
for trial in range(3):
 for cc in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  for comparison in (('reduced-zero','stock-exact') if trial%2==0 else ('stock-exact','reduced-zero')):
   group=[]
   for name in ('control','candidate','control'):
    if comparison=='stock-exact':
     r=execute(BASE/cc/'stock/nv12','measure',6,*FRAMES[30:]) if name=='control' else execute(B/(cc+'-uv-paired'),'fast',3,6,*FRAMES[30:])
    else:r=execute(BASE/cc/'current/nv12','fast',2,6,*FRAMES[30:]) if name=='control' else execute(B/(cc+'-zero-groups'),'fast',2,6,*FRAMES[30:])
    r.update(trial=trial,compiler=cc,comparison=comparison,variant=name);rows.append(r);group.append(r)
   assert len({v['hash'] for v in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
   brackets.append({'trial':trial,'compiler':cc,'comparison':comparison,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
   save(HERE/'confirm-results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc in ('clang','gcc'):
 summary[cc]={}
 for name in ('reduced-zero','stock-exact'):
  r=[v for v in brackets if v['compiler']==cc and v['comparison']==name];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
  summary[cc][name]={'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(HERE/'confirm-summary.json',summary)
