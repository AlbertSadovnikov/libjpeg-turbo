#!/usr/bin/env python3
"""Batch-timed stage measurements normalized by the fixture's 16,200 MCUs."""
import json
import hashlib
from pathlib import Path
import statistics
import subprocess
from run import compile_driver, variants, sources, build

here=Path(__file__).resolve().parent
root=here.parents[2]
out=here/'stages'
out.mkdir(exist_ok=True)
names=('baseline','pair10')
binaries={}
nv12={name:compile_driver(name) for name in names}
for name in names:
    library=variants[name]
    includes=['-I'+str(library),'-I'+str(sources[name]/'src'),'-I'+str(root/'benchmarks')]
    shim=Path('/tmp')/('nv12-stage-shim-'+name+'.o')
    subprocess.run(['cc','-O3','-DNDEBUG',*includes,'-c',str(root/'benchmarks/huffman_tables.c'),
                    '-o',str(shim)],check=True)
    binary=Path('/tmp')/('nv12-stages-'+name)
    subprocess.run(['c++','-O3','-DNDEBUG','-std=c++17',*includes,
                    '-DMJPEG_FRAME_SHA256="'+hashlib.sha256((root/'benchmarks/data/webcam_1920x1080_422.jpg').read_bytes()).hexdigest()+'"',
                    '-I'+str(build/'_deps/googlebenchmark-src/include'),
                    str(root/'benchmarks/mjpeg_bench.cc'),str(shim),
                    str(build/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o'),
                    str(build/'_deps/googlebenchmark-build/src/libbenchmark.a'),
                    str(library/'libjpeg.a'),str(library/'libturbojpeg.a'),'-lm','-lpthread','-lrt',
                    '-o',str(binary)],check=True)
    binaries[name]=binary

stage_filter=r'^MJPEG/(Stages/(EntropyWithStoresAndZeroing|IDCT_(Accurate|Fast)(_(Y|Cb|Cr))?|MCUPipeline_(Accurate|Fast))|Libjpeg/HeaderAndAbort)$'
nv12_filter=r'^MJPEG/NV12/((Accurate|FastIDCT)/(RawStrips_SIMD|PlanarThenPack)|PackOnly_(Scalar|SIMD))$'
records=[]
for trial in range(3):
    for name in (names if trial%2==0 else names[::-1]):
        for group,binary,pattern in [('decode',binaries[name],stage_filter),('nv12',nv12[name],nv12_filter)]:
            output=out/f'{trial}-{name}-{group}.json'
            cmd=['taskset','-c','0',str(binary),'--benchmark_filter='+pattern,
                 '--benchmark_min_time=0.3s','--benchmark_min_warmup_time=0.05',
                 '--benchmark_repetitions=1','--benchmark_out='+str(output),'--benchmark_out_format=json']
            result=subprocess.run(cmd,capture_output=True,text=True,check=True)
            (out/f'{trial}-{name}-{group}.log').write_text(result.stdout+result.stderr)
            rows=json.loads(output.read_text())['benchmarks']
            assert len(rows)==(12 if group=='decode' else 6)
            assert not any(r.get('error_occurred') for r in rows)
            for row in rows:
                ns=row['cpu_time']*{'ns':1,'us':1000,'ms':1e6,'s':1e9}[row['time_unit']]
                records.append(dict(trial=trial,variant=name,stage=row['name'],frame_ns=ns))
            print(trial,name,group,flush=True)
mcus=120*135
summary=dict(mcus_per_frame=mcus,blocks_per_mcu=dict(Y=2,Cb=1,Cr=1),
             method='Median of three CPU-time means, CPU 0, batch-timed full passes, normalized by 16200 MCUs; stages are not additive',
             cases={},records=records)
for name in names:
    summary['cases'][name]={}
    for stage in sorted({r['stage'] for r in records}):
        runs=[r['frame_ns'] for r in records if r['variant']==name and r['stage']==stage]
        ns=statistics.median(runs)
        summary['cases'][name][stage]=dict(frame_ms=ns/1e6,mean_ns_per_mcu=ns/mcus,
                                           min_frame_ms=min(runs)/1e6,max_frame_ms=max(runs)/1e6)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary['cases'],indent=2))
