#!/usr/bin/env python3
"""Generate explicit-layout and straight-line register-allocated paired kernels.

The allocator treats vector copies and the two stack scratch slots as aliases,
then allocates SSA values to 16 vector registers with last-use reuse. It never
changes arithmetic order, immediates, memory coefficient/quantizer loads, or
sample stores. This is specific to the branch-free SysV prototype.
"""
from pathlib import Path
import re,json,subprocess,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-coefficient-cost')
base=Path('/tmp/mjpeg-pgo-lto/gcc-base');fused=Path('/tmp/mjpeg-fused-chroma')
source=(root/'test/webcam/nv12/paired-idct/pair.asm').read_text()
reg=re.compile(r'\b([xy])mm(\d+)\b')
def allocate(s):
 start=s.index('    vmovdqu xmm0,');end=s.index('    vzeroupper',start)
 env={};ops=[];serial=0;removed=0
 def key(x):
  if reg.fullmatch(x):return 'v'+reg.fullmatch(x)[2]
  if '[wk(' in x:return 'w'+re.search(r'wk\((\d)\)',x)[1]
  return None
 def operand(x):
  if key(x) and key(x).startswith('w'):return ('y',env[key(x)])
  m=reg.fullmatch(x)
  if m:return (m[1],env[key(x)])
  assert not reg.search(x),x
  return x
 for line in s[start:end].splitlines():
  op,arg=line.strip().split(None,1)
  args=[a.strip() for a in re.split(r',\s*(?![^\[\]]*\])(?![^()]*\))',arg)]
  dest=key(args[0])
  if op=='vmovdqa' and dest and key(args[1]):
   env[dest]=env[key(args[1])];removed+=1;continue
  inputs=[operand(a) for a in args[1:]] if dest else [operand(a) for a in args]
  output=None
  if dest:
   assert dest.startswith('v');output=serial;serial+=1;env[dest]=output
  ops.append((op,args[0] if dest else None,output,inputs))
 last={}
 for i,(_,_,_,args) in enumerate(ops):
  for a in args:
   if isinstance(a,tuple):last[a[1]]=i
 active={};out=[];peak=0
 for i,(op,dest,value,args) in enumerate(ops):
  args_out=[('xmm' if a[0]=='x' else 'ymm')+str(active[a[1]]) if isinstance(a,tuple) else a for a in args]
  free={k for k in range(16)}-set(active.values())
  dying=[a[1] for a in args if isinstance(a,tuple) and last[a[1]]==i]
  if value is not None:
   reusable=[active[v] for v in dying]
   p=min(reusable) if reusable else min(free)
   out.append('    '+op+' '+('xmm' if dest.startswith('x') else 'ymm')+str(p)+', '+', '.join(args_out))
  else:out.append('    '+op+' '+', '.join(args_out))
  for v in set(dying):del active[v]
  if value is not None and value in last:active[value]=p
  peak=max(peak,len(active))
 assert peak<=16
 result=s[:start]+'\n'.join(out)+'\n'+s[end:]
 for line in ('    push rbp\n','    mov rbp, rsp\n','    and rsp, -32\n','    sub rsp, 64\n','    mov rsp, rbp\n','    pop rbp\n'):result=result.replace(line,'')
 assert '[wk(' not in result
 return result,dict(alias_instructions_removed=removed,max_live_vectors=peak,input_vector_instructions=len(s[start:end].splitlines()),output_vector_instructions=len(out))
layout=source
pat=re.compile(r'    vmovdqu xmm(\d+), XMMWORD \[XMMBLOCK\((\d), 0, rsi, SIZEOF_JCOEF\)\]\n    vinserti128 ymm\1, ymm\1, XMMWORD \[XMMBLOCK\(\2, 0, r9, SIZEOF_JCOEF\)\], 1')
layout,n=pat.subn(lambda m:f'    vmovdqu ymm{m[1]}, YMMWORD [rsi+{int(m[2])*32}]',layout);assert n==8
optimized,audit=allocate(source)
variants={'layout':layout,'registers':optimized}
info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto']
def run(c):subprocess.run(list(map(str,c)),check=True)
inc=['-I'+str(base),'-I'+str(fused/'source/src'),'-I'+str(root/'test/webcam/nv12/fused-chroma')]
cpp=Path('/tmp/mjpeg-paired-idct/paired.cc').read_text()
needle='mjpeg_idct_ifast_pair(c->comp_info[0].dct_table,*blocks[0],*blocks[1],output[0],col*16);'
assert cpp.count(needle)==1
convert='''alignas(32) JCOEF interleaved[128];
    for(int row=0;row<8;row++) {
      auto lo=_mm_loadu_si128((const __m128i *)(*blocks[0]+row*8));
      auto hi=_mm_loadu_si128((const __m128i *)(*blocks[1]+row*8));
      auto pair=_mm256_inserti128_si256(_mm256_castsi128_si256(lo),hi,1);
      _mm256_store_si256((__m256i *)(interleaved+row*16),pair);
    }
    mjpeg_idct_ifast_layout(c->comp_info[0].dct_table,interleaved,nullptr,output[0],col*16);'''
