#!/usr/bin/env python3
"""Stock public-API fast-IDCT NV12 baseline and same-cohort fused comparison."""
from pathlib import Path
import hashlib
import json
import statistics
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3]
base=Path('/tmp/mjpeg-stock-nv12');google=Path('/tmp/mjpeg-google-bench')
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if r.returncode:print(r.stderr,flush=True)
    r.check_returncode();return r
assert not run(['git','diff','HEAD','--','src','simd']).stdout
flags=(base/'CMakeFiles/jpeg-static.dir/flags.make').read_text();assert 'C_FLAGS = -O3 -DNDEBUG' in flags
binary=base/'stock-fast-nv12'
run(['g++','-O3','-DNDEBUG','-std=c++17','-I'+str(base),'-I'+str(root/'src'),'-I'+str(root/'benchmarks'),
     '-I'+str(google/'_deps/googlebenchmark-src/include'),here/'driver.cc',
     google/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o',google/'_deps/googlebenchmark-build/src/libbenchmark.a',
     base/'libjpeg.a',base/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
validation=run(['taskset','-c','0',binary,'validate','1',*frames]);assert not validation.stderr,validation.stderr
(here/'validation.json').write_text(json.dumps(json.loads(validation.stdout),indent=2)+'\n')
evidence={'compiler':run(['gcc','--version']).stdout.splitlines()[0],
    'flags':'-O3 -DNDEBUG; SIMD enabled; no PGO/LTO or internal patches',
    'codec_source_commit':run(['git','log','-1','--format=%H','--','src','simd']).stdout.strip(),
    'production_source_clean':True,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
    'archive_sha256':{f:hashlib.sha256((base/f).read_bytes()).hexdigest() for f in ('libjpeg.a','libturbojpeg.a')}}
(here/'build-summary.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('Stock fast planar NV12 matches raw fast and scalar packing on all 120 frames.',flush=True)
frames=frames[30:];records=[];paired=[]
fused=Path('/tmp/mjpeg-fused-chroma/pgo-fused');assert fused.exists()
for trial in range(3):
    rows=[]
    for position,name in enumerate(('stock','fused','stock')):
        cmd=[binary,'measure','3',*frames] if name=='stock' else [fused,'fast','2','3',*frames]
        result=run(['taskset','-c','0',*cmd]);assert not result.stderr,result.stderr
        row=json.loads(result.stdout);row.update(variant=name,trial=trial,position=position);records.append(row);rows.append(row)
    assert rows[0]['hash']==rows[2]['hash']
    stock=statistics.mean([rows[0]['mean_ms'],rows[2]['mean_ms']]);value=rows[1]['mean_ms']
    paired.append(dict(trial=trial,stock_ms=stock,fused_ms=value,time_reduction_percent=100*(1-value/stock)))
    (here/'results.json').write_text(json.dumps(dict(paired=paired,records=records),indent=2)+'\n')
    print(paired[-1],flush=True)
stock=statistics.mean(r['stock_ms'] for r in paired);value=statistics.mean(r['fused_ms'] for r in paired)
summary=dict(stock_ms=stock,fused_ms=value,time_reduction_percent=100*(1-value/stock),
    stock_decode_ms=statistics.mean(r['decode_ms'] for r in records if r['variant']=='stock'),
    stock_pack_ms=statistics.mean(r['pack_ms'] for r in records if r['variant']=='stock'),
    method='Three stock-fused-stock brackets; fast IDCT on both; 90 held-out preloaded frames; three passes after full warmup; CPU 0; disk/allocation/hash excluded; fused UV retains documented quality difference')
(here/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
