#!/usr/bin/env python3
from pathlib import Path
import sys,statistics,argparse
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
p=argparse.ArgumentParser();p.add_argument('--confirm',action='store_true');p.add_argument('--separate',action='store_true');args=p.parse_args()
PREFIX='separate-' if args.separate else ''
TAG='rst-separate' if args.separate else 'rst'
assert (here/(PREFIX+'suspension.json')).exists() and (here/(PREFIX+'coefficients.json')).exists()
B=WORK/'bin';inventory=json.loads((HERE.parent/'multi-camera/inventory.json').read_text());cases=[]
for c in inventory:
 life='Microsoft' in c['camera']
 for size in (('640x480','1280x720','1920x1080') if life else ('640x480','1920x1080')):
  mode=max(c['groups'][size]['modes'],key=lambda m:float(m['requested']['fps']));files=sorted(Path(mode['directory']).glob('frame_*.jpg'))
  for cc in ('clang','gcc'):
   for comparison in (('restart','stock') if life else ('restart',)):
    if args.confirm and (size!='1920x1080' or comparison!='restart'):continue
    cases.append((c,size,cc,comparison,files))
 if life and not args.confirm:
  mode=max(c['groups']['1920x1080']['modes'],key=lambda m:float(m['requested']['fps']))
  for cc in ('clang','gcc'):cases.append((c,'1920x1080',cc,'noise',sorted(Path(mode['directory']).glob('frame_*.jpg'))))
rows=[];brackets=[]
for trial in range(3):
 for c,size,cc,comparison,files in (cases if trial%2==0 else cases[::-1]):
  group=[]
  for role in ('control','candidate','control'):
   stock=role=='control' and comparison=='stock'
   binary=B/(cc+'-camera-stock') if stock else B/(cc+'-'+TAG+('-control' if role=='control' or comparison=='noise' else '-fast'))
   r=execute(binary,'measure',60 if args.confirm else 20,*files) if stock else execute(binary,'fast',3,60 if args.confirm else 20,*files)
   r.update(trial=trial,batch=c['batch'],compiler=cc,size=size,comparison=comparison,role=role);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append({'trial':trial,'camera':c['camera'],'batch':c['batch'],'compiler':cc,'size':size,'comparison':comparison,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
  save(here/(PREFIX+('confirm-results.json' if args.confirm else 'results.json')),{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary=[]
for c,size,cc,comparison,files in cases:
 r=[v for v in brackets if v['batch']==c['batch'] and v['compiler']==cc and v['size']==size and v['comparison']==comparison];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
 summary.append({'camera':c['camera'],'batch':c['batch'],'compiler':cc,'size':size,'comparison':comparison,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r})
save(here/(PREFIX+('confirm-summary.json' if args.confirm else 'summary.json')),summary)
