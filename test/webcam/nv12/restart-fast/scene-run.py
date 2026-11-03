#!/usr/bin/env python3
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--separate",action="store_true");args=p.parse_args()
PREFIX="separate-" if args.separate else ""
TAG="rst-separate" if args.separate else "rst"
assert (here/(PREFIX+'suspension.json')).exists();W=Path('/tmp/mjpeg-restart-fast')/('separate' if args.separate else '');B=WORK/'bin';rows=[]
for cc in ('clang','gcc'):
 for scene in ('ordinary-rst1.jpg','ordinary-rst2.jpg','zeroac-rst3.jpg','dense-rst2.jpg','ordinary-fill-rst3.jpg'):
  for trial in range(3):
   group=[]
   for name in (TAG+'-control',TAG+'-fast',TAG+'-control'):
    r=execute(B/(cc+'-'+name),'fast',3,50,Path('/tmp/mjpeg-restart-fast/fixtures')/scene);r['variant']=name;group.append(r)
   assert len({r['hash'] for r in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms'];rows.append({'compiler':cc,'scene':scene,'trial':trial,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'records':group});save(here/(PREFIX+'scene-results.json'),rows)
  print(cc,scene,'scene timings retained.',flush=True)
