#!/usr/bin/env python3
"""Reuse an unused LUT byte for total coefficient advance; train each source."""
from pathlib import Path
import subprocess,json,hashlib,difflib,shutil
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-entropy-span');work.mkdir(exist_ok=True)
codec=Path('/tmp/mjpeg-memset-call/avx2');fused=Path('/tmp/mjpeg-fused-chroma');previous=Path('/tmp/mjpeg-coefficient-cost')
info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto'];base=Path(info['build'])
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
old=(fused/'source/src/jdhuff.c').read_text();new=old.replace('UINT8 bits, step1, step2, count;','UINT8 bits, step1, step2, span;')
assert new!=old
new=new.replace('e->count = 1;','e->span = (UINT8)step;').replace('e->count = 2;','e->span = (UINT8)(e->step1 + step);')
start=new.index('        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {');end=new.index('        HUFF_DECODE_FAST(s, l, actbl);',start)
new=new[:start]+'''        /* The former unused count byte holds step1+step2 (1..32).
         * Reuse next_k for the guard and last-store/next-iteration index. */
        const int next_k = k + e.span;
        if (e.bits && next_k <= DCTSIZE2) {
          const int first_k = k + e.step1 - 1;
          DROP_BITS(e.bits);
          k = next_k - 1;
          (*block)[jpeg_natural_order[first_k]] = e.value1;
          /* Single-symbol entries still repeat the same nonzero store. */
          (*block)[jpeg_natural_order[k]] = e.value2;
          continue;
        }
'''+new[end:]
(here/'span.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/jdhuff.c',tofile='b/src/jdhuff.c')))
common_flags=['-O3','-DNDEBUG','-mtune=znver2','-mbmi2']
def run(c,**kw):
 p=subprocess.run(list(map(str,c)),capture_output=True,text=True,**kw)
 if p.returncode:print(p.stderr,flush=True)
 p.check_returncode();return p

def libraries(name,tree,flags):
 build=work/name;build.mkdir(exist_ok=True)
 for lib in ('libjpeg.a','libturbojpeg.a'):
  objdir=build/(lib+'-objects');objdir.mkdir(exist_ok=True);obj=objdir/'jdhuff.c.o'
  extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
  r=run(['clang',*common_flags,*flags,'-I'+str(base),*extra,'-c',tree/'src/jdhuff.c','-o',obj])
  assert not r.stderr,r.stderr
  shutil.copyfile(codec/lib,build/lib);run(['llvm-ar-18','r',build/lib,obj]);run(['llvm-ranlib-18',build/lib])
 return build

def link(build,flags,binary,extra_objects=()):
 run(['clang++','-fuse-ld=gold','-O3','-DNDEBUG','-mtune=znver2','-flto=thin',*flags,fused/'driver.o',previous/'g++-registers.o',previous/'registers.o','/tmp/mjpeg-paired-idct/pair.o',fused/'exact.o','/tmp/mjpeg-pgo-lto/heldout-frame.o','/tmp/mjpeg-google-bench/_deps/googlebenchmark-build/src/libbenchmark.a',*extra_objects,build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])

records={}
for name,text in [('control',old),('span',new)]:
 tree=work/(name+'-source')
 if not tree.exists():shutil.copytree(fused/'source/src',tree/'src')
 (tree/'src/jdhuff.c').write_text(text)
 # Native, unprofiled debug objects are assembly diagnostics for BOTH compilers,
 # not the objects used by the independently profiled whole-path comparison.
 for cc in ('clang','gcc'):
  run([cc,*common_flags,'-g','-I'+str(base),'-c',tree/'src/jdhuff.c','-o',work/(cc+'-'+name+'-audit.o')])
 profile=work/(name+'-native-profile');profile.mkdir(exist_ok=True)
 assert not list(profile.glob('*.profraw')),'Use a new profile directory rather than mix training runs'
 genflags=['-fprofile-instr-generate='+str(profile/'raw-%m-%p.profraw')]
 generated=libraries(name+'-native-generate',tree,genflags);train=work/(name+'-train');link(generated,genflags,train)
 train_records=[]
 for mode in ('accurate','fast'):
  r=run(['taskset','-c','0',train,mode,2,1,*frames[:30]]);assert not r.stderr,r.stderr;train_records.append(json.loads(r.stdout))
 raw=sorted(profile.glob('*.profraw'));assert raw
 run(['llvm-profdata-18','merge','-o',profile/'merged.profdata',*raw])
 flags=['-fprofile-instr-use='+str(profile/'merged.profdata')]
 build=libraries(name,tree,flags);binary=build/'nv12';link(build,flags,binary)
 isolation={}
 for lib in ('libjpeg.a','libturbojpeg.a'):
  members=run(['llvm-ar-18','t',codec/lib]).stdout.splitlines();changed=[]
  for member in members:
   a=subprocess.check_output(['llvm-ar-18','p',str(codec/lib),member]);b=subprocess.check_output(['llvm-ar-18','p',str(build/lib),member])
   if a!=b:changed.append(member)
  assert changed==['jdhuff.c.o'],changed;isolation[lib]=changed
 records[name]={'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'flags':common_flags+flags,'profile_sha256':hashlib.sha256((profile/'merged.profdata').read_bytes()).hexdigest(),'training':train_records,'isolation':isolation,'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [binary,build/'libjpeg.a',build/'libturbojpeg.a']}}
 print(name,'independently trained on first 30 captures through selected pipeline.',flush=True)
shutil.copy2(work/'control/nv12',work/'identical')
(here/'build-summary.json').write_text(json.dumps({'cases':records,'training_frames':[str(p) for p in frames[:30]],'heldout_frames':[str(p) for p in frames[30:]],'unchanged_pipeline':'inline AVX2 zeroing, register-rewritten paired Y, existing reduced UV; other codec archive members including their PGO are byte-identical','entry_size_bytes':8,'lut_entries':1024,'new_metadata':'span=step1+step2 replaces unused count byte','old_profile_used_for_changed_entropy':False,'entropy_lto':False,'reason_entropy_is_native':'Fresh per-source ProfileSummary conflicts with retained codec ProfileSummary during ThinLTO imports. Both entropy objects use native code with independently matched PGO; all other archive members preserve their original ThinLTO/PGO bytes.'},indent=2)+'\n')
