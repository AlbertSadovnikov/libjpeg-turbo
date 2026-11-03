#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
parser=argparse.ArgumentParser();parser.add_argument("--paired-entry",action="store_true");args=parser.parse_args()
TAG="two-mcu-pair" if args.paired_entry else "two-mcu"
PREFIX="paired-" if args.paired_entry else ""
W=Path('/tmp/mjpeg-two-mcu');W.mkdir(exist_ok=True)
original=(TREE/'src/jdcoefct.c').read_text()
# The query uses the existing full fusion eligibility checks and only mode 3.
query='extern int mjpeg_two_mcu_active(j_decompress_ptr);\n'
source=original.replace('#ifdef WITH_PROFILE\n#include "tjutil.h"',query+'#ifdef WITH_PROFILE\n#include "tjutil.h"',1)
needle='''    for (MCU_col_num = coef->MCU_ctr; MCU_col_num <= last_MCU_col;
         MCU_col_num++) {'''
assert source.count(needle)==1
batch='''#if BITS_IN_JSAMPLE == 8
    /* Benchmark-only two-MCU scheduling. Fusion registration has already
     * checked uncropped, unscaled, complete 4:2:2 blocks and fast IDCT.
     * Both buffers are cleared with the existing inline AVX2 implementation.
     * Entropy remains strictly serial; only reconstruction is delayed.
     */
    if (mjpeg_two_mcu_active(cinfo)) {
      JBLOCK second[4];
      JBLOCKROW next[4] = { second, second + 1, second + 2, second + 3 };
      for (MCU_col_num = coef->MCU_ctr; MCU_col_num <= last_MCU_col;
           MCU_col_num += 2) {
        mjpeg_clear_experiment(coef->MCU_buffer[0], 4 * sizeof(JBLOCK));
        if (!cinfo->entropy->insufficient_data)
          cinfo->master->last_good_iMCU_row = cinfo->input_iMCU_row;
        if (!(*cinfo->entropy->decode_mcu)(cinfo, coef->MCU_buffer)) {
          coef->MCU_vert_offset = yoffset;
          coef->MCU_ctr = MCU_col_num;
          return JPEG_SUSPENDED;
        }
        if (MCU_col_num < last_MCU_col) {
          mjpeg_clear_experiment(second, sizeof(second));
          if (!cinfo->entropy->insufficient_data)
            cinfo->master->last_good_iMCU_row = cinfo->input_iMCU_row;
          if (!(*cinfo->entropy->decode_mcu)(cinfo, next)) {
            /* First MCU committed; emit it before returning. Resume at the
             * second MCU with normal entropy rollback, never decode it twice.
             */
            mjpeg_fusion_mcu(cinfo, coef->MCU_buffer, output_buf, MCU_col_num);
            coef->MCU_vert_offset = yoffset;
            coef->MCU_ctr = MCU_col_num + 1;
            return JPEG_SUSPENDED;
          }
          mjpeg_fusion_mcu(cinfo, coef->MCU_buffer, output_buf, MCU_col_num);
          mjpeg_fusion_mcu(cinfo, next, output_buf, MCU_col_num + 1);
        } else {
          /* Odd row length: reconstruct the final single MCU. */
          mjpeg_fusion_mcu(cinfo, coef->MCU_buffer, output_buf, MCU_col_num);
        }
      }
      goto two_mcu_row_completed;
    }
#endif
'''
source=source.replace(needle,batch+needle)
needle='''    /* Completed an MCU row, but perhaps not an iMCU row */'''
source=source.replace(needle,'two_mcu_row_completed:\n'+needle,1)
if args.paired_entry:
 source=source.replace(query,query+'extern void mjpeg_two_mcu_reconstruct(j_decompress_ptr, JBLOCKROW *, JBLOCKROW *, JSAMPIMAGE, JDIMENSION);\n')
 old='          mjpeg_fusion_mcu(cinfo, coef->MCU_buffer, output_buf, MCU_col_num);\n          mjpeg_fusion_mcu(cinfo, next, output_buf, MCU_col_num + 1);'
 assert source.count(old)==1
 source=source.replace(old,'          mjpeg_two_mcu_reconstruct(cinfo, coef->MCU_buffer, next, output_buf, MCU_col_num);')
