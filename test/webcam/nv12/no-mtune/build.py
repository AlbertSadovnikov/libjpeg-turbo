#!/usr/bin/env python3
"""Matched stock/current codecs: Clang and GCC, LTO, no PGO or -mtune."""
from pathlib import Path
import subprocess,json,hashlib,os,shlex
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-no-mtune');work.mkdir(exist_ok=True)
previous=Path('/tmp/mjpeg-lto-only');common=previous/'common';google=Path('/tmp/mjpeg-google-bench')
prior=json.loads((here.parent/'lto-only/build-summary.json').read_text());assert prior['pgo'] is False
for filename,wanted in prior['native_support_sha256'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==wanted,filename
# The shared native GCC C++ support was built with O3, no -mtune/no PGO.
# Reusing it keeps UV rounding and the application-side code identical.
env=os.environ.copy()
for key in ('CFLAGS','CXXFLAGS','LDFLAGS','LLVM_PROFILE_FILE'):env.pop(key,None)
def run(c,**kw):return subprocess.run(list(map(str,c)),check=True,env=env,**kw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run(['git','diff','--exit-code','--','src','simd'],check=True,cwd=root)
records={}
for compiler,cxx,ar,ranlib,lto in [('clang','clang++','/usr/bin/llvm-ar-18','/usr/bin/llvm-ranlib-18','-flto=thin'),('gcc','g++','/usr/bin/gcc-ar','/usr/bin/gcc-ranlib','-flto')]:
 flags=['-O3','-DNDEBUG',lto];records[compiler]={}
 for name in ('stock','current'):
  source=previous/(name+'-source');assert source.exists()
  build=work/compiler/name
  config=['cmake','-S',source,'-B',build,'-DCMAKE_C_COMPILER='+compiler,'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS=','-DCMAKE_C_FLAGS_RELEASE='+' '.join(flags),'-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=gold '+lto,'-DCMAKE_AR='+ar,'-DCMAKE_RANLIB='+ranlib,'-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DENABLE_SHARED=OFF','-DWITH_BENCHMARKS=OFF','-DWITH_TESTS=OFF','-DWITH_PROFILE=OFF','-DBUILD=20261024']
  for phase,cmd in [('configure',config),('build',['cmake','--build',build,'--target','jpeg-static','turbojpeg-static','-j','6'])]:
   with (work/(compiler+'-'+name+'-'+phase+'.log')).open('w') as log:run(cmd,stdout=log,stderr=subprocess.STDOUT)
  commands=json.loads((build/'compile_commands.json').read_text())
  for command in commands:
   args=shlex.split(command['command'])
   assert not any(arg.startswith(x) for arg in args for x in ('-mtune','-march','-mcpu','-fprofile','-fauto-profile','-fcs-profile','--coverage','-fcoverage')),command
   if command['file'].endswith('.c'):assert lto in args,command
  objects=[common/(name+'-driver.o'),common/'frame.o']
  if name=='current':objects += [common/'fusion.o',common/'registers.o',common/'exact.o']
  bench=google/'_deps/googlebenchmark-build/src/libbenchmark.a'
  run([cxx,'-fuse-ld=gold',*flags,*objects,bench,build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',build/'nv12'])
  records[compiler][name]={'source':str(source),'build':str(build),'codec_flags':flags,'entropy_extra_flags':['-mbmi2'],'pgo':False,'explicit_mtune':False,'lto':lto,'compile_commands_sha256':sha(build/'compile_commands.json'),'sha256':{str(p):sha(p) for p in [build/'nv12',build/'libjpeg.a',build/'libturbojpeg.a']}}
  print(compiler,name,'built and linked: LTO, no PGO, no explicit -mtune/-march/-mcpu.',flush=True)
(here/'build-summary.json').write_text(json.dumps({'cases':records,'pgo':False,'explicit_mtune':False,'compilers':{cc:subprocess.check_output([cc,'--version'],text=True).splitlines()[0] for cc in ('clang','gcc')},'native_support_sha256':prior['native_support_sha256'],'native_support_policy':'Shared unchanged GCC O3 native drivers/fusion, no PGO and no -mtune; verified hashes. Preserves exact established reduced-UV rounding.','benchmark_archive_sha256':prior['benchmark_archive_sha256'],'source_snapshots':'Same isolated unmodified stock/prototype current snapshots as lto-only; only compiler and removal of codec -mtune differ. Existing BMI2-on-entropy tier is retained for both stock/current.'},indent=2)+'\n')
