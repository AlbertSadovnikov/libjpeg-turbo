#!/usr/bin/env python3
from pathlib import Path
import sys,os
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-partial-mcu');B=WORK/'bin';UV=Path('/tmp/mjpeg-paired-fast-chroma');build=json.loads((here/'build-summary.json').read_text())['records']
s=(here.parent/'two-mcu/check.cc').read_text().replace('two-MCU check failed','partial-MCU state check failed')
s=s.replace('require(w%16==0&&h%8==0&&','require(w%2==0&&h%2==0&&')
s=s.replace('std::vector<unsigned char> u(w/2*8),v(u.size());','const int raw_y=(w+7)/8*8,cp=(w/2+7)/8*8;\n std::vector<unsigned char> temp(raw_y*8),u(cp*8),v(u.size());')
s=s.replace('u.data()+i*w/2;vr[i]=v.data()+i*w/2','u.data()+i*cp;vr[i]=v.data()+i*cp')
s=s.replace('yr[i]=r.y.data()+(row+i)*yp','yr[i]=temp.data()+i*raw_y')
s=s.replace('if(!fused)for(int y=0;y<4;y++)','for(int y=0;y<std::min(8,h-row);y++)std::memcpy(r.y.data()+(row+y)*yp,yr[y],w);\n  if(!fused)for(int y=0;y<std::min(8,h-row)/2;y++)')
(W/'suspend.cc').write_text(s)
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',W/'suspend.cc','-o',W/'suspend.o'])
fixtures=[Path(p) for p in json.loads((here/'fixtures.json').read_text()) if 'progressive' not in p]
inv=json.loads((here.parent/'multi-camera/inventory.json').read_text());logi=next(c for c in inv if 'Logitech' in c['camera']);affected=('320x180','424x240','480x270','960x540')
files=fixtures+[Path(logi['groups'][size]['frames'][0]) for size in affected]
reports={}
for cc in ('clang','gcc'):
 cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto';archives=Path(next(iter(build[cc]['archives']))).parent
 reports[cc]={}
 for name,wrapper in [('control',WORK/'uv-paired-wrapper.o'),('edge',W/'fusion.o')]:
  binary=W/(cc+'-suspend-'+name)
  run([cxx,lto,'-fuse-ld=gold',W/'suspend.o',wrapper,OLD_COMMON/'registers.o',OLD_COMMON/'exact.o',UV/'fast.o',archives/'libjpeg.a','-lm','-o',binary])
  p=run(['taskset','-c','0',binary,*files],text=True);assert not p.stderr;reports[cc][name]=json.loads(p.stdout)
 assert reports[cc]['control']==reports[cc]['edge'];save(here/'suspension.json',reports);print(cc,'suspension, pixel and padding checks passed.',flush=True)
# Separate diagnostic object: counters never enter timed candidates.
s=(W/'fusion.cc').read_text();s=s.replace('static thread_local Context ctx;','static unsigned long long edges=0,interiors=0;\n__attribute__((destructor)) static void report_edges(){std::fprintf(stderr,"{\\"edges\\":%llu,\\"interiors\\":%llu}\\n",edges,interiors);}\nstatic thread_local Context ctx;')
s=s.replace('    const unsigned x=col*16, y=c->input_iMCU_row*8;','    edges++;\n    const unsigned x=col*16, y=c->input_iMCU_row*8;')
s=s.replace('  auto idct=c->idct->inverse_DCT[0];','  interiors++;\n  auto idct=c->idct->inverse_DCT[0];')
(W/'diagnostic.cc').write_text(s);run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*INCLUDES,'-c',W/'diagnostic.cc','-o',W/'diagnostic.o'])
diagnostics={}
for cc in ('clang','gcc'):
 archives=Path(next(iter(build[cc]['archives']))).parent
 binary=link(cc,'partial-diagnostic',W/'diagnostic.o',archives=archives,driver=Path('/tmp/mjpeg-multi-camera/exact-driver.o'),extra=[UV/'fast.o']);diagnostics[cc]={}
 for size in (*affected,'640x480'):
  width,height=map(int,size.split('x'));file=logi['groups'][size]['frames'][0]
  r=run([binary,'fast',3,1,file],text=True);counters=json.loads(r.stderr)
  mcus=(width+15)//16*((height+7)//8);full=(width//16)*(height//8)
  assert counters==dict(edges=2*(mcus-full),interiors=2*full),(size,counters)
  diagnostics[cc][size]=counters
save(here/'diagnostics.json',diagnostics)
print('Edge and interior MCU selection counts verified.',flush=True)
