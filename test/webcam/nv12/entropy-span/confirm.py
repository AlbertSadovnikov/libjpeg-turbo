#!/usr/bin/env python3
"""Direct confirmation against the actual preferred pre-span executable."""
from pathlib import Path
import json,subprocess,statistics,shutil,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-entropy-span')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
selected=Path('/tmp/mjpeg-memset-call/nv12');noise=work/'selected-identical';shutil.copy2(selected,noise)
assert hashlib.sha256(selected.read_bytes()).digest()==hashlib.sha256(noise.read_bytes()).digest()
binaries={'control':selected,'span':work/'span/nv12','identical':noise}
rows=[];brackets=[]
for trial in range(5):
 for candidate in (('span','identical') if trial%2==0 else ('identical','span')):
  group=[]
  for name in ('control',candidate,'control'):
   p=subprocess.run(['taskset','-c','0',str(binaries[name]),'fast','2','6',*map(str,frames[30:])],check=True,capture_output=True,text=True);assert not p.stderr,p.stderr
   r=json.loads(p.stdout);r.update(trial=trial,variant=name,candidate=candidate);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append(dict(trial=trial,variant=candidate,control_ms=a,candidate_ms=b,change_percent=100*(b/a-1)))
  (here/'confirm-results.json').write_text(json.dumps(dict(records=rows,brackets=brackets),indent=2)+'\n');print(brackets[-1],flush=True)
summary={}
for name in ('span','identical'):
 group=[r for r in brackets if r['variant']==name];a=statistics.mean(r['control_ms'] for r in group);b=statistics.mean(r['candidate_ms'] for r in group)
 summary[name]=dict(control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),improving_brackets=sum(r['change_percent']<0 for r in group),brackets=group)
(here/'confirm-summary.json').write_text(json.dumps({'cases':summary,'baseline_sha256':hashlib.sha256(selected.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(binaries['span'].read_bytes()).hexdigest(),'method':'Five selected/span/selected and five selected/identical/selected brackets, alternating order, CPU 0, 90 preloaded held-out frames, six measured passes after warmup. Direct comparison includes the new native entropy/profile regime; it is NOT pure source attribution, which uses the separately matched-profile cohort.'},indent=2)+'\n')
print(json.dumps(summary,indent=2))
