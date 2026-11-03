#!/usr/bin/env python3
from common_segment import *
import statistics
rows=[]
for cc in ('clang','gcc'):
 for scene in ('ordinary-rst1.jpg','ordinary-rst2.jpg','zeroac-rst3.jpg','dense-rst2.jpg','ordinary-fill-rst3.jpg'):
  for trial in range(3):
   group=[execute_segment(cc,on,'fast',3,50,Path('/tmp/mjpeg-restart-fast/fixtures')/scene) for on in (False,True,False)]
   assert len({r['hash'] for r in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
   rows.append(dict(compiler=cc,scene=scene,trial=trial,control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),records=group))
   save(here/'scene-results.json',rows)
  print(cc,scene,'scene timings retained.',flush=True)
