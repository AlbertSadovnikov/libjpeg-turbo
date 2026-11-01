#!/usr/bin/env python3
from pathlib import Path
import subprocess
here=Path(__file__).resolve().parent;root=here.parents[3]
work=Path('/tmp/mjpeg-fused-chroma');base=Path('/tmp/mjpeg-pgo-lto/gcc-base');google=Path('/tmp/mjpeg-google-bench')
text=(root/'benchmarks/nv12_bench.cc').read_text()
old='    Check(jpeg_start_decompress(&c),"JPEG start");';assert text.count(old)==1
text=text.replace(old,old+'\n    const bool fused=mjpeg_fusion_begin(&c,uv,uv_pitch,mjpeg_requested_mode);')
old='      pack(uv+y/2*uv_pitch,u.data(),v.data(),cp,uv_pitch,width/2,valid/2,subsamp==TJSAMP_422);';assert text.count(old)==1
text=text.replace(old,'      if(!fused) '+old.strip())
old='    Check(jpeg_finish_decompress(&c),"JPEG finish");';assert text.count(old)==1
text=text.replace(old,old+'\n    mjpeg_fusion_end();')
prototype=work/'nv12-fused.cc';prototype.write_text(text)
obj=work/'driver.o'
subprocess.run(['g++','-O3','-DNDEBUG','-std=c++17','-I'+str(base),'-I'+str(work/'source/src'),'-I'+str(here),'-I'+str(root/'benchmarks'),'-I'+str(google/'_deps/googlebenchmark-src/include'),'-DMJPEG_FUSED_PROTOTYPE="'+str(prototype)+'"','-c',str(here/'driver.cc'),'-o',str(obj)],check=True)
for name,build in [('baseline',base),('fused',work)]:
    subprocess.run(['g++','-fuse-ld=gold',str(obj),str(work/'fusion.o'),str(work/'exact.o'),
        '/tmp/mjpeg-pgo-lto/heldout-frame.o',str(google/'_deps/googlebenchmark-build/src/libbenchmark.a'),
        str(build/'libjpeg.a'),str(build/'libturbojpeg.a'),'-lm','-lpthread','-lrt','-o',str(work/name)],check=True)
print('Matched NV12 drivers linked.',flush=True)
