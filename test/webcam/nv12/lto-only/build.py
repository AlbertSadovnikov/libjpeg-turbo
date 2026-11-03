#!/usr/bin/env python3
"""Fresh matched Clang ThinLTO codecs, without any profile generation/use."""
from pathlib import Path
import json,subprocess,shutil,hashlib,os
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-lto-only');work.mkdir(exist_ok=True)
google=Path('/tmp/mjpeg-google-bench');flags=['-O3','-DNDEBUG','-mtune=znver2','-flto=thin']
subprocess.run(['git','diff','--exit-code','HEAD','--','src','simd'],cwd=root,check=True)
env=os.environ.copy()
for key in ('CFLAGS','CXXFLAGS','LDFLAGS','LLVM_PROFILE_FILE'):env.pop(key,None)
def run(c,**kw):return subprocess.run(list(map(str,c)),check=True,env=env,**kw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
stock_source=work/'stock-source';current_source=work/'current-source'
if not stock_source.exists():
 stock_source.mkdir()
 for rel in subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0'):
  if not rel:continue
  src=root/rel
  if not src.is_file():continue
  dst=stock_source/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
if not current_source.exists():
 shutil.copytree(stock_source,current_source)
 shutil.rmtree(current_source/'src');shutil.copytree('/tmp/mjpeg-memset-call/source/src',current_source/'src')
 shutil.copy2('/tmp/mjpeg-entropy-span/span-source/src/jdhuff.c',current_source/'src/jdhuff.c')
# Give both entropy translation units the same CPU feature tier; no whole-codec
# AVX2 requirement. This is build configuration, not a production source edit.
for tree in (stock_source,current_source):
 cmake=tree/'CMakeLists.txt';text=cmake.read_text();extra='\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n'
 if extra not in text:cmake.write_text(text+extra)
records={}
for name,tree in [('stock',stock_source),('current',current_source)]:
 build=work/name
 configure=['cmake','-S',tree,'-B',build,'-DCMAKE_C_COMPILER=clang','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS=','-DCMAKE_C_FLAGS_RELEASE='+' '.join(flags),'-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=gold -flto=thin','-DCMAKE_AR=/usr/bin/llvm-ar-18','-DCMAKE_RANLIB=/usr/bin/llvm-ranlib-18','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DENABLE_SHARED=OFF','-DWITH_BENCHMARKS=OFF','-DWITH_TESTS=OFF','-DWITH_PROFILE=OFF','-DBUILD=20261024']
 for phase,cmd in [('configure',configure),('build',['cmake','--build',build,'--target','jpeg-static','turbojpeg-static','-j','6'])]:
  with (work/(name+'-'+phase+'.log')).open('w') as log:run(cmd,stdout=log,stderr=subprocess.STDOUT)
 commands=json.loads((build/'compile_commands.json').read_text())
 for command in commands:
  assert not any(x in command['command'] for x in ('-fprofile','-fauto-profile','-fcs-profile','-fcoverage','--coverage')),command
 records[name]={'source':str(tree),'build':str(build),'codec_flags':flags,'entropy_extra_flags':['-mbmi2'],'pgo':False,'thinlto':True,'compile_commands_sha256':sha(build/'compile_commands.json'),'archive_sha256':{str(build/lib):sha(build/lib) for lib in ('libjpeg.a','libturbojpeg.a')}}
 print(name,'codec rebuilt entirely with ThinLTO, no PGO.',flush=True)

# Recompile drivers/support as well. Shared GCC native C++ objects preserve the
# existing floating-point UV contract; Clang would change a few UV bytes.
# Both drivers use the same GCC O3 flags, no PGO; all codec C objects use the
# matching Clang/ThinLTO flags above. NASM kernels are naturally native code.
base=work/'stock';common=work/'common';common.mkdir(exist_ok=True)
cppflags=['-O3','-DNDEBUG','-std=c++17'];include=['-I'+str(base),'-I'+str(current_source/'src'),'-I'+str(root/'benchmarks'),'-I'+str(google/'_deps/googlebenchmark-src/include'),'-I'+str(root/'test/webcam/nv12/fused-chroma')]
prototype=(root/'benchmarks/nv12_bench.cc').read_text()
a='    Check(jpeg_start_decompress(&c),"JPEG start");';assert prototype.count(a)==1
prototype=prototype.replace(a,a+'\n    const bool fused=mjpeg_fusion_begin(&c,uv,uv_pitch,mjpeg_requested_mode);')
a='      pack(uv+y/2*uv_pitch,u.data(),v.data(),cp,uv_pitch,width/2,valid/2,subsamp==TJSAMP_422);';assert prototype.count(a)==1
prototype=prototype.replace(a,'      if(!fused) '+a.strip())
a='    Check(jpeg_finish_decompress(&c),"JPEG finish");';assert prototype.count(a)==1
prototype=prototype.replace(a,a+'\n    mjpeg_fusion_end();');(common/'nv12-fused.cc').write_text(prototype)
run(['g++',*cppflags,*include,'-DMJPEG_FUSED_PROTOTYPE="'+str(common/'nv12-fused.cc')+'"','-c',root/'test/webcam/nv12/fused-chroma/driver.cc','-o',common/'current-driver.o'])
run(['g++',*cppflags,*include,'-c',root/'test/webcam/nv12/stock-fast/driver.cc','-o',common/'stock-driver.o'])
run(['g++',*cppflags,'-mavx2','-mfma',*include,'-c','/tmp/mjpeg-coefficient-cost/registers.cc','-o',common/'fusion.o'])
run(['g++',*cppflags,*include,'-c','/tmp/mjpeg-pgo-lto/heldout-frame.cc','-o',common/'frame.o'])
for name,source in [('registers',root/'test/webcam/nv12/coefficient-cost/registers.asm'),('exact',root/'test/webcam/nv12/fused-chroma/exact.asm')]:
 run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(base)+'/', '-I'+str(root/'simd/nasm')+'/', '-I'+str(root/'simd/x86_64')+'/',source,'-o',common/(name+'.o')])
bench=google/'_deps/googlebenchmark-build/src/libbenchmark.a'
benchflags=(google/'_deps/googlebenchmark-build/src/CMakeFiles/benchmark.dir/flags.make').read_text();assert '-fprofile' not in benchflags
for name in ('stock','current'):
 build=work/name;objects=[common/(name+'-driver.o'),common/'frame.o']
 if name=='current':objects += [common/'fusion.o',common/'registers.o',common/'exact.o']
 run(['clang++','-fuse-ld=gold',*flags,*objects,bench,build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',build/'nv12'])
 records[name]['binary_sha256']=sha(build/'nv12')
(here/'build-summary.json').write_text(json.dumps({'cases':records,'pgo':False,'policy':'No profile generation, use, sampling or retained profiled codec members in comparisons. LTO is enabled and matched for codec C objects.','drivers':'Both freshly compiled GCC O3 native, no PGO; common wrapper retains exact existing UV rounding. Codec C objects are Clang ThinLTO in both builds.','native_support_sha256':{str(p):sha(p) for p in common.glob('*.o')},'benchmark_support_flags':benchflags,'benchmark_archive_sha256':sha(bench),'compiler':subprocess.check_output(['clang','--version'],text=True).splitlines()[0]},indent=2)+'\n')
print('Fresh stock/current binaries linked; no retained codec archives or PGO objects.',flush=True)
