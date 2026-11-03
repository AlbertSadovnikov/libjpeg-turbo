#!/usr/bin/env python3
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
B=WORK/'bin';frame=next(p for p in FIXTURES if p.stem=='dense');rows=[]
# One initial candidate invocation was much slower throughout despite adjacent
# controls being stable. Retain it and repeat this scene separately with bracketed controls.
for trial in range(3):
 group=[]
 for name in ('control','deferred','control'):
  r=execute(B/('gcc-loads-'+name),'fast',3,100,frame);r['variant']=name;group.append(r)
 assert len({r['hash'] for r in group})==1
 a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms'];rows.append({'trial':trial,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'records':group});save(here/'dense-confirmation.json',rows);print(rows[-1]['change_percent'],flush=True)
