#!/usr/bin/env python3
"""Bracket the two plausible source changes against compiler-generated BMI2."""
from pathlib import Path
import json
import statistics
import subprocess

here=Path(__file__).resolve().parent; root=here.parents[2]
base=Path('/tmp/mjpeg-google-bench')
builds={'control':Path('/tmp/mjpeg-bmi-current-build/bmi2'),
        **{name:Path('/tmp/mjpeg-intrinsics-build')/name for name in ('bzhi-mask','extend-c')}}
sources={'control':Path('/tmp/mjpeg-bmi-current-src/bmi2'),
         **{name:Path('/tmp/mjpeg-intrinsics-src')/name for name in ('bzhi-mask','extend-c')}}
out=here/'sequence'; out.mkdir(exist_ok=True)
binaries={}
for name,build in builds.items():
    binary=Path('/tmp')/('intrinsics-sequence-'+name)
    subprocess.run(['c++','-O3','-DNDEBUG','-std=c++17','-I'+str(build),
                    '-I'+str(sources[name]/'src'),'-I'+str(root/'benchmarks'),
                    '-I'+str(base/'_deps/googlebenchmark-src/include'),
                    str(root/'test/webcam/bmi-current/nv12_sequence.cc'),
                    str(base/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o'),
                    str(base/'_deps/googlebenchmark-build/src/libbenchmark.a'),
                    str(build/'libjpeg.a'),str(build/'libturbojpeg.a'),'-lm','-lpthread','-lrt',
                    '-o',str(binary)],check=True)
    binaries[name]=binary
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg')); assert len(frames)==120
records=[]; paired=[]
for mode in ('accurate','fast'):
    for trial in range(3):
        order=['bzhi-mask','extend-c'] if trial%2==0 else ['extend-c','bzhi-mask']
        for candidate in order:
            current=[]
            for position,name in enumerate(('control',candidate,'control')):
                r=subprocess.run(['taskset','-c','0',str(binaries[name]),mode,'3',*map(str,frames)],
                                 capture_output=True,text=True,check=True)
                assert not r.stderr,r.stderr
                row=json.loads(r.stdout)
                row.update(mode=mode,trial=trial,variant=name,candidate=candidate,position=position)
                records.append(row); current.append(row)
            assert len({r['hash'] for r in current})==1
            control=statistics.mean(r['mean_ms'] for r in current if r['variant']=='control')
            value=current[1]['mean_ms']
            paired.append(dict(mode=mode,trial=trial,variant=candidate,control_ms=control,
                               candidate_ms=value,reduction_percent=100*(1-value/control)))
            print(mode,trial,candidate,paired[-1],flush=True)
summary={}
for mode in ('accurate','fast'):
    summary[mode]={}
    for name in ('bzhi-mask','extend-c'):
        rows=[r for r in paired if r['mode']==mode and r['variant']==name]
        b=statistics.mean(r['control_ms'] for r in rows); c=statistics.mean(r['candidate_ms'] for r in rows)
        summary[mode][name]=dict(control_ms=b,candidate_ms=c,reduction_percent=100*(1-c/b))
(out/'summary.json').write_text(json.dumps(dict(method='Three control-candidate-control brackets per candidate and IDCT mode, 120 preloaded frames, three passes after full warmup, CPU 0',
                                             cases=summary,paired=paired,records=records),indent=2)+'\n')
print(json.dumps(summary,indent=2))
