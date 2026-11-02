#!/usr/bin/env python3
"""Lift upstream SSE2 IFAST arithmetic into independent AVX2 block lanes."""
from pathlib import Path
import re,subprocess,json,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-paired-idct');work.mkdir(exist_ok=True)
base=Path('/tmp/mjpeg-pgo-lto/gcc-base');fused=Path('/tmp/mjpeg-fused-chroma')
s=(root/'simd/x86_64/jidctfst-sse2.asm').read_text()
prefix=s[:s.index('    align       32\n    GLOBAL_FUNCTION(jsimd_idct_ifast_sse2)')]
prefix=prefix.replace('jconst_idct_ifast_sse2','mjpeg_pair_constants').replace('times 8  dw','times 16 dw').replace('times 16 db','times 32 db')
prefix=prefix.replace('%define wk(i)   r15 - (WK_NUM - (i)) * SIZEOF_XMMWORD','%define wk(i)   rsp + (i) * 32')
body=s[s.index('    ; -- Even part'):s.index('    pshufd      xmm5, xmm1, 0x4E')]
# No scalar early-out in this initial paired kernel: both lanes run full IDCT.
lines=[]
for line in body.splitlines():
 line=line.split(';')[0].strip()
 if not line:continue
 if line.startswith('prefetch') or line.startswith('mov         rdi') or line.startswith('mov         eax') or line=='.column_end:':continue
 op,operands=line.split(None,1);args=[a.strip() for a in re.split(r',\s*(?![^\[\]]*\])(?![^()]*\))',operands)]
 args=[a.replace('XMMWORD','YMMWORD').replace('xmm','ymm') for a in args]
 if 'XMMBLOCK' in operands:
  mem=args[1]
  if 'rsi' in mem:
   lines+=['    vmovdqu '+args[0].replace('ymm','xmm')+', '+mem.replace('YMMWORD','XMMWORD'), '    vinserti128 '+args[0]+', '+args[0]+', '+mem.replace('rsi','r9').replace('YMMWORD','XMMWORD')+', 1']
   continue
  lines+=['    vbroadcasti128 ymm8, '+mem.replace('YMMWORD','XMMWORD')]
  args[1]='ymm8'
 if op=='movdqa':out='vmovdqa '+', '.join(args)
 elif op.startswith('p'):out='v'+op+' '+', '.join([args[0],args[0],*args[1:]])
 else:raise ValueError(line)
 lines.append('    '+out)
asm=prefix+'''
    GLOBAL_FUNCTION(mjpeg_idct_ifast_pair)
EXTN(mjpeg_idct_ifast_pair):
    ENDBR64
    push rbp
    mov rbp, rsp
    and rsp, -32
    sub rsp, 64
    ; SysV: quant, block0, block1, rows, output column.
    mov r9, rdx
    mov rdx, rdi
    mov rdi, rcx
    mov eax, r8d
'''+ '\n'.join(lines)+'\n'
# Each lane contains two rows; join low/high block halves into 16-byte Y rows.
for reg,row in [(1,0),(3,2),(4,4),(7,6)]:
 asm+=f'''    vextracti128 xmm8, ymm{reg}, 1
    vpunpcklqdq xmm9, xmm{reg}, xmm8
    vpunpckhqdq xmm10, xmm{reg}, xmm8
    mov rdx, [rdi+{row}*8]
    vmovdqu [rdx+rax], xmm9
    mov rdx, [rdi+{row+1}*8]
    vmovdqu [rdx+rax], xmm10
'''
asm+='    vzeroupper\n    mov rsp, rbp\n    pop rbp\n    ret\nSECTION .note.GNU-stack noalloc noexec nowrite progbits\n'
(here/'pair.asm').write_text(asm)
def run(cmd):subprocess.run(list(map(str,cmd)),check=True)
run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(base)+'/', '-I'+str(root/'simd/nasm')+'/', '-I'+str(root/'simd/x86_64')+'/',here/'pair.asm','-o',work/'pair.o'])
src=(root/'test/webcam/nv12/fused-chroma/fusion.cc').read_text()
needle='  idct(c,&c->comp_info[0],*blocks[0],output[0],col*16);\n  idct(c,&c->comp_info[0],*blocks[1],output[0],col*16+8);'
assert src.count(needle)==1
src=src.replace('struct alignas(32) Context', 'extern "C" void mjpeg_idct_ifast_pair(const void *, const JCOEF *, const JCOEF *, JSAMPARRAY, unsigned);\nstruct alignas(32) Context')
for name in ('control','paired'):
 text=src if name=='control' else src.replace(needle,'''  if(c->dct_method==JDCT_IFAST) mjpeg_idct_ifast_pair(c->comp_info[0].dct_table,*blocks[0],*blocks[1],output[0],col*16);
  else {
'''+needle+'\n  }')
 (work/(name+'.cc')).write_text(text)
 run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma','-I'+str(base),'-I'+str(fused/'source/src'),'-I'+str(root/'test/webcam/nv12/fused-chroma'),'-c',work/(name+'.cc'),'-o',work/(name+'.o')])
 info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto']
 run(['clang++','-fuse-ld=gold',*info['flags'],fused/'driver.o',work/(name+'.o'),work/'pair.o',fused/'exact.o','/tmp/mjpeg-pgo-lto/heldout-frame.o','/tmp/mjpeg-google-bench/_deps/googlebenchmark-build/src/libbenchmark.a',fused/'pgo/libjpeg.a',fused/'pgo/libturbojpeg.a','-lm','-lpthread','-lrt','-o',work/name])
print('Built matched fused-path control and paired Y IDCT.')
run(['g++','-O3','-I'+str(base),'-I'+str(fused/'source/src'),'-I'+str(root/'benchmarks'),here/'check.cc',
     '/tmp/mjpeg-pgo-lto/heldout-frame.o',work/'pair.o',base/'libjpeg.a','-o',work/'check'])
artifacts={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [work/'control',work/'paired',work/'pair.o',fused/'pgo/libjpeg.a',fused/'pgo/libturbojpeg.a']}
(here/'artifact-summary.json').write_text(json.dumps(dict(sha256=artifacts,kernel='SysV x86-64 AVX2, paired 8-bit IFAST',wrapper_flags=['-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma'],codec_flags=info['flags']),indent=2)+'\n')
