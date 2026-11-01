#!/usr/bin/env python3
"""Batch-timed chroma costs using the retained best Clang NV12 candidate."""
from pathlib import Path
import json
import statistics
import subprocess

here=Path(__file__).resolve().parent
root=here.parents[3]
work=Path('/tmp/mjpeg-pgo-lto');google=Path('/tmp/mjpeg-google-bench')
manifest=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())
info=manifest['builds']['clang-pgo-lto'];build=Path(info['build']);obj=work/'chroma-budget.o'
subprocess.run(['g++','-O3','-DNDEBUG','-std=c++17','-I'+str(build),
    '-I'+str(Path(info['source'])/'src'),'-I'+str(root/'benchmarks'),
    '-I'+str(google/'_deps/googlebenchmark-src/include'),'-c',str(here/'driver.cc'),'-o',str(obj)],check=True)
binary=work/'chroma-budget'
subprocess.run(['clang++','-fuse-ld=gold',*info['flags'],str(obj),str(work/'heldout-frame.o'),
    str(google/'_deps/googlebenchmark-build/src/libbenchmark.a'),str(build/'libjpeg.a'),
    str(build/'libturbojpeg.a'),'-lm','-lpthread','-lrt','-o',str(binary)],check=True)
rows=[]
for trial in range(3):
    result=subprocess.run(['taskset','-c','0',str(binary)],check=True,capture_output=True,text=True)
    assert not result.stderr,result.stderr
    row=json.loads(result.stdout);row['trial']=trial;rows.append(row)
    (here/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(trial,'complete',flush=True)
summary={}
for mode in ('accurate','fast'):
    r={key:statistics.median(row['modes'][mode][key] for row in rows) for key in rows[0]['modes'][mode]}
    r['UV_idct_percent']=100*r['UV_idct_ms']/r['full_ms']
    r['halve_interleave_percent']=100*r['halve_interleave_ms']/r['full_ms']
    r['UV_reconstruction_and_pack_ms']=r['UV_idct_ms']+r['halve_interleave_ms']
    r['UV_reconstruction_and_pack_percent']=100*r['UV_reconstruction_and_pack_ms']/r['full_ms']
    summary[mode]=r
(here/'summary.json').write_text(json.dumps(dict(cases=summary,planes=rows[0]['planes'],
    fixture=manifest['split']['entropy_frame'],mcus=16200,
    method='Median of three batch means, at least 0.2 seconds per stage, CPU 0; isolated stages are not strictly additive'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
