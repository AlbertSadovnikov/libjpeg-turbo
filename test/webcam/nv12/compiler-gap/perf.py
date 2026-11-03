#!/usr/bin/env python3
from pathlib import Path
import sys,re,collections
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-compiler-gap');rows=[]
for cc in ('clang','gcc'):
 b=WORK/'bin'/(cc+'-uv-paired');cmd=['taskset','-c','0',str(b),'fast','3','24',*map(str,FRAMES[30:])]
 p=subprocess.run(['perf','stat','-x,','-e','cycles:u,instructions:u,branches:u,branch-misses:u','--',*cmd],capture_output=True,text=True)
 rows.append({'compiler':cc,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'scope':'Entire process: includes input loading, warmup and hashing; 24 timed passes over 90 frames; not decode-only counters.'})
 if p.returncode:save(here/'perf.json',rows);continue
 data=W/(cc+'.perf.data')
 p=subprocess.run(['perf','record','-q','-e','cycles:u','-F','1999','-o',str(data),'--',*cmd],capture_output=True,text=True)
 rows[-1]['sampling_returncode']=p.returncode;rows[-1]['sampling_stderr']=p.stderr
 if p.returncode==0:
  report=run(['perf','report','-i',data,'--stdio','--no-children','--sort','symbol','--percent-limit','0.5'],text=True).stdout
  (W/(cc+'-perf-report.txt')).write_text(report);rows[-1]['report']=report
  # Keep full annotated output under /tmp, not in the compact repository JSON.
  sym=json.loads((here/'assembly.json').read_text())[cc+'-original']['symbol']
  p=subprocess.run(['perf','annotate','-i',str(data),'--stdio','--symbol',sym],capture_output=True,text=True)
  (W/(cc+'-perf-annotate.txt')).write_text(p.stdout+p.stderr)
  rows[-1]['annotation_returncode']=p.returncode
 save(here/'perf.json',rows);print(cc,'counter/sampling records saved.',flush=True)
