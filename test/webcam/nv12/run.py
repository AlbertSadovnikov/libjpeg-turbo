#!/usr/bin/env python3
"""Compare NV12 paths against original, scalar-bulk, and two-symbol decoders."""
import json
from pathlib import Path
import statistics
import subprocess

here=Path(__file__).resolve().parent
root=here.parents[2]
build=Path('/tmp/mjpeg-google-bench')
variants=dict(baseline=build,scalar=Path('/tmp/mjpeg-entropy-opt-build/bulk-once'),
              pair10=Path('/tmp/mjpeg-multi10-branchless'))
sources=dict(baseline=root,scalar=Path('/tmp/mjpeg-entropy-opt-src/bulk-once'),
             pair10=Path('/tmp/mjpeg-multisymbol-branchless-src'))
def compile_driver(name,fixture=None,extra_flags=()):
    binary=Path('/tmp')/('nv12-bench-'+name)
    library=variants[name]
    command=['c++','-O3','-DNDEBUG','-std=c++17','-Wall','-Wextra',
             *extra_flags,
             '-I'+str(library),'-I'+str(sources[name]/'src'),'-I'+str(root/'benchmarks'),
             '-I'+str(build/'_deps/googlebenchmark-src/include'),
             str(root/'benchmarks/nv12_bench.cc'),
             str(fixture or build/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o'),
             str(build/'_deps/googlebenchmark-build/src/libbenchmark.a'),
             str(library/'libjpeg.a'),str(library/'libturbojpeg.a'),'-lm','-lpthread','-lrt',
             '-o',str(binary)]
    subprocess.run(command,check=True)
    return binary

if __name__=='__main__':
    binaries={name:compile_driver(name) for name in variants}
    records=[]
    for trial in range(3):
        names=list(variants); names=names[trial:]+names[:trial]
        for name in names:
            output=here/f'{trial}-{name}.json'
            cmd=['taskset','-c','0',str(binaries[name]),'--benchmark_min_time=0.2s',
                 '--benchmark_min_warmup_time=0.03','--benchmark_repetitions=1',
                 '--benchmark_out='+str(output),'--benchmark_out_format=json']
            result=subprocess.run(cmd,capture_output=True,text=True,check=True)
            (here/f'{trial}-{name}.log').write_text(result.stdout+result.stderr)
            rows=json.loads(output.read_text())['benchmarks']
            assert len(rows)==9 and not any(r.get('error_occurred') for r in rows)
            records.append(dict(trial=trial,variant=name,cpu_ms={r['name']:r['cpu_time'] for r in rows}))
            print(trial,name,flush=True)
    summary={name:{metric:statistics.median(r['cpu_ms'][metric] for r in records if r['variant']==name)
                   for metric in records[0]['cpu_ms']} for name in variants}
    (here/'summary.json').write_text(json.dumps(dict(method='Median of three per-run CPU means; rotated variant order; CPU 0; embedded frame',
                                                   cases=summary,records=records),indent=2)+'\n')
    print(json.dumps(summary,indent=2))
