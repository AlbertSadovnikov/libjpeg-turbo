#!/usr/bin/env python3
"""Expanded Y multiplier cache; same selected inline-clear codec archives."""
from pathlib import Path
import subprocess,json,hashlib,re,difflib,shutil
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-quantizer-cache');work.mkdir(exist_ok=True)
fused=Path('/tmp/mjpeg-fused-chroma');previous=Path('/tmp/mjpeg-coefficient-cost');codec=Path('/tmp/mjpeg-memset-call/avx2');base=Path('/tmp/mjpeg-pgo-lto/gcc-base')
info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto']
def run(c):subprocess.run(list(map(str,c)),check=True)
asm=(here.parent/'coefficient-cost/registers.asm').read_text()
pattern=re.compile(r'    vbroadcasti128 (ymm\d+), XMMWORD \[XMMBLOCK\((\d), 0, rdx, SIZEOF_IFAST_MULT_TYPE\)\]\n    vpmullw (ymm\d+), (ymm\d+), \1')
asm,n=pattern.subn(lambda m:f'    vpmullw {m[3]}, {m[4]}, YMMWORD [rdx+{int(m[2])*32}]',asm);assert n==8
asm=asm.replace('mjpeg_idct_ifast_registers','mjpeg_idct_ifast_cached').replace('mjpeg_registers_constants','mjpeg_cached_constants')
(here/'cached.asm').write_text(asm)
run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(base)+'/', '-I'+str(root/'simd/nasm')+'/', '-I'+str(root/'simd/x86_64')+'/',here/'cached.asm','-o',work/'cached-kernel.o'])
control=(previous/'registers.cc').read_text()
candidate=control.replace('#include <cstring>','#include <cstring>\n#include "cache.h"')
candidate=candidate.replace('struct alignas(32) Context {','extern "C" void mjpeg_idct_ifast_cached(const void *, const JCOEF *, const JCOEF *, JSAMPARRAY, unsigned);\nstruct alignas(32) Context {\n  YQuantCache ycache;')
needle='  bool changed=!ctx.prepared;';assert candidate.count(needle)==1
candidate=candidate.replace(needle,'''  if(c->dct_method==JDCT_IFAST) {
    if(!c->comp_info[0].dct_table)return 0;
    ctx.ycache.Update(c->comp_info[0].dct_table);
  }
'''+needle)
candidate=candidate.replace('mjpeg_idct_ifast_registers(c->comp_info[0].dct_table,','mjpeg_idct_ifast_cached(ctx.ycache.expanded,')
(here/'wrapper.patch').write_text(''.join(difflib.unified_diff(control.splitlines(True),candidate.splitlines(True),fromfile='registers.cc',tofile='cached.cc')))
incs=['-I'+str(base),'-I'+str(fused/'source/src'),'-I'+str(root/'test/webcam/nv12/fused-chroma'),'-I'+str(here)]
artifacts=[]
for name,text in [('control',control),('cached',candidate)]:
 (work/(name+'.cc')).write_text(text)
 run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*incs,'-c',work/(name+'.cc'),'-o',work/(name+'.o')])
 run(['clang++','-fuse-ld=gold',*info['flags'],fused/'driver.o',work/(name+'.o'),previous/'registers.o',work/'cached-kernel.o','/tmp/mjpeg-paired-idct/pair.o',fused/'exact.o','/tmp/mjpeg-pgo-lto/heldout-frame.o','/tmp/mjpeg-google-bench/_deps/googlebenchmark-build/src/libbenchmark.a',codec/'libjpeg.a',codec/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',work/name]);artifacts+=[work/name,work/(name+'.o')]
# A second name of the exact control executable supplies a noise control.
shutil.copy2(work/'control',work/'identical')
check=(root/'test/webcam/nv12/paired-idct/check.cc').read_text()
check=check.replace('int main(){','''#include "cache.h"
extern "C" void mjpeg_idct_ifast_cached(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);
extern "C" void mjpeg_idct_ifast_registers(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);
int main(){
 YQuantCache cache; unsigned updates=0;''')
check=check.replace('  mjpeg_idct_ifast_pair(q,b,b+64,oo,3);','''  updates+=cache.Update(q);
  if(cache.Update(q)){std::fprintf(stderr,"Unchanged table rebuilt\\n");std::exit(1);}
  mjpeg_idct_ifast_cached(cache.expanded,b,b+64,oo,3);''')
check=check.replace('  check(b);','''  check(b);
  alignas(32) int16_t changed[64];for(int i=0;i<64;i++)changed[i]=int(next()%65536)-32768;
  auto old=q;q=changed;check(b);q=old;
  // Reuse the SAME pointer while mutating one multiplier.
  changed[t%64]^=1;q=changed;check(b);q=old;''')
check=check.replace(' std::printf("{\\"capture_pairs', ' cache.Update(q);\n std::printf("{\\"capture_pairs')
check=check.replace('kind<2','kind<3').replace('if(kind)mjpeg_idct_ifast_pair(q,v.data(),v.data()+64,oo,3);else','if(kind==2)mjpeg_idct_ifast_cached(cache.expanded,v.data(),v.data()+64,oo,3);else if(kind==1)mjpeg_idct_ifast_registers(q,v.data(),v.data()+64,oo,3);else')
(work/'check.cc').write_text(check)
run(['g++','-O3','-mavx2','-mfma',*incs,'-I'+str(root/'benchmarks'),work/'check.cc','/tmp/mjpeg-pgo-lto/heldout-frame.o',previous/'registers.o',work/'cached-kernel.o',base/'libjpeg.a','-o',work/'check'])
artifacts += [work/'cached-kernel.o',work/'check',codec/'libjpeg.a',codec/'libturbojpeg.a']
(here/'build-summary.json').write_text(json.dumps({'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},'wrapper_flags':['-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma'],'link_flags':info['flags'],'codec_changes':[],'removed_quantizer_broadcasts_per_y_pair':8,'expanded_bytes':256,'snapshot_bytes':128,'cache_total_bytes':416},indent=2)+'\n')
print('Built multiplier-cache control/candidate on selected inline-clear baseline.')
