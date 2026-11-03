#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--wrapped",action="store_true");args=p.parse_args()
W=Path('/tmp/mjpeg-restart-segment');W.mkdir(exist_ok=True);TU=Path('/tmp/mjpeg-restart-tu');UV=Path('/tmp/mjpeg-paired-fast-chroma');records={}
proto=(OLD_COMMON/'nv12-fused.cc').read_text();needle='    const bool fused=mjpeg_fusion_begin(&c,uv,uv_pitch,mjpeg_requested_mode);';assert proto.count(needle)==1
proto=proto.replace(needle,needle+'\n    if(fused && mjpeg_requested_mode==3 && c.restart_interval) mjpeg_segment_install(&c);')
(W/'prototype.cc').write_text(proto)
driver=Path('/tmp/mjpeg-multi-camera/exact-driver.cc').read_text();driver=driver.replace('int mjpeg_requested_mode=0;','int mjpeg_requested_mode=0;\nextern "C" int mjpeg_segment_enabled;\nextern "C" int mjpeg_segment_install(j_decompress_ptr);')
needle='  if(argc<3)return 2;';assert driver.count(needle)==1
driver=driver.replace(needle,needle+'\n  const char *segment_flag=std::getenv("MJPEG_SEGMENT");\n  mjpeg_segment_enabled=!(segment_flag && std::strcmp(segment_flag,"0")==0);')
(W/'driver.cc').write_text(driver)
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-I'+str(GOOGLE/'_deps/googlebenchmark-src/include'),'-DMJPEG_FUSED_PROTOTYPE="'+str(W/'prototype.cc')+'"','-c',W/'driver.cc','-o',W/'driver.o'])
for cc in ('clang','gcc'):
 d=W/cc;d.mkdir(exist_ok=True)
 s=(TU/cc/'restart.c').read_text();s=s[:s.index('#define BUFSIZE')]
 s=s.replace('mjpeg_restart_','mjpeg_segment_')
 s='#define BITS_IN_JSAMPLE 8\n'+s
 signature='decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)';assert s.count(signature)==1
 s=s.replace(signature,'segment_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data,\n             bitread_working_state *working, savable_state *predictors)')
 old='''  BITREAD_LOAD_STATE(cinfo, entropy->bitstate);
  buffer = (JOCTET *)br_state.next_input_byte;
  state = entropy->saved;''';assert s.count(old)==1
 s=s.replace(old,'''  br_state = *working;
  get_buffer = working->get_buffer;
  bits_left = working->bits_left;
  buffer = (JOCTET *)br_state.next_input_byte;
  state = *predictors;''')
 old='''  BITREAD_SAVE_STATE(cinfo, entropy->bitstate);
  entropy->saved = state;
  return TRUE;
}'''
 # The slow routine retains its global commit. Replace only in fast body.
 a=s.index('segment_fast(');head=s[:a];body=s[a:];assert body.count(old)==1
 body=body.replace(old,'''  br_state.get_buffer = get_buffer;
  br_state.bits_left = bits_left;
  *working = br_state;
  *predictors = state;
  return TRUE;
}''')
 s=head+body+'\n'+(here/'controller.c').read_text();(d/'segment.c').write_text(s)
 flags=['-O3','-DNDEBUG','-fno-lto','-mbmi2','-I'+str(BASE/cc/'current'),'-I'+str(TU/cc/'source/src')]
 run([cc,*flags,'-c',d/'segment.c','-o',d/'segment.o'])
 adapter=[]
 if args.wrapped:
  run([cc,'-O3','-DNDEBUG','-fno-lto','-I'+str(BASE/cc/'current'),'-I'+str(TU/cc/'source/src'),'-c',here/'adapter.c','-o',d/'adapter.o'])
  adapter=[d/'adapter.o','-Wl,--wrap=mjpeg_fusion_begin']
 b=link(cc,'segment',WORK/'uv-paired-wrapper.o',archives=TU/cc,driver=(Path('/tmp/mjpeg-multi-camera/exact-driver.o') if args.wrapped else W/'driver.o'),extra=[UV/'fast.o',TU/cc/'restart.o',d/'segment.o',*adapter])
 records[cc]={'binary':str(b),'sha256':sha(b),'flags':flags,'source_sha256':sha(d/'segment.c'),'object_sha256':sha(d/'segment.o'),'archives':{str(TU/cc/lib):sha(TU/cc/lib) for lib in ('libjpeg.a','libturbojpeg.a')},'baseline_binary':str(WORK/'bin'/(cc+'-tu-fast'))}
save(here/'build-summary.json',{'pgo':False,'explicit_tune':False,'core_archives_unchanged':True,'packaging':'original driver plus registration adapter' if args.wrapped else 'driver hook','driver_sha256':sha(Path('/tmp/mjpeg-multi-camera/exact-driver.o') if args.wrapped else W/'driver.o'),'prototype_sha256':sha(OLD_COMMON/'nv12-fused.cc' if args.wrapped else W/'prototype.cc'),'records':records,'enable_switch':'MJPEG_SEGMENT=0/1 before process startup; same executable, outside timed regions.'})
print('Built serial segment controllers with local bit/DC state; original archives unchanged.',flush=True)
