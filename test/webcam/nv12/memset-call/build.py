#!/usr/bin/env python3
"""Change only the isolated coefficient controller; preserve other codec PGO."""
from pathlib import Path
import hashlib,json,subprocess,shutil,difflib,sys
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-memset-call');work.mkdir(exist_ok=True)
fused=Path('/tmp/mjpeg-fused-chroma');previous=Path('/tmp/mjpeg-coefficient-cost')
info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto'];base=Path(info['build'])
source=work/'source'
if not source.exists():shutil.copytree(fused/'source/src',source/'src')
old=(fused/'source/src/jdcoefct.c').read_text()
needle='''      jzero_far((void *)coef->MCU_buffer[0],
                (size_t)(cinfo->blocks_in_MCU * sizeof(JBLOCK)));'''
assert old.count(needle)==1
new=old.replace('#include "jsamplecomp.h"','#include "jsamplecomp.h"\n#include "'+str(here/'clear.h')+'"')
new=new.replace(needle,needle.replace('jzero_far','mjpeg_clear_experiment'))
(source/'src/jdcoefct.c').write_text(new)
(here/'controller.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='fused-source/src/jdcoefct.c',tofile='memset-source/src/jdcoefct.c')))
def run(cmd):subprocess.run(list(map(str,cmd)),check=True)
variants={'control':0,'direct-libc':1,'inline':2,'avx2':3};records={}
for name,kind in variants.items():
 build=work/name;build.mkdir(exist_ok=True)
 isolation={}
 for lib in ('libjpeg.a','libturbojpeg.a'):
  objdir=build/(lib+'-objects');objdir.mkdir(exist_ok=True);obj=objdir/'jdcoefct-8.c.o'
  extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
  # The original fusion controller was already built without its obsolete PGO
  # profile. Keep that policy and the exact same O3/ThinLTO flags for all cases.
  run(['clang','-O3','-DNDEBUG','-mtune=znver2','-flto=thin','-I'+str(base),*extra,'-DMJPEG_CLEAR_VARIANT='+str(kind),'-c',source/'src/wrapper/jdcoefct-8.c','-o',obj])
  shutil.copyfile(fused/'pgo'/lib,build/lib);run(['llvm-ar-18','r',build/lib,obj]);run(['llvm-ranlib-18',build/lib])
  members=subprocess.check_output(['llvm-ar-18','t',str(fused/'pgo'/lib)],text=True).splitlines()
  changed=[]
  for member in members:
   a=subprocess.check_output(['llvm-ar-18','p',str(fused/'pgo'/lib),member]);b=subprocess.check_output(['llvm-ar-18','p',str(build/lib),member])
   if a!=b:changed.append(member)
  assert changed==['jdcoefct-8.c.o'],changed
  isolation[lib]=changed
 binary=build/'nv12'
 run(['clang++','-fuse-ld=gold',*info['flags'],fused/'driver.o',previous/'g++-registers.o',previous/'registers.o','/tmp/mjpeg-paired-idct/pair.o',fused/'exact.o','/tmp/mjpeg-pgo-lto/heldout-frame.o','/tmp/mjpeg-google-bench/_deps/googlebenchmark-build/src/libbenchmark.a',build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
 records[name]={'isolation':isolation,'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [binary,build/'libjpeg.a',build/'libturbojpeg.a']}}
(here/'build-summary.json').write_text(json.dumps({'variants':records,'controller_flags':['-O3','-DNDEBUG','-mtune=znver2','-flto=thin'],'controller_pgo':False,'other_codec_members':'unchanged, including retained PGO','best_y_kernel':'coefficient-cost/registers.asm','link_flags':info['flags']},indent=2)+'\n')
print('Built matched clearing variants on the register-only paired Y baseline.')
run([sys.executable,here/'select.py'])
