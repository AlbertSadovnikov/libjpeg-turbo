#!/usr/bin/env python3
from pathlib import Path
import sys,statistics,argparse
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
p=argparse.ArgumentParser();p.add_argument('--confirm',action='store_true');args=p.parse_args()
assert (here/'validation.json').exists() and (here/'coefficients.json').exists()
B=WORK/'bin';rows=[];brackets=[]
# no-hoist is byte-identical to control, so a second duplicate noise cohort
# would add no evidence. Keep one explicit identical-binary noise control.
cases=[('gcc','deferred'),('gcc','control'),('clang','deferred')]
if args.confirm:cases=[(cc,n) for cc,n in cases if n!='control']
for trial in range(3 if args.confirm else 5):
 for cc,name in (cases if trial%2==0 else cases[::-1]):
  control=B/('gcc-loads-control' if cc=='gcc' else 'clang-uv-paired');candidate=B/(cc+'-loads-'+name)
  group=[]
  for label,binary in [('control',control),('candidate',candidate),('control',control)]:
   r=execute(binary,'fast',3,6 if args.confirm else 3,*FRAMES[30:]);r.update(trial=trial,compiler=cc,variant=name,role=label);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append({'trial':trial,'compiler':cc,'variant':name,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
  save(here/('confirm-results.json' if args.confirm else 'results.json'),{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc,name in cases:
 r=[v for v in brackets if v['compiler']==cc and v['variant']==name];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
 summary[cc+'-'+name]={'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(here/('confirm-summary.json' if args.confirm else 'summary.json'),summary)