# The entire conversion is part of both isolated and full-path candidate costs.
for name,asm in variants.items():
 asm=asm.replace('mjpeg_idct_ifast_pair','mjpeg_idct_ifast_'+name).replace('mjpeg_pair_constants','mjpeg_'+name+'_constants')
 (here/(name+'.asm')).write_text(asm)
 run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(base)+'/', '-I'+str(root/'simd/nasm')+'/', '-I'+str(root/'simd/x86_64')+'/',here/(name+'.asm'),'-o',work/(name+'.o')])
 text=cpp.replace(needle,'{\n'+convert+'\n}') if name=='layout' else cpp.replace('mjpeg_idct_ifast_pair','mjpeg_idct_ifast_registers')
 if name=='layout':text=text.replace('void mjpeg_idct_ifast_pair(', 'void mjpeg_idct_ifast_layout(')
 (work/(name+'.cc')).write_text(text)
 (here/(name+'-wrapper.patch')).write_text(subprocess.run(['diff','-u','--label','paired.cc','--label',name+'.cc','/tmp/mjpeg-paired-idct/paired.cc',str(work/(name+'.cc'))],capture_output=True,text=True).stdout)
for compiler in ('g++','clang++'):
 for name in ('control','layout','registers'):
  src=Path('/tmp/mjpeg-paired-idct/paired.cc') if name=='control' else work/(name+'.cc')
  obj=work/(compiler+'-'+name+'.o');binary=work/(compiler+'-'+name)
  run([compiler,'-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*inc,'-c',src,'-o',obj])
  run(['clang++','-fuse-ld=gold',*info['flags'],fused/'driver.o',obj,'/tmp/mjpeg-paired-idct/pair.o',work/'layout.o',work/'registers.o',fused/'exact.o','/tmp/mjpeg-pgo-lto/heldout-frame.o','/tmp/mjpeg-google-bench/_deps/googlebenchmark-build/src/libbenchmark.a',fused/'pgo/libjpeg.a',fused/'pgo/libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
# Adapt the independent upstream SSE2 comparison to include both candidates.
check=(root/'test/webcam/nv12/paired-idct/check.cc').read_text()
check=check.replace('int main(){','''extern "C" void mjpeg_idct_ifast_layout(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);
extern "C" void mjpeg_idct_ifast_registers(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);
#include <immintrin.h>
static void convert(const JCOEF *a,const JCOEF *b,JCOEF *t){
  for(int r=0;r<8;r++){
    auto lo=_mm_loadu_si128((const __m128i *)(a+r*8));
    auto hi=_mm_loadu_si128((const __m128i *)(b+r*8));
    _mm256_store_si256((__m256i *)(t+r*16),_mm256_inserti128_si256(_mm256_castsi128_si256(lo),hi,1));
  }
}
static void validate_layout(const JCOEF *a,const JCOEF *b){
  alignas(32) JCOEF t[128];convert(a,b,t);
  for(int r=0;r<8;r++)for(int k=0;k<8;k++)if(t[r*16+k]!=a[r*8+k]||t[r*16+8+k]!=b[r*8+k])std::abort();
}
static void layout_call(const void *q,const JCOEF *a,const JCOEF *b,JSAMPARRAY rows,unsigned col){
  alignas(32) JCOEF t[128];
  convert(a,b,t);
  mjpeg_idct_ifast_layout(q,t,nullptr,rows,col);
}
int main(){''')
check=check.replace('  mjpeg_idct_ifast_pair(q,b,b+64,oo,3);','''  validate_layout(b,b+64);
  for(int kind=0;kind<3;kind++){
  std::memset(out,0xa5,sizeof(out));
  if(kind==0)mjpeg_idct_ifast_pair(q,b,b+64,oo,3);
  else if(kind==1)layout_call(q,b,b+64,oo,3);
  else mjpeg_idct_ifast_registers(q,b,b+64,oo,3);
  if(std::memcmp(ref,out,sizeof(out))){std::fprintf(stderr,"Kernel mismatch kind=%d\\n",kind);std::exit(1);}
  }''')
# In addition to the real frame, validate two quantizer tables across extremes.
check=check.replace('  check(b);','''  check(b);
  alignas(32) int16_t changed[64];for(int i=0;i<64;i++)changed[i]=int(next()%65536)-32768;
  auto old=q;q=changed;check(b);q=old;''')
check=check.replace('kind<2','kind<4').replace('if(kind)mjpeg_idct_ifast_pair(q,v.data(),v.data()+64,oo,3);else', 'if(kind==3)mjpeg_idct_ifast_registers(q,v.data(),v.data()+64,oo,3);else if(kind==2)layout_call(q,v.data(),v.data()+64,oo,3);else if(kind==1)mjpeg_idct_ifast_pair(q,v.data(),v.data()+64,oo,3);else')
(work/'check.cc').write_text(check)
run(['g++','-O3','-mavx2','-mfma',*inc,'-I'+str(root/'benchmarks'),work/'check.cc','/tmp/mjpeg-pgo-lto/heldout-frame.o','/tmp/mjpeg-paired-idct/pair.o',work/'layout.o',work/'registers.o',base/'libjpeg.a','-o',work/'check-variants'])
(here/'register-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
paths=[work/(cc+'-'+n) for cc in ('g++','clang++') for n in ('control','layout','registers')]+[work/'layout.o',work/'registers.o']
(here/'variant-artifacts.json').write_text(json.dumps({'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'codec_changes':[],'wrapper_flags':['-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma'],'link_flags':info['flags']},indent=2)+'\n')
print(audit)
