#!/usr/bin/env python3
"""Standalone repository+capture reconstruction; no old /tmp codec/support needed.

This intentionally has no import of common.py: it must work without retained
prototype trees, generated wrappers, embedded-frame objects or benchmark libs.
"""
from pathlib import Path
import argparse,subprocess,shutil,json,hashlib,os
here=Path(__file__).resolve().parent;root=here.parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--compiler',choices=['clang','gcc'],default='clang');args=parser.parse_args()
cc=args.compiler;cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
w=Path('/tmp/mjpeg-next-round/standalone-'+cc);w.mkdir(parents=True,exist_ok=True);tree=w/'source';build=w/'build'
env=os.environ.copy()
for key in ('CFLAGS','CXXFLAGS','LDFLAGS','LLVM_PROFILE_FILE'):env.pop(key,None)
def run(c,**kw):return subprocess.run(list(map(str,c)),check=True,env=env,**kw)
if not tree.exists():
 tree.mkdir()
 for rel in subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0'):
  if rel and (root/rel).is_file():
   p=tree/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,p)
 run(['patch','-p1','-i',here.parent/'lto-only/codec.patch'],cwd=tree,stdout=subprocess.DEVNULL)
 p=tree/'src/jdcoefct.c';p.write_text(p.read_text().replace('/home/al/src/libjpeg-turbo/test/webcam/nv12/',str(here.parent)+'/'))
 p=tree/'CMakeLists.txt';p.write_text(p.read_text()+'\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n')
configure=['cmake','-S',tree,'-B',build,'-DCMAKE_C_COMPILER='+cc,'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS=','-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG '+lto,'-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=gold '+lto,'-DCMAKE_AR='+('/usr/bin/llvm-ar-18' if cc=='clang' else '/usr/bin/gcc-ar'),'-DCMAKE_RANLIB='+('/usr/bin/llvm-ranlib-18' if cc=='clang' else '/usr/bin/gcc-ranlib'),'-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DENABLE_SHARED=OFF','-DWITH_BENCHMARKS=OFF','-DWITH_TESTS=OFF','-DWITH_PROFILE=OFF','-DBUILD=20261024']
for phase,cmd in [('configure',configure),('build',['cmake','--build',build,'--target','jpeg-static','turbojpeg-static','-j','6'])]:
 with (w/(phase+'.log')).open('w') as log:run(cmd,stdout=log,stderr=subprocess.STDOUT)
# Remove benchmark registration and its unused main from the application
# prototype. Keep the same Strips/packing implementation and validation driver.
prototype=(root/'benchmarks/nv12_bench.cc').read_text().split('void Register()')[0]
prototype=prototype.replace('#include <benchmark/benchmark.h>','')+'\n} // namespace\n'
a='    Check(jpeg_start_decompress(&c),"JPEG start");';assert prototype.count(a)==1
prototype=prototype.replace(a,a+'\n    const bool fused=mjpeg_fusion_begin(&c,uv,uv_pitch,mjpeg_requested_mode);')
a='      pack(uv+y/2*uv_pitch,u.data(),v.data(),cp,uv_pitch,width/2,valid/2,subsamp==TJSAMP_422);';assert prototype.count(a)==1
prototype=prototype.replace(a,'      if(!fused) '+a.strip())
a='    Check(jpeg_finish_decompress(&c),"JPEG finish");';prototype=prototype.replace(a,a+'\n    mjpeg_fusion_end();');(w/'prototype.cc').write_text(prototype)
text=(here.parent/'fused-chroma/fusion.cc').read_text();needle='  idct(c,&c->comp_info[0],*blocks[0],output[0],col*16);\n  idct(c,&c->comp_info[0],*blocks[1],output[0],col*16+8);';assert text.count(needle)==1
text=text.replace('struct alignas(32) Context','extern "C" void mjpeg_idct_ifast_registers(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);\nstruct alignas(32) Context')
text=text.replace(needle,'  if(c->dct_method==JDCT_IFAST)mjpeg_idct_ifast_registers(c->comp_info[0].dct_table,*blocks[0],*blocks[1],output[0],col*16);\n  else {\n'+needle+'\n  }');(w/'fusion.cc').write_text(text)
frame=root/'test/webcam/20261023T230418Z/frame_000060.jpg';data=frame.read_bytes()
(w/'frame.cc').write_text('#include "embedded_frame.h"\nnamespace mjpeg_bench {const unsigned char kJpeg[]={'+','.join(map(str,data))+'};const std::size_t kJpegSize=sizeof(kJpeg);}\n')
include=['-I'+str(build),'-I'+str(tree/'src'),'-I'+str(root/'benchmarks'),'-I'+str(here.parent/'fused-chroma')]
for name,source,extra in [('driver',here.parent/'fused-chroma/driver.cc',['-DMJPEG_FUSED_PROTOTYPE="'+str(w/'prototype.cc')+'"']),('fusion',w/'fusion.cc',['-mavx2','-mfma']),('frame',w/'frame.cc',[])]:
 run(['g++','-O3','-DNDEBUG','-std=c++17',*include,*extra,'-c',source,'-o',w/(name+'.o')])
for name,source in [('registers',here.parent/'coefficient-cost/registers.asm'),('exact',here.parent/'fused-chroma/exact.asm')]:
 run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(build)+'/', '-I'+str(root/'simd/nasm')+'/', '-I'+str(root/'simd/x86_64')+'/',source,'-o',w/(name+'.o')])
run([cxx,'-O3',lto,'-fuse-ld=gold',*[w/(n+'.o') for n in ('driver','fusion','frame','registers','exact')],build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-o',w/'nv12'])
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
p=run(['taskset','-c','0',w/'nv12','validate',*frames],capture_output=True,text=True);assert not p.stderr,p.stderr
report=json.loads(p.stdout);assert report==json.loads((here.parent/'no-mtune/validation.json').read_text())[cc]['current']['capture']
(here/('standalone-'+cc+'.json')).write_text(json.dumps({'pgo':False,'mtune':False,'compiler':cc,'reconstruction':'Repository tracked source + saved codec patch + actual frame_000060 bytes; no retained archive, generated wrapper or Google Benchmark dependency.','validation':report,'binary':str(w/'nv12'),'sha256':hashlib.sha256((w/'nv12').read_bytes()).hexdigest(),'note':'Fresh compact application driver changes code layout; this is a validated reconstruction, not a timing result or reuse of old percentages.'},indent=2)+'\n')
print('Standalone',cc,'baseline rebuilt without old /tmp codec/support dependencies; all 120 outputs match.')
