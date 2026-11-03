#!/usr/bin/env python3
from pathlib import Path
import sys,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
assert (here/'mixed-validation.json').exists()
B=WORK/'bin';inventory=json.loads((here/'inventory.json').read_text());valid=json.loads((here/'validation.json').read_text());assert len(valid)==sum(len(c['groups']) for c in inventory) and all(r['status']=='passed' for r in valid)
rows=[];brackets=[];cases=[]
for camera in inventory:
 for size in ('640x480','1280x720','1920x1080'):
  g=camera['groups'][size];mode=max(g['modes'],key=lambda m:float(m['requested']['fps']));frames=sorted(Path(mode['directory']).glob('frame_*.jpg'));assert len(frames)==12
  for comparison in ('clang-stock-vs-exact','gcc-stock-vs-deferred','gcc-exact-vs-deferred'):
   cases.append((camera,size,comparison,frames))
 # One same-binary noise control at 1080p per camera.
 g=camera['groups']['1920x1080'];mode=max(g['modes'],key=lambda m:float(m['requested']['fps']));cases.append((camera,'1920x1080','gcc-noise',sorted(Path(mode['directory']).glob('frame_*.jpg'))))
for trial in range(3):
 for camera,size,comparison,frames in (cases if trial%2==0 else cases[::-1]):
  cc='clang' if comparison.startswith('clang') else 'gcc';group=[]
  for role in ('control','candidate','control'):
   stock=role=='control' and 'stock-vs' in comparison
   variant='stock' if stock else ('exact' if cc=='clang' or (role=='control' and comparison=='gcc-exact-vs-deferred') or comparison=='gcc-noise' else 'deferred')
   binary=B/(cc+'-camera-'+variant)
   r=execute(binary,'measure',30,*frames) if stock else execute(binary,'fast',3,30,*frames)
   r.update(trial=trial,batch=camera['batch'],size=size,comparison=comparison,role=role);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append({'trial':trial,'batch':camera['batch'],'camera':camera['camera'],'size':size,'comparison':comparison,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1)})
  save(here/'results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary=[]
for camera,size,comparison,frames in cases:
 r=[x for x in brackets if x['batch']==camera['batch'] and x['size']==size and x['comparison']==comparison];a=statistics.mean(x['control_ms'] for x in r);b=statistics.mean(x['candidate_ms'] for x in r)
 summary.append({'camera':camera['camera'],'batch':camera['batch'],'size':size,'comparison':comparison,'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r})
save(here/'summary.json',summary)
