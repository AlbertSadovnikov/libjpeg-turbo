#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-gcc-deferred-loads');W.mkdir(exist_ok=True);UV=Path('/tmp/mjpeg-paired-fast-chroma')
original=(TREE/'src/jdhuff.c').read_text()
a=original.index('        multi_entry e;');b=original.index('        HUFF_DECODE_FAST(s, l, actbl);',a)
chunk=original[a:b];replacement=chunk.replace('multi_entry e;','const multi_entry *e;').replace('e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];','e = &fused[PEEK_BITS(MJPEG_FUSED_BITS)];\n        const int entry_bits = e->bits;').replace('e.span','e->span').replace('e.bits','e->bits').replace('e.step1','e->step1').replace('e.value1','e->value1').replace('e.value2','e->value2').replace('if (e->bits &&','if (entry_bits &&').replace('DROP_BITS(e->bits);','DROP_BITS(entry_bits);')
assert replacement!=chunk
rewrite=original[:a]+replacement+original[b:];patch(here/'deferred.patch',original,rewrite)
records={}
for cc,name,text,flags in [('gcc','control',original,[]),('gcc','no-hoist',original,['-fno-hoist-adjacent-loads']),('gcc','deferred',rewrite,[]),('clang','deferred',rewrite,[])]:
 folder=W/(cc+'-'+name);folder.mkdir(exist_ok=True);tree=folder/'source';shutil.copytree(TREE/'src',tree/'src',dirs_exist_ok=True);source=tree/'src/jdhuff.c';source.write_text(text)
 lto='-flto=thin' if cc=='clang' else '-flto';ar='llvm-ar-18' if cc=='clang' else 'gcc-ar';ranlib='llvm-ranlib-18' if cc=='clang' else 'gcc-ranlib'
 opts=['-O3','-DNDEBUG',lto,'-mbmi2',*flags,'-I'+str(BASE/cc/'current')]
 for lib in ('libjpeg.a','libturbojpeg.a'):
  d=folder/(lib+'-objects');d.mkdir(exist_ok=True);obj=d/'jdhuff.c.o'
  extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
  run([cc,*opts,*extra,'-c',source,'-o',obj]);shutil.copy2(BASE/cc/'current'/lib,folder/lib);run([ar,'r',folder/lib,obj]);run([ranlib,folder/lib])
  changed=[m for m in run([ar,'t',folder/lib],text=True).stdout.splitlines() if run([ar,'p',folder/lib,m]).stdout!=run([ar,'p',BASE/cc/'current'/lib,m]).stdout]
  assert set(changed)<=set(['jdhuff.c.o']),changed
 b=link(cc,'loads-'+name,WORK/'uv-paired-wrapper.o',archives=folder,driver=UV/'driver.o',extra=[UV/'fast.o'])
 records[cc+'-'+name]={'binary':str(b),'sha256':sha(b),'flags':opts,'source_sha256':sha(source),'archives':{str(folder/lib):sha(folder/lib) for lib in ('libjpeg.a','libturbojpeg.a')}}
save(here/'build-summary.json',{'pgo':False,'explicit_tune':False,'changed_member':'jdhuff.c.o','records':records})
print('Built separate no-hoist flag and pointer/deferred-field source variants, retaining LTO.',flush=True)
