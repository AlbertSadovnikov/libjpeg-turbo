#!/usr/bin/env python3
from pathlib import Path
import sys,statistics,argparse
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
p=argparse.ArgumentParser();p.add_argument('--confirm',action='store_true');p.add_argument('--paired-entry',action='store_true');args=p.parse_args()
TAG='two-mcu-pair' if args.paired_entry else 'two-mcu'
PREFIX='paired-' if args.paired_entry else ''
assert (here/(PREFIX+'validation.json')).exists()
B=WORK/'bin';rows=[];brackets=[];passes=6 if args.confirm else 3;rounds=3 if args.confirm else 5
for trial in range(rounds):
 for cc in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  for candidate in ((TAG,) if args.confirm else ((TAG,TAG+'-control') if trial%2==0 else (TAG+'-control',TAG))):
   group=[]
   for name in (TAG+'-control',candidate,TAG+'-control'):
    r=execute(B/(cc+'-'+name),'fast',3,passes,*FRAMES[30:]);r.update(compiler=cc,trial=trial,variant=name,candidate=candidate);rows.append(r);group.append(r)
   assert len({r['hash'] for r in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
   brackets.append({'compiler':cc,'trial':trial,'candidate':candidate,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
   save(here/(PREFIX+('confirm-results.json' if args.confirm else 'results.json')),{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc in ('clang','gcc'):
 summary[cc]={}
 for candidate in sorted(set(r['candidate'] for r in brackets)):
  r=[v for v in brackets if v['compiler']==cc and v['candidate']==candidate];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
  summary[cc][candidate]={'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(here/(PREFIX+('confirm-summary.json' if args.confirm else 'summary.json')),summary)
