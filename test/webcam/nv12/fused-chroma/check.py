#!/usr/bin/env python3
from pathlib import Path
import subprocess
here=Path(__file__).resolve().parent;root=here.parents[3]
work=Path('/tmp/mjpeg-fused-chroma');base=Path('/tmp/mjpeg-pgo-lto/gcc-base')
subprocess.run(['g++','-O3','-DNDEBUG','-std=c++17','-I'+str(base),'-I'+str(work/'source/src'),
    '-I'+str(root/'benchmarks'),str(here/'check.cc'),str(work/'fusion.o'),str(work/'exact.o'),
    '/tmp/mjpeg-pgo-lto/heldout-frame.o',str(base/'libjpeg.a'),'-lm','-o',str(work/'check')],check=True)
result=subprocess.run([str(work/'check')],check=True,capture_output=True,text=True)
assert not result.stderr,result.stderr
(here/'kernel-summary.json').write_text(result.stdout)
print(result.stdout,end='')
