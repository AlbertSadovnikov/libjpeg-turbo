#!/usr/bin/env python3
"""Bracket BMI2 with controls on all 120 preloaded NV12 frames."""
from pathlib import Path
import json
import statistics
import subprocess

here=Path(__file__).resolve().parent; root=here.parents[2]
base=Path('/tmp/mjpeg-google-bench')
builds=dict(control=Path('/tmp/mjpeg-stb-build/threshold-pair10'),
            bmi2=Path('/tmp/mjpeg-bmi-current-build/bmi2'))
sources=dict(control=Path('/tmp/mjpeg-stb-src/threshold-pair10'),
             bmi2=Path('/tmp/mjpeg-bmi-current-src/bmi2'))
binaries={}
out=here/'sequence'; out.mkdir(exist_ok=True)
for name,build in builds.items():
    binary=Path('/tmp')/('bmi-current-sequence-'+name)
    subprocess.run(['c++','-O3','-DNDEBUG','-std=c++17','-I'+str(build),
                    '-I'+str(sources[name]/'src'),'-I'+str(root/'benchmarks'),
                    '-I'+str(base/'_deps/googlebenchmark-src/include'),str(here/'nv12_sequence.cc'),
                    str(base/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o'),
                    str(base/'_deps/googlebenchmark-build/src/libbenchmark.a'),
                    str(build/'libjpeg.a'),str(build/'libturbojpeg.a'),'-lm','-lpthread','-lrt',
                    '-o',str(binary)],check=True)
    binaries[name]=binary
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg')); assert len(frames)==120
records=[]; paired=[]
for mode in ('accurate','fast'):
    for trial in range(3):
        current=[]
        for position,name in enumerate(('control','bmi2','control')):
            r=subprocess.run(['taskset','-c','0',str(binaries[name]),mode,'3',*map(str,frames)],
                             capture_output=True,text=True,check=True)
            assert not r.stderr,r.stderr
            row=json.loads(r.stdout); row.update(mode=mode,trial=trial,variant=name,position=position)
            records.append(row); current.append(row)
        assert len({r['hash'] for r in current})==1,'Full-sequence NV12 hashes differ'
        control=statistics.mean(r['mean_ms'] for r in current if r['variant']=='control')
        candidate=current[1]['mean_ms']
        paired.append(dict(mode=mode,trial=trial,control_ms=control,bmi2_ms=candidate,
                           reduction_percent=100*(1-candidate/control)))
        print(mode,trial,paired[-1],flush=True)
summary={mode:dict(control_ms=statistics.mean(r['control_ms'] for r in paired if r['mode']==mode),
                  bmi2_ms=statistics.mean(r['bmi2_ms'] for r in paired if r['mode']==mode)) for mode in ('accurate','fast')}
for values in summary.values(): values['reduction_percent']=100*(1-values['bmi2_ms']/values['control_ms'])
(out/'summary.json').write_text(json.dumps(dict(method='Three control-candidate-control brackets per IDCT mode; 120 preloaded frames; three passes after one warmup pass; CPU 0',
                                             cases=summary,paired=paired,records=records),indent=2)+'\n')
print(json.dumps(summary,indent=2))
