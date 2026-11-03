#!/usr/bin/env python3
"""Paired no-PGO Clang check: remove only the explicit mtune setting."""
from pathlib import Path
import json,subprocess,statistics,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3]
tuned=Path('/tmp/mjpeg-lto-only/current/nv12');untuned=Path('/tmp/mjpeg-no-mtune/clang/current/nv12')
a=json.loads((here.parent/'lto-only/build-summary.json').read_text());b=json.loads((here/'build-summary.json').read_text())
assert a['pgo'] is False and b['pgo'] is False
assert a['native_support_sha256']==b['native_support_sha256']
assert hashlib.sha256(tuned.read_bytes()).hexdigest()==a['cases']['current']['binary_sha256']
assert hashlib.sha256(untuned.read_bytes()).hexdigest()==b['cases']['clang']['current']['sha256'][str(untuned)]
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
rows=[];brackets=[]
for trial in range(3):
 group=[]
 for name,binary in [('znver2',tuned),('default',untuned),('znver2',tuned)]:
  p=subprocess.run(['taskset','-c','0',str(binary),'fast','2','6',*map(str,frames[30:])],check=True,capture_output=True,text=True);assert not p.stderr,p.stderr
  r=json.loads(p.stdout);r.update(trial=trial,variant=name);rows.append(r);group.append(r)
 assert len({r['hash'] for r in group})==1
 c=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);v=group[1]['mean_ms']
 brackets.append(dict(trial=trial,znver2_ms=c,default_ms=v,change_percent=100*(v/c-1)))
 (here/'clang-mtune-results.json').write_text(json.dumps(dict(records=rows,brackets=brackets),indent=2)+'\n');print(brackets[-1],flush=True)
c=statistics.mean(r['znver2_ms'] for r in brackets);v=statistics.mean(r['default_ms'] for r in brackets)
(here/'clang-mtune-summary.json').write_text(json.dumps(dict(znver2_ms=c,default_ms=v,change_percent=100*(v/c-1),brackets=brackets,pgo=False,method='Three Clang current znver2/default/znver2 brackets, both ThinLTO and no PGO, same source snapshots/BMI2 entropy and identical native support, CPU 0, 90 preloaded held-out frames, six measured passes after warmup.'),indent=2)+'\n')
