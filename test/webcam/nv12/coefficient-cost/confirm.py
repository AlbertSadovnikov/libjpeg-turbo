#!/usr/bin/env python3
"""Independent confirmation of the register-only candidate, no rebuilding."""
from pathlib import Path
import subprocess,json,statistics
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-coefficient-cost')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
rows=[];brackets=[]
for trial in range(5):
 group=[]
 for name in ('control','registers','control'):
  p=subprocess.run(['taskset','-c','0',str(work/('g++-'+name)),'fast','2','3',*map(str,frames[30:])],capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr
  r=json.loads(p.stdout);r.update(trial=trial,variant=name);rows.append(r);group.append(r)
 assert len({r['hash'] for r in group})==1
 a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
 brackets.append(dict(trial=trial,control_ms=a,candidate_ms=b,change_percent=100*(b/a-1)))
 (here/'confirm-results.json').write_text(json.dumps(dict(records=rows,brackets=brackets),indent=2)+'\n');print(brackets[-1],flush=True)
a=statistics.mean(r['control_ms'] for r in brackets);b=statistics.mean(r['candidate_ms'] for r in brackets)
summary=dict(control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),brackets=brackets,reason='Initial register brackets have a wide effect-size range and control drift; check sustained improvement in a separate cohort.',method='CPU 0; five control/registers/control brackets, 90 preloaded held-out frames, three passes after warmup; same already validated binaries')
(here/'confirm-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
