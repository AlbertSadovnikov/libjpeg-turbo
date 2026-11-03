#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
UVWORK=Path('/tmp/mjpeg-paired-fast-chroma');UVWORK.mkdir(exist_ok=True)
asm=(HERE.parent/'coefficient-cost/registers.asm').read_text()
old='''    mov r9, rdx
    mov rdx, rdi
    mov rdi, rcx
    mov eax, r8d''';assert asm.count(old)==1
asm=asm.replace(old,'''    ; SysV: qCb, qCr, cb, cr, uv, pitch. Independent quantizers per lane.
    mov r10, rsi
    mov rsi, rdx
    mov rdx, rdi
    mov rdi, r8
    mov r11d, r9d
    mov r9, rcx''')
p=re.compile(r'    vbroadcasti128 (ymm\d+), XMMWORD \[XMMBLOCK\((\d), 0, rdx, SIZEOF_IFAST_MULT_TYPE\)\]')
asm,n=p.subn(lambda m:f'    vmovdqu {m[1].replace("ymm","xmm")}, XMMWORD [XMMBLOCK({m[2]}, 0, rdx, SIZEOF_IFAST_MULT_TYPE)]\n    vinserti128 {m[1]}, {m[1]}, XMMWORD [XMMBLOCK({m[2]}, 0, r10, SIZEOF_IFAST_MULT_TYPE)], 1',asm);assert n==8
start=asm.index('    vextracti128 xmm2, ymm1, 1');end=asm.index('    vzeroupper',start)
tail=[]
for reg in (1,3,4,0):
 tail += [f'    vpsrldq ymm2, ymm{reg}, 8',f'    vpavgb ymm{reg}, ymm{reg}, ymm2',f'    vextracti128 xmm2, ymm{reg}, 1',f'    vpunpcklbw xmm{reg}, xmm{reg}, xmm2',f'    vmovdqu [rdi], xmm{reg}','    add rdi, r11']
asm=asm[:start]+'\n'.join(tail)+'\n'+asm[end:]
asm=asm.replace('mjpeg_idct_ifast_registers','mjpeg_chroma_fast_pair').replace('mjpeg_registers_constants','mjpeg_fast_chroma_constants')
(here/'fast.asm').write_text(asm)
run(['nasm','-f','elf64','-DELF','-D__x86_64__','-D__CET__','-I'+str(BASE/'clang/current')+'/', '-I'+str(ROOT/'simd/nasm')+'/', '-I'+str(ROOT/'simd/x86_64')+'/',here/'fast.asm','-o',UVWORK/'fast.o'])
text=WRAPPER.replace('struct alignas(32) Context','extern "C" void mjpeg_chroma_fast_pair(const void *,const void *,const JCOEF *,const JCOEF *,unsigned char *,int);\nstruct alignas(32) Context')
text=text.replace('(mode==1&&c->dct_method!=JDCT_ISLOW))','(mode==1&&c->dct_method!=JDCT_ISLOW)||(mode==3&&c->dct_method!=JDCT_IFAST))')
needle='  bool changed=!ctx.prepared;';assert text.count(needle)==1
text=text.replace(needle,'  if(mode==3){ctx.c=c;ctx.uv=uv;ctx.pitch=pitch;ctx.mode=mode;return 1;}\n'+needle)
text=text.replace('  if(ctx.mode==1)mjpeg_chroma_exact','  if(ctx.mode==3)mjpeg_chroma_fast_pair(c->comp_info[1].dct_table,c->comp_info[2].dct_table,*blocks[2],*blocks[3],dst,ctx.pitch);\n  else if(ctx.mode==1)mjpeg_chroma_exact')
(UVWORK/'fusion.cc').write_text(text)
control=WRAPPER.replace('  ctx.c=nullptr;','  ctx.c=nullptr;\n  if(mode==3)return 0;',1)
objects={'uv-control':wrapper('uv-control-wrapper',control),'uv-paired':wrapper('uv-paired-wrapper',text)}
driver=(HERE.parent/'fused-chroma/driver.cc').read_text().replace('for(int mode:{1,2})','for(int mode:{1,2,3})').replace('if(mode==1)Check(a==b,','if(mode==1||mode==3)Check(a==b,')
(UVWORK/'driver.cc').write_text(driver)
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-I'+str(GOOGLE/'_deps/googlebenchmark-src/include'),'-DMJPEG_FUSED_PROTOTYPE="'+str(OLD_COMMON/'nv12-fused.cc')+'"','-c',UVWORK/'driver.cc','-o',UVWORK/'driver.o'])
for cc in ('clang','gcc'):
 for name,obj in objects.items():link(cc,name,obj,driver=UVWORK/'driver.o',extra=[UVWORK/'fast.o'])
# A direct checker is compiled by check.py, after this generated kernel exists.
save(here/'build-summary.json',{'pgo':False,'mtune':False,'kernel_sha256':sha(UVWORK/'fast.o'),'assembly_sha256':sha(here/'fast.asm'),'wrapper_sha256':sha(UVWORK/'fusion.cc'),'independent_quantizers':True,'binaries':{cc+'-'+n:sha(WORK/'bin'/(cc+'-'+n)) for cc in ('clang','gcc') for n in objects},'archives':'Verified current no-mtune codecs; unchanged for both wrappers.'})
print('Built separate stock-fast-exact UV mode, independent quantizers per AVX2 lane.')
