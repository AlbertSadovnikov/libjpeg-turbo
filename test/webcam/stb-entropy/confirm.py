#!/usr/bin/env python3
"""Fixed-frame NV12 confirmation: native time and gated hardware counters."""
from pathlib import Path
import json
import os
import statistics
import subprocess
import tempfile

here=Path(__file__).resolve().parent
root=here.parents[2]
base=Path('/tmp/mjpeg-google-bench')
builds=dict(pair10=Path('/tmp/mjpeg-multi10-branchless'),
            threshold=Path('/tmp/mjpeg-stb-build/threshold-pair10'))
sources=dict(pair10=Path('/tmp/mjpeg-multisymbol-branchless-src'),
             threshold=Path('/tmp/mjpeg-stb-src/threshold-pair10'))
drivers={}
for name,build in builds.items():
    binary=Path('/tmp')/('nv12-confirm-'+name)
    subprocess.run(['c++','-O3','-DNDEBUG','-std=c++17','-I'+str(build),
                    '-I'+str(sources[name]/'src'),'-I'+str(root/'benchmarks'),
                    '-I'+str(base/'_deps/googlebenchmark-src/include'),
                    str(here/'nv12_hardware.cc'),
                    str(base/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o'),
                    str(base/'_deps/googlebenchmark-build/src/libbenchmark.a'),
                    str(build/'libjpeg.a'),str(build/'libturbojpeg.a'),'-lm','-lpthread','-lrt',
                    '-o',str(binary)],check=True)
    drivers[name]=binary
records=[]
with tempfile.TemporaryDirectory(prefix='nv12-confirm-') as tmp:
    ctl=Path(tmp)/'control'; os.mkfifo(ctl); os.mkfifo(str(ctl)+'.ack')
    for kind in ('native','hardware'):
        for mode in ('accurate','fast'):
            for trial in range(5):
                for name in (list(builds) if trial%2==0 else list(builds)[::-1]):
                    cmd=['taskset','-c','0',str(drivers[name]),mode,'100']
                    env=dict(os.environ)
                    if kind=='hardware':
                        raw=here/f'confirm-{mode}-{trial}-{name}.perf.csv'
                        cmd=['perf','stat','-D','-1','--control',f'fifo:{ctl},{ctl}.ack',
                             '-x',';','-o',str(raw),'-e','{cycles:u,instructions:u,branches:u,branch-misses:u}',
                             '--',*cmd]
                        env['MJPEG_PERF_CONTROL']=str(ctl)
                    r=subprocess.run(cmd,env=env,capture_output=True,text=True,check=True,timeout=60)
                    row=json.loads(r.stdout); row.update(kind=kind,mode=mode,trial=trial,variant=name)
                    if kind=='hardware':
                        counts={}
                        for line in raw.read_text().splitlines():
                            f=line.split(';')
                            if len(f)<5 or not f[2]: continue
                            assert f[0].isdigit() and float(f[4])>=99.9,line
                            counts[f[2]]=int(f[0])/100
                        row['counts_per_frame']=counts
                    records.append(row)
            print(kind,mode,'complete',flush=True)
summary={}
for mode in ('accurate','fast'):
    assert len({r['hash'] for r in records if r['mode']==mode})==1
    summary[mode]={}
    for name in builds:
        a=[r for r in records if r['mode']==mode and r['variant']==name]
        summary[mode][name]=dict(native_ms=statistics.median(r['median_ms'] for r in a if r['kind']=='native'),
             hardware_per_frame={event:statistics.median(r['counts_per_frame'][event] for r in a if r['kind']=='hardware')
                                 for event in ('cycles:u','instructions:u','branches:u','branch-misses:u')})
output=here/'confirmation'; output.mkdir(exist_ok=True)
(output/'summary.json').write_text(json.dumps(dict(cases=summary,records=records),indent=2)+'\n')
print(json.dumps(summary,indent=2))
