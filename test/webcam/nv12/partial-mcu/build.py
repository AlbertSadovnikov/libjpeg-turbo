#!/usr/bin/env python3
from pathlib import Path
import sys,argparse
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
parser=argparse.ArgumentParser();parser.add_argument('--inline',action='store_true');args=parser.parse_args()
W=Path('/tmp/mjpeg-partial-mcu');W.mkdir(exist_ok=True)
s=(WORK/'uv-paired-wrapper.cc').read_text()
needle='c->image_width%16||c->image_height%8||';assert s.count(needle)==1
s=s.replace(needle,'(mode==3 ? (c->image_width%2||c->image_height%2) : (c->image_width%16||c->image_height%8))||')
needle='  if(ctx.c!=c)return 0;';assert s.count(needle)==1
edge=(here/'edge.cc').read_text()
if args.inline:
 s=s.replace(needle,needle+'\n'+edge)
else:
 # Keep edge scratch storage out of the direct reconstruction function.
 a=edge.index('    const unsigned x=');body=edge[a:edge.rfind('  }')]
 helper='static __attribute__((noinline)) int partial_mcu(j_decompress_ptr c,JBLOCKROW *blocks,JSAMPIMAGE output,JDIMENSION col) {\n'+body+'}\n'
 s=s.replace('static thread_local Context ctx;','static thread_local Context ctx;\nstatic thread_local bool partial_frame=false;')
 s=s.replace('  ctx.c=nullptr;','  ctx.c=nullptr; partial_frame=(c->image_width%16 || c->image_height%8);')
 s=s.replace('extern "C" int mjpeg_fusion_mcu(',helper+'\nextern "C" int mjpeg_fusion_mcu(')
 s=s.replace(needle,needle+'\n  if(partial_frame && (col*16+16>c->image_width || c->input_iMCU_row*8+8>c->image_height))\n    return partial_mcu(c,blocks,output,col);')
(W/'fusion.cc').write_text(s)
(here/'fusion.patch').write_text(''.join(difflib.unified_diff((WORK/'uv-paired-wrapper.cc').read_text().splitlines(True),s.splitlines(True),fromfile='a/fusion.cc',tofile='b/fusion.cc')))
run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*INCLUDES,'-c',W/'fusion.cc','-o',W/'fusion.o'])
records={}
for cc in ('clang','gcc'):
 archives=BASE/cc/'current' if cc=='clang' else Path('/tmp/mjpeg-gcc-deferred-loads/gcc-deferred')
 b=link(cc,'partial-mcu',W/'fusion.o',archives=archives,driver=Path('/tmp/mjpeg-multi-camera/exact-driver.o'),extra=[Path('/tmp/mjpeg-paired-fast-chroma/fast.o')])
 records[cc]=dict(binary=str(b),sha256=sha(b),archives={str(archives/lib):sha(archives/lib) for lib in ('libjpeg.a','libturbojpeg.a')})
save(here/'build-summary.json',dict(implementation='inline edge' if args.inline else 'out-of-line edge helper',base_wrapper_sha256=sha(WORK/'uv-paired-wrapper.cc'),pgo=False,explicit_tune=False,core_LTO=True,wrapper_LTO=False,wrapper_flags=['-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*INCLUDES],source_sha256=sha(W/'fusion.cc'),object_sha256=sha(W/'fusion.o'),records=records))
print('Built partial-MCU reconstruction experiment.',flush=True)