(here/(PREFIX+'controller.patch')).write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='a/src/jdcoefct.c',tofile='b/src/jdcoefct.c')))
# Same exact-fast wrapper for both; mode 3 alone can enter the new schedule.
text=(Path('/tmp/mjpeg-paired-fast-chroma')/'fusion.cc').read_text()
text+='\nextern "C" int mjpeg_two_mcu_active(j_decompress_ptr c) { return ctx.c==c && ctx.mode==3; }\n'
if args.paired_entry:
 text+=r'''
// Called only after the fast-exact registration guard. Cache shared per-pair
// pointers and dispatch directly to the same two native kernels per MCU.
extern "C" void mjpeg_two_mcu_reconstruct(j_decompress_ptr c,JBLOCKROW *a,JBLOCKROW *b,JSAMPIMAGE out,JDIMENSION col) {
 const void *qy=c->comp_info[0].dct_table,*qu=c->comp_info[1].dct_table,*qv=c->comp_info[2].dct_table;
 auto y=out[0];const int pitch=ctx.pitch;
 auto uv=ctx.uv+c->input_iMCU_row*4*pitch+col*16;
 mjpeg_idct_ifast_registers(qy,*a[0],*a[1],y,col*16);
 mjpeg_chroma_fast_pair(qu,qv,*a[2],*a[3],uv,pitch);
 mjpeg_idct_ifast_registers(qy,*b[0],*b[1],y,(col+1)*16);
 mjpeg_chroma_fast_pair(qu,qv,*b[2],*b[3],uv+16,pitch);
}
'''
obj=wrapper(TAG+'-wrapper',text)
records={}
for cc in ('clang','gcc'):
 folder=W/(PREFIX+cc);folder.mkdir(exist_ok=True)
 tree=folder/'src';shutil.copytree(TREE/'src',tree,dirs_exist_ok=True)
 (tree/'jdcoefct.c').write_text(source)
 lto='-flto=thin' if cc=='clang' else '-flto';ar='llvm-ar-18' if cc=='clang' else 'gcc-ar';ranlib='llvm-ranlib-18' if cc=='clang' else 'gcc-ranlib'
 for lib in ('libjpeg.a','libturbojpeg.a'):
  objdir=folder/(lib+'-objects');objdir.mkdir(exist_ok=True);co=objdir/'jdcoefct-8.c.o'
  flags=[cc,'-O3','-DNDEBUG',lto,'-I'+str(BASE/cc/'current')]
  # jdcoefct is a generic target in the baseline; do not inherit entropy BMI2.
  run([*flags,'-c',tree/'wrapper/jdcoefct-8.c','-o',co])
  shutil.copy2(BASE/cc/'current'/lib,folder/lib);run([ar,'r',folder/lib,co]);run([ranlib,folder/lib])
  changed=[m for m in run([ar,'t',folder/lib],text=True).stdout.splitlines() if run([ar,'p',folder/lib,m]).stdout!=run([ar,'p',BASE/cc/'current'/lib,m]).stdout]
  assert changed==['jdcoefct-8.c.o'],changed
 for name,archives in [(TAG+'-control',BASE/cc/'current'),(TAG,folder)]:
  binary=link(cc,name,obj,archives=archives,driver=Path('/tmp/mjpeg-paired-fast-chroma/driver.o'),extra=[Path('/tmp/mjpeg-paired-fast-chroma/fast.o')])
  records[cc+'-'+name]={'binary':str(binary),'sha256':sha(binary)}
 records[cc+'-archives']={str(folder/lib):sha(folder/lib) for lib in ('libjpeg.a','libturbojpeg.a')}
save(here/(PREFIX+'build-summary.json'),{'pgo':False,'explicit_tune':False,'optimization':'O3; Clang ThinLTO / GCC LTO','changed_member':'jdcoefct-8.c.o','wrapper_sha256':sha(WORK/(TAG+'-wrapper.cc')),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'records':records})
print('Built two-MCU controller and matched single-MCU controls.',flush=True)
