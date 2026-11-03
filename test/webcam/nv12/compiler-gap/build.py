#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-compiler-gap');W.mkdir(exist_ok=True)
UV=Path('/tmp/mjpeg-paired-fast-chroma');obj=WORK/'uv-paired-wrapper.o'
record={}
for compiler in ('clang','gcc'):
 folder=W/('entropy-'+compiler);folder.mkdir(exist_ok=True)
 target=folder/'jdhuff.c.o'
 flags=['-O3','-DNDEBUG','-mbmi2','-fno-lto','-I'+str(BASE/'clang/current')]
 run([compiler,*flags,'-c',TREE/'src/jdhuff.c','-o',target]);record[compiler]={'flags':flags,'object_sha256':sha(target)}
for host in ('clang','gcc'):
 for entropy in ('clang','gcc'):
  folder=W/(host+'-entropy-'+entropy);folder.mkdir(exist_ok=True)
  for lib in ('libjpeg.a','libturbojpeg.a'):
   shutil.copy2(BASE/host/'current'/lib,folder/lib)
   ar='llvm-ar-18' if host=='clang' else 'gcc-ar';ranlib='llvm-ranlib-18' if host=='clang' else 'gcc-ranlib'
   run([ar,'r',folder/lib,W/('entropy-'+entropy)/'jdhuff.c.o']);run([ranlib,folder/lib])
   changed=[m for m in run([ar,'t',folder/lib],text=True).stdout.splitlines() if run([ar,'p',folder/lib,m]).stdout!=run([ar,'p',BASE/host/'current'/lib,m]).stdout];assert changed==['jdhuff.c.o']
  b=link(host,'gap-'+entropy,obj,archives=folder,driver=UV/'driver.o',extra=[UV/'fast.o'])
  record[host+'-host-'+entropy]={'binary':str(b),'sha256':sha(b),'archives':{str(folder/lib):sha(folder/lib) for lib in ('libjpeg.a','libturbojpeg.a')}}
save(here/'build-summary.json',{'pgo':False,'explicit_tune':False,'source_sha256':sha(TREE/'src/jdhuff.c'),'records':record,'method':'Identical native (non-LTO) entropy objects crossed into both LTO hosts; only jdhuff.c.o changed. Native Y/UV/driver identical.'})
print('Built crossed entropy-object matrix.',flush=True)
