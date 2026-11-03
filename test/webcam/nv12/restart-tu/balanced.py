#!/usr/bin/env python3
"""Resolve transient/order noise with fixed ABBA/BAAB regression checks."""
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
B=WORK/'bin';c=next(c for c in json.loads((HERE.parent/'multi-camera/inventory.json').read_text()) if 'Logitech' in c['camera']);mode=max(c['groups']['1920x1080']['modes'],key=lambda m:float(m['requested']['fps']));files=sorted(Path(mode['directory']).glob('frame_*.jpg'));rows=[];brackets=[]
for trial in range(5):
 for cc in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  # A=old reference; B=candidate. Sham B uses A's identical executable.
  for comparison in (('candidate','noise') if trial in (1,3) else ('candidate',)):
   group=[];order=('A','B','B','A') if trial%2==0 else ('B','A','A','B')
   for role in order:
    name='fast' if role=='B' and comparison=='candidate' else 'control'
    r=execute(B/(cc+'-tu-'+name),'fast',3,60,*files);r.update(trial=trial,compiler=cc,comparison=comparison,role=role);rows.append(r);group.append(r)
   assert len({r['hash'] for r in group})==1
   a=statistics.mean(r['mean_ms'] for r in group if r['role']=='A');b=statistics.mean(r['mean_ms'] for r in group if r['role']=='B')
   brackets.append({'trial':trial,'compiler':cc,'comparison':comparison,'order':''.join(order),'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
   save(here/'balanced-results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc in ('clang','gcc'):
 summary[cc]={}
 for comparison in ('candidate','noise'):
  r=[v for v in brackets if v['compiler']==cc and v['comparison']==comparison];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
  summary[cc][comparison]={'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(here/'balanced-summary.json',summary)
