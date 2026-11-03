#!/usr/bin/env python3
from common import *
base=(TREE/'src/jdhuff.c').read_text();diag=base.replace('#include "jstdhuff.c"','#include "jstdhuff.c"\nextern unsigned long long mjpeg_diag[11];\n#define JHIT(i) (++mjpeg_diag[i])')
diag=diag.replace('decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(0);')
diag=diag.replace('decode_mcu_slow(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_slow(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(8);')
diag=diag.replace('if (!decode_mcu_fast(cinfo, MCU_data)) goto use_slow;','if (!decode_mcu_fast(cinfo, MCU_data)) { JHIT(7); goto use_slow; }')
diag=diag.replace('    bit_buf_type word, inverted; \\', '    JHIT(4); \\\n    bit_buf_type word, inverted; \\')
diag=diag.replace('      get_buffer = (get_buffer << 48)', '      JHIT(5); \\\n      get_buffer = (get_buffer << 48)')
diag=diag.replace('      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\', '      JHIT(6); \\\n      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\',1)
diag=diag.replace('    if (c1 != 0) { \\', '    if (c1 == 0) JHIT(9); \\\n    if (c1 != 0) { \\\n      JHIT(10); \\')
diag=diag.replace('if (e.bits && next_k <= DCTSIZE2) {','if (e.bits && next_k <= DCTSIZE2) {\n          JHIT(e.step2 ? 2 : 1);')
start=diag.index('const int next_k = k + e.span;');i=diag.index('        HUFF_DECODE_FAST(s, l, actbl);',start);diag=diag[:i]+'        JHIT(3);\n'+diag[i:]
patch(HERE/'diagnostic.patch',base,diag)
folder=WORK/'span-off-source';shutil.copytree(TREE/'src',folder/'src',dirs_exist_ok=True)
run(['patch','-R','-p1','-i',HERE.parent/'entropy-span/span.patch'],cwd=folder)
spanoff=(folder/'src/jdhuff.c').read_text();unpaired=wrapper('unpaired-wrapper',(HERE.parent/'fused-chroma/fusion.cc').read_text())
probeobj=WORK/'probe.o';run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',HERE/'probe.cc','-o',probeobj])
probeFusion=wrapper('probe-fusion',extra=['-Dmjpeg_fusion_mcu=mjpeg_unused_fusion_mcu'])
for cc in ('clang','gcc'):
 diagnostic=codec_variant(cc,'diagnostic',diag)
 off=codec_variant(cc,'span-off',spanoff)
 link(cc,'span-off',WORK/'control-wrapper.o',off)
 link(cc,'unpaired',unpaired)
 for name,archives in [('probe',None),('diagnostic-probe',diagnostic)]:
  link(cc,name,probeFusion,archives,driver=probeobj)
print('Stage probes, untimed counters and matched span/Y ablations built.')
