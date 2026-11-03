#!/usr/bin/env python3
from pathlib import Path
import sys,json
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
rows=[]
for name in ('control','deferred'):
 b=WORK/'bin'/('gcc-loads-'+name)
 p=subprocess.run(['perf','stat','-x,','-e','cycles:u,instructions:u,branches:u,branch-misses:u','--','taskset','-c','0',str(b),'fast','3','24',*map(str,FRAMES[30:])],capture_output=True,text=True)
 rows.append({'variant':name,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'scope':'Whole process, including loading/warmup/hash, not decode-only counters.'});save(here/'perf.json',rows);print(name,'counters saved.',flush=True)
