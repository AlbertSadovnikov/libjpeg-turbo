#!/usr/bin/env python3
"""Build fused chroma kernels and an isolated raw-MCU scheduling hook."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil
import subprocess

here=Path(__file__).resolve().parent
root=here.parents[3]
work=Path('/tmp/mjpeg-fused-chroma');work.mkdir(exist_ok=True)
source=Path('/tmp/mjpeg-stb-src/threshold-pair10')
base=Path('/tmp/mjpeg-pgo-lto/gcc-base')
tree=work/'source'
if not tree.exists():shutil.copytree(source,tree)
def run(cmd):return subprocess.run(list(map(str,cmd)),check=True,capture_output=True)
def sha(data):return hashlib.sha256(data).hexdigest()

# Reuse the exact accurate IDCT arithmetic, clipping and rounding, while
# retaining averaged Cb rows in xmm12..15 across the Cr transform.
original=(root/'simd/x86_64/jidctint-avx2.asm').read_text()
start=original.index('    align       32\n    GLOBAL_FUNCTION(jsimd_idct_islow_avx2)')
prefix=original[:start].replace('jconst_idct_islow_avx2','mjpeg_chroma_exact_constants')
begin=original.index('    ; ---- Pass 1: process columns.',start)
end=original.index('    vpshufd     xmm1, xmm0, 0x4E',begin)
body=original[begin:end]
# The upstream single-block entry starts with clean YMM upper lanes. Our
# second block follows AVX2 arithmetic, so keep even its AC tests VEX-encoded.
body=body.replace('    movdqa ', '    vmovdqa ').replace('    movd ', '    vmovd ')
assembly=prefix+'''
; SysV x86-64: qCb, qCr, coefficientsCb, coefficientsCr, UV, pitch.
    align 32
    GLOBAL_FUNCTION(mjpeg_chroma_exact)
EXTN(mjpeg_chroma_exact):
    ENDBR64
    push rbp
    mov rbp, rsp
    push r12
    push r13
    push r14
    push r15
    mov r12, rsi
    mov r13, rcx
    mov r14, r8
    mov r15d, r9d
    mov r10, rdi
    mov r11, rdx
    call .block
    vmovdqa xmm12, xmm0
    vmovdqa xmm13, xmm2
    vmovdqa xmm14, xmm4
    vmovdqa xmm15, xmm6
    mov r10, r12
    mov r11, r13
    call .block
    vpunpcklbw xmm0, xmm12, xmm0
    vpunpcklbw xmm2, xmm13, xmm2
    vpunpcklbw xmm4, xmm14, xmm4
    vpunpcklbw xmm6, xmm15, xmm6
    vmovdqu [r14], xmm0
    add r14, r15
    vmovdqu [r14], xmm2
    add r14, r15
    vmovdqu [r14], xmm4
    add r14, r15
    vmovdqu [r14], xmm6
    vzeroupper
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    ret
.block:
'''+body+'''
    vpsrldq xmm1, xmm0, 8
    vpavgb xmm0, xmm0, xmm1
    vpsrldq xmm3, xmm2, 8
    vpavgb xmm2, xmm2, xmm3
    vpsrldq xmm5, xmm4, 8
    vpavgb xmm4, xmm4, xmm5
    vpsrldq xmm7, xmm6, 8
    vpavgb xmm6, xmm6, xmm7
    ret
SECTION .note.GNU-stack noalloc noexec nowrite progbits
'''
(here/'exact.asm').write_text(assembly)
run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(base)+'/',
     '-I'+str(root/'simd/nasm')+'/', '-I'+str(root/'simd/x86_64')+'/',here/'exact.asm','-o',work/'exact.o'])
run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma','-I'+str(base),
     '-I'+str(source/'src'),'-c',here/'fusion.cc','-o',work/'fusion.o'])

path=tree/'src/jdcoefct.c';text=(source/'src/jdcoefct.c').read_text()
include='#include "jsamplecomp.h"';assert text.count(include)==1
text=text.replace(include,include+'\n#if BITS_IN_JSAMPLE == 8\n#include "'+str(here/'fusion.h')+'"\n#endif',1)
marker='''      /* Only perform the IDCT on blocks that are contained within the desired
       * cropping region.'''
assert text.count(marker)==1
text=text.replace(marker,'''#if BITS_IN_JSAMPLE == 8
      /* Benchmark-only 4:2:2 raw-output fusion; ordinary scheduling is retained. */
      if (mjpeg_fusion_mcu(cinfo, coef->MCU_buffer, output_buf, MCU_col_num))
        continue;
#endif

'''+marker)
path.write_text(text)
(here/'codec-hook.patch').write_text(''.join(difflib.unified_diff((source/'src/jdcoefct.c').read_text().splitlines(True),text.splitlines(True),fromfile='a/src/jdcoefct.c',tofile='b/src/jdcoefct.c')))
isolation={}
for lib in ('libjpeg.a','libturbojpeg.a'):
    objdir=work/(lib+'-objects');objdir.mkdir(exist_ok=True)
    extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
    obj=objdir/'jdcoefct-8.c.o'
    run(['gcc','-O3','-DNDEBUG','-I'+str(base),*extra,'-c',tree/'src/wrapper/jdcoefct-8.c','-o',obj])
    shutil.copyfile(base/lib,work/lib);run(['ar','r',work/lib,obj]);run(['ranlib',work/lib])
    members=run(['ar','t',base/lib]).stdout.decode().splitlines()
    changed=[m for m in members if run(['ar','p',base/lib,m]).stdout!=run(['ar','p',work/lib,m]).stdout]
    assert changed==['jdcoefct-8.c.o'],changed
    isolation[lib]=dict(changed_members=changed,sha256=sha((work/lib).read_bytes()))
(here/'isolation.json').write_text(json.dumps(isolation,indent=2)+'\n')
print('Kernels and raw-MCU hook built.',flush=True)
