#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-multi-camera');W.mkdir(exist_ok=True);UV=Path('/tmp/mjpeg-paired-fast-chroma')
s=(UV/'driver.cc').read_text();needle='    auto pack=SimdPack();';assert s.count(needle)==1
s=s.replace('  width=1920;height=1080;subsamp=TJSAMP_422;','  width=height=0;subsamp=TJSAMP_422;')
s=s.replace(needle,'''    jpeg_decompress_struct header{};jpeg_error_mgr err{};header.err=jpeg_std_error(&err);jpeg_create_decompress(&header);
    jpeg_mem_src(&header,frames[0].data(),frames[0].size());Check(jpeg_read_header(&header,TRUE)==JPEG_HEADER_OK,"Header");
    width=header.image_width;height=header.image_height;Check(width%2==0&&height%2==0,"NV12 requires even geometry");jpeg_destroy_decompress(&header);
'''+needle)
(W/'exact-driver.cc').write_text(s)
s=(HERE.parent/'stock-fast/driver.cc').read_text().replace('1920/2*1080','width/2*height').replace('width=1920;height=1080;subsamp=TJSAMP_422;','width=height=0;subsamp=TJSAMP_422;')
needle='      Check(tj3Get(header,TJPARAM_JPEGWIDTH)==width';assert s.count(needle)==1
s=s.replace(needle,'      if(!width){width=tj3Get(header,TJPARAM_JPEGWIDTH);height=tj3Get(header,TJPARAM_JPEGHEIGHT);Check(width%2==0&&height%2==0,"Even NV12 geometry");}\n'+needle)
# Resolve the original source-relative include after moving this generated file.
s=s.replace('#include "../../../../benchmarks/nv12_bench.cc"','#include "'+str(ROOT/'benchmarks/nv12_bench.cc')+'"')
(W/'stock-driver.cc').write_text(s)
for name in ('exact','stock'):
 run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-I'+str(GOOGLE/'_deps/googlebenchmark-src/include'),'-DMJPEG_FUSED_PROTOTYPE="'+str(OLD_COMMON/'nv12-fused.cc')+'"','-c',W/(name+'-driver.cc'),'-o',W/(name+'-driver.o')])
records={}
for cc in ('clang','gcc'):
 # Native support is deliberately shared; archives retain matched compiler/LTO.
 for name,archives,driver in [('stock',BASE/cc/'stock',W/'stock-driver.o'),('exact',BASE/cc/'current',W/'exact-driver.o')]+([('deferred',Path('/tmp/mjpeg-gcc-deferred-loads/gcc-deferred'),W/'exact-driver.o')] if cc=='gcc' else []):
  b=link(cc,'camera-'+name,WORK/'uv-paired-wrapper.o',archives=archives,driver=driver,extra=[UV/'fast.o']);records[cc+'-'+name]={'binary':str(b),'sha256':sha(b),'archives':{str(archives/lib):sha(archives/lib) for lib in ('libjpeg.a','libturbojpeg.a')}}
save(here/'build-summary.json',{'pgo':False,'explicit_tune':False,'records':records,'scope':'Geometry-aware drivers only; existing measured codec/native kernels reused unchanged. Fresh timing cohort.'})
print('Built geometry-aware stock/current/deferred NV12 drivers.',flush=True)
