#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
PREFIX=""
TAG="tu"
W=Path('/tmp/mjpeg-restart-tu');B=WORK/'bin';UV=Path('/tmp/mjpeg-paired-fast-chroma')
fixtures=[Path(p) for p in json.loads((HERE.parent/'restart-fast/fixtures.json').read_text())];inventory=json.loads((HERE.parent/'multi-camera/inventory.json').read_text());expected=json.loads((HERE.parent/'multi-camera/validation.json').read_text());reports=[]
# Check actual cameras first, all output contracts and padded destinations.
for camera in inventory:
 for size,g in camera['groups'].items():
  ref=next(r for r in expected if r['batch']==camera['batch'] and r['size']==size)
  for cc in ('clang','gcc'):
   r=execute(B/(cc+'-'+TAG+'-fast'),'validate',*g['frames']);assert r==ref['cases'][cc]['exact'],(cc,camera['camera'],size)
  reports.append({'batch':camera['batch'],'size':size,'frames':len(g['frames']),'passed':True});save(here/(PREFIX+'camera-validation.json'),reports);print(camera['batch'],size,'NV12 and padding passed.',flush=True)
# Synthetic interval/fill cases: compare complete candidate/control reports.
extra=sorted(UV.glob('independent-q*.jpg'))
validation={}
for cc in ('clang','gcc'):
 validation[cc]={}
 for i,p in enumerate(fixtures):
  a=execute(B/(cc+'-'+TAG+'-control'),'validate',p);b=execute(B/(cc+'-'+TAG+'-fast'),'validate',p);assert a==b,(cc,p)
  validation[cc][p.name]=b
  if i%10==9:print(cc,i+1,'restart fixtures passed.',flush=True)
 files=[FRAMES[60],*extra,*FIXTURES,*fixtures[:5],FRAMES[60]]
 assert execute(B/(cc+'-'+TAG+'-control'),'validate',*files)==execute(B/(cc+'-'+TAG+'-fast'),'validate',*files)
 # Alternate cameras and tables in persistent decoders.
 for size in ('640x480','1280x720','1920x1080'):
  files=[Path(c['groups'][size]['frames'][i]) for i in range(3) for c in inventory]
  assert execute(B/(cc+'-'+TAG+'-control'),'validate',*files)==execute(B/(cc+'-'+TAG+'-fast'),'validate',*files)
 save(here/(PREFIX+'fixture-validation.json'),validation)
# Coefficients exercise noncontiguous virtual-array blocks, unlike raw strips.
obj=W/'coefficients.o';run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',HERE.parent/'entropy-span/coefficients.cc','-o',obj])
for cc in ('clang','gcc'):
 cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
 run([cxx,lto,'-fuse-ld=gold',obj,W/cc/'restart.o',W/cc/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',W/(cc+'-coefficients')])
files=[Path(p) for c in inventory for g in c['groups'].values() for p in g['frames']]+fixtures+FRAMES+FIXTURES
coefficients=[]
for i,p in enumerate(files):
 reference=run([B/'gcc-reference-coefficients',p]).stdout
 for cc in ('clang','gcc'):
  r=run([W/(cc+'-coefficients'),p]);assert not r.stderr;assert r.stdout==reference,(cc,p)
 coefficients.append({'file':str(p),'bytes':len(reference),'sha256':hashlib.sha256(reference).hexdigest()})
 if i%300==299:save(here/(PREFIX+'coefficients.json'),{'literal_equality':True,'files':coefficients});print(i+1,'literal coefficient streams passed.',flush=True)
save(here/(PREFIX+'coefficients.json'),{'literal_equality':True,'files':coefficients})
# Forced entropy/marker suspension, with full and suspended arrays compared.
source=(HERE.parent/'two-mcu/check.cc').read_text().replace('two-MCU check failed','restart check failed')
(W/'suspend.cc').write_text(source);run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',W/'suspend.cc','-o',W/'suspend.o'])
suspfiles=[FRAMES[60],*FIXTURES,*[p for p in fixtures if p.name in ('ordinary-rst2.jpg','ordinary-rst3.jpg','dense-rst2.jpg','dense-rst3.jpg','zeroac-rst3.jpg','zeroac-rst7.jpg','ordinary-fill-rst3.jpg','dense-fill-rst3.jpg','zeroac-fill-rst3.jpg','tail63-optimized-rst3.jpg')]]
suspfiles += [Path(c['groups'][size]['frames'][0]) for c in inventory for size in ('640x480','1280x720','1920x1080')]
result={}
for cc in ('clang','gcc'):
 cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto';base=BASE/cc/'current' if cc=='clang' else Path('/tmp/mjpeg-gcc-deferred-loads/gcc-deferred');result[cc]={}
 for name,archives in [('control',base),('fast',W/cc)]:
  binary=W/(cc+'-suspend-'+name)
  run([cxx,lto,'-fuse-ld=gold',W/'suspend.o',WORK/'uv-paired-wrapper.o',OLD_COMMON/'registers.o',OLD_COMMON/'exact.o',UV/'fast.o',*([W/cc/'restart.o'] if name=='fast' else []),archives/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',binary])
  result[cc][name]=execute(binary,*suspfiles)
 assert result[cc]['control']['hash']==result[cc]['fast']['hash']
 assert result[cc]['fast']['suspensions']>0
 print(cc,'suspended marker/entropy reads match literally.',flush=True);save(here/(PREFIX+'suspension.json'),result)
print('All restart-aware validation gates passed.',flush=True)
