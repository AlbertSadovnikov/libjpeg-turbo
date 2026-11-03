#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-partial-mcu');F=W/'fixtures';F.mkdir(exist_ok=True)
build=json.loads((here/'build-summary.json').read_text())['records'];B=WORK/'bin'
for cc,r in build.items():
 assert sha(r['binary'])==r['sha256']
 for p,d in r['archives'].items():assert sha(p)==d
run(['gcc','-O2','-flto','-fuse-ld=gold','-I'+str(BASE/'gcc/stock'),'-I'+str(TREE/'src'),here/'fixtures.c',BASE/'gcc/stock/libjpeg.a','-lm','-o',W/'fixtures-tool'])
fixtures=[]
for width in range(2,33,2):
 for height in range(2,17,2):
  p=F/f'{width}x{height}.jpg';run([W/'fixtures-tool',p,width,height,3 if width%4 else 0,0]);fixtures.append(p)
for width,height in [(8,4),(24,14),(40,22),(424,246),(480,270)]:
 p=F/f'progressive-{width}x{height}.jpg';run([W/'fixtures-tool',p,width,height,3,1]);fixtures.append(p)
save(here/'fixtures.json',{str(p):sha(p) for p in fixtures})
inv=json.loads((here.parent/'multi-camera/inventory.json').read_text());expected=json.loads((here.parent/'multi-camera/validation.json').read_text());camera=[]
for c in inv:
 for size,g in c['groups'].items():
  ref=next(r for r in expected if r['batch']==c['batch'] and r['size']==size)
  for cc in ('clang','gcc'):
   report=execute(build[cc]['binary'],'validate',*g['frames']);assert report==ref['cases'][cc]['exact'],(cc,size)
  camera.append(dict(batch=c['batch'],size=size,frames=len(g['frames']),passed=True));save(here/'camera-validation.json',camera)
  print(c['camera'].split()[0],size,'NV12/padding passed.',flush=True)
fixture_reports={}
prior=[Path(p) for p in json.loads((here.parent/'restart-fast/fixtures.json').read_text())]
for cc in ('clang','gcc'):
 fixture_reports[cc]={}
 for p in [*fixtures,*prior,*FIXTURES]:
  candidate=execute(build[cc]['binary'],'validate',p)
  reference=execute(B/(cc+'-camera-exact'),'validate',p)
  assert candidate==reference,(cc,p)
  fixture_reports[cc][str(p)]=candidate
 save(here/'fixture-validation.json',fixture_reports);print(cc,'all synthetic/restart/old fixtures passed.',flush=True)
print('All pixel/padding validation gates passed.',flush=True)
