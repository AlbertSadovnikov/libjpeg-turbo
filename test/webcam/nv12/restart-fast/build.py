#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--separate",action="store_true");args=p.parse_args()
PREFIX="separate-" if args.separate else ""
TAG="rst-separate" if args.separate else "rst"
W=Path('/tmp/mjpeg-restart-fast')/('separate' if args.separate else '');W.mkdir(parents=True,exist_ok=True);UV=Path('/tmp/mjpeg-paired-fast-chroma');D=Path('/tmp/mjpeg-multi-camera')
records={}
for cc in ('clang','gcc'):
 base=BASE/cc/'current' if cc=='clang' else Path('/tmp/mjpeg-gcc-deferred-loads/gcc-deferred')
 original=(TREE/'src/jdhuff.c').read_text() if cc=='clang' else (base/'source/src/jdhuff.c').read_text()
 old='''      /* Oops, it's actually a marker indicating end of compressed data. */ \\
      cinfo->unread_marker = c1; \\
      /* Back out pre-execution and fill the buffer with zero bits */ \\
      buffer -= 2; \\
      get_buffer &= ~0xFF; \\'''
 new='''      /* Marker lookahead: discard local bit/source/DC state immediately. \\
       * Do not fabricate coefficient bits or consume the marker.  The \\
       * dispatcher clears partial output and replays this MCU slowly. */ \\
      return FALSE; \\'''
 assert original.count(old)==1
 source=original.replace(old,new)
 old='''    usefast = 0;
  }

  /* Preserve the byte reader'''
 new='''    /* Keep the last MCU on the marker-aware slow path.  Earlier MCUs
     * can use the fast reader; speculative marker lookahead rolls back.
     * Small intervals naturally retain the generic path when necessary.
     */
    usefast = entropy->restarts_to_go > 1;
  }

  /* Preserve the byte reader'''
 assert source.count(old)==1;source=source.replace(old,new)
 old='''      if (!decode_mcu_fast(cinfo, MCU_data)) goto use_slow;'''
 new='''      if (!decode_mcu_fast(cinfo, MCU_data)) {
        /* Fast state commits only on success.  Coefficient pointers can
         * belong to different virtual arrays, so clear each block rather
         * than assuming the whole MCU is contiguous.  Constant-size zeroing
         * is compiled inline; the ordinary controller AVX2 clear is retained.
         */
        if (MCU_data) {
          int retry_block;
          for (retry_block = 0; retry_block < cinfo->blocks_in_MCU;
               retry_block++)
            memset(MCU_data[retry_block], 0, sizeof(JBLOCK));
        }
        goto use_slow;
      }'''
 assert source.count(old)==1;source=source.replace(old,new)
 if args.separate:
  # Preserve the original decoder's source and select the restart-aware
  # implementation once per scan. Duplicate just the private fast routine
  # with a marker-aborting GET_BYTE definition; no camera/table constants.
  candidate=source
  mstart=original.index('#define GET_BYTE {');mend=original.index('\n\n#if SIZEOF_SIZE_T',mstart)
  new_macro=candidate[mstart:candidate.index('\n\n#if SIZEOF_SIZE_T',mstart)]
  fstart=original.index('LOCAL(boolean)\ndecode_mcu_fast(');fend=original.index('\n}\n',fstart)+3
  fast=original[fstart:fend].replace('decode_mcu_fast(', 'decode_mcu_restart_fast(',1)
  # Keep the same sanitizer annotation for the cloned arithmetic routine.
  attrs=original[original.rfind('#if defined(__has_feature)',0,fstart):fstart]
  rstart=candidate.index('METHODDEF(boolean)\ndecode_mcu(');rend=candidate.index('\n}\n',rstart)+3
  restart=candidate[rstart:rend].replace('decode_mcu(', 'decode_mcu_restart(',1).replace('decode_mcu_fast(cinfo', 'decode_mcu_restart_fast(cinfo')
  source=original[:fend]+'\n\n/* Restart-only reader; the original routine above keeps its macro expansion. */\n#undef GET_BYTE\n'+new_macro+'\n\n'+attrs+fast+'\n'+original[fend:]
  decl='METHODDEF(boolean) decode_mcu(j_decompress_ptr, JBLOCKROW *);\nMETHODDEF(boolean) decode_mcu_restart(j_decompress_ptr, JBLOCKROW *);\n\n'
  marker='METHODDEF(void)\nstart_pass_huff_decoder('
  assert source.count(marker)==1;source=source.replace(marker,decl+marker)
  marker='  entropy->restarts_to_go = cinfo->restart_interval;\n}'
  assert source.count(marker)==1
  source=source.replace(marker,'  entropy->restarts_to_go = cinfo->restart_interval;\n  /* Select per scan so DRI changes on decoder reuse are honored. */\n  entropy->pub.decode_mcu = cinfo->restart_interval ? decode_mcu_restart : decode_mcu;\n}')
  source+='\n\n/* Selected only for restart-enabled sequential scans. */\n'+restart+'\n'
  assert original[fstart:fend] in source
 patch(here/(cc+'-'+PREFIX+'restart.patch'),original,source)
 folder=W/cc;folder.mkdir(exist_ok=True);tree=folder/'source';shutil.copytree(TREE/'src',tree/'src',dirs_exist_ok=True);(tree/'src/jdhuff.c').write_text(source)
 lto='-flto=thin' if cc=='clang' else '-flto';ar='llvm-ar-18' if cc=='clang' else 'gcc-ar';ranlib='llvm-ranlib-18' if cc=='clang' else 'gcc-ranlib'
 flags=['-O3','-DNDEBUG',lto,'-mbmi2','-I'+str(BASE/cc/'current')]
 for lib in ('libjpeg.a','libturbojpeg.a'):
  d=folder/(lib+'-objects');d.mkdir(exist_ok=True);obj=d/'jdhuff.c.o';extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
  run([cc,*flags,*extra,'-c',tree/'src/jdhuff.c','-o',obj]);shutil.copy2(base/lib,folder/lib);run([ar,'r',folder/lib,obj]);run([ranlib,folder/lib])
  changed=[m for m in run([ar,'t',folder/lib],text=True).stdout.splitlines() if run([ar,'p',folder/lib,m]).stdout!=run([ar,'p',base/lib,m]).stdout];assert changed==['jdhuff.c.o'],changed
 for name,archives in [(TAG+'-control',base),(TAG+'-fast',folder)]:
  b=link(cc,name,WORK/'uv-paired-wrapper.o',archives=archives,driver=D/'exact-driver.o',extra=[UV/'fast.o']);records[cc+'-'+name]={'binary':str(b),'sha256':sha(b),'archives':{str(archives/lib):sha(archives/lib) for lib in ('libjpeg.a','libturbojpeg.a')}}
 records[cc+'-source']={'flags':flags,'source_sha256':sha(tree/'src/jdhuff.c')}
save(here/(PREFIX+'build-summary.json'),{'pgo':False,'explicit_tune':False,'records':records,'changed_member':'jdhuff.c.o','scope':'Restart-aware fast attempts; marker early abort, per-block clear on retry, last-MCU slow path. GCC retains deferred-field expression.'})
print('Built restart-aware candidates and matched controls; no production edits.',flush=True)
