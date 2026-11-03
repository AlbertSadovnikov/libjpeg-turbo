#!/usr/bin/env python3
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
B=WORK/'bin';rows=[]
for cc in ('gcc','clang'):
 control=B/('gcc-loads-control' if cc=='gcc' else 'clang-uv-paired')
 for scene in ('dense','zeroac'):
  frame=next(p for p in FIXTURES if p.stem==scene)
  for trial in range(3):
   group=[]
   for name,b in [('control',control),('deferred',B/(cc+'-loads-deferred')),('control',control)]:
    r=execute(b,'fast',3,50,frame);r['variant']=name;group.append(r)
   assert len({r['hash'] for r in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
   rows.append({'compiler':cc,'scene':scene,'trial':trial,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'records':group});save(here/'fixture-results.json',rows)
  print(cc,scene,'fixture rounds saved.',flush=True)
