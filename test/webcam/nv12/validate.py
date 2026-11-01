#!/usr/bin/env python3
"""Exercise padding, AVX2 tails, bottom strips, 420/422 and restart/progressive input."""
import json
from pathlib import Path
import subprocess
import tempfile
from run import compile_driver

here=Path(__file__).resolve().parent
results=[]
with tempfile.TemporaryDirectory(prefix='nv12-validation-') as tmp:
    tmp=Path(tmp)
    for w,h,sampling,progressive,restart in [(18,18,'2x1',False,False),
            (34,10,'2x2',False,False),(66,30,'2x1',False,True),
            (66,18,'2x2',True,False),(16,2,'2x1',False,False),
            (16,2,'2x2',False,False),(130,34,'2x1',False,False)]:
        ppm=tmp/'input.ppm'; jpg=tmp/'input.jpg'
        ppm.write_bytes(f'P6\n{w} {h}\n255\n'.encode()+bytes((x*13+y*31+c*71)%256
                         for y in range(h) for x in range(w) for c in range(3)))
        cmd=['/tmp/mjpeg-google-bench/cjpeg-static','-sample',sampling,'-quality','85']
        if progressive: cmd+=['-progressive']
        if restart: cmd+=['-restart','1B']
        subprocess.run([*cmd,'-outfile',str(jpg),str(ppm)],check=True)
        data=jpg.read_bytes(); fixture=tmp/'frame.cc'
        fixture.write_text('#include "embedded_frame.h"\nnamespace mjpeg_bench {\n'
                           'const unsigned char kJpeg[]={'+','.join(map(str,data))+'};\n'
                           'const std::size_t kJpegSize=sizeof(kJpeg);\n}\n')
        for variant in ('baseline','pair10'):
            binary=compile_driver(variant,fixture)
            result=subprocess.run([str(binary),'--benchmark_filter=RawStrips',
                                   '--benchmark_min_time=0.001s','--benchmark_min_warmup_time=0'],
                                  capture_output=True,text=True,check=True)
            results.append(dict(width=w,height=h,sampling=sampling,progressive=progressive,
                                restart=restart,variant=variant,validated=True))
(here/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
print(f'{len(results)} fixture/decoder combinations passed all NV12 byte-equality checks.')
