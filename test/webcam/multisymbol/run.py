#!/usr/bin/env python3
"""Validate multi-symbol prototypes, then compare native time and PMU events."""
from pathlib import Path
import json
import os
import statistics
import subprocess
import tempfile
import sys

here = Path(__file__).resolve().parent
root = here.parents[2]
branchless = '--branchless' in sys.argv[1:]
if branchless:
    here = here/'branchless'
    here.mkdir(exist_ok=True)
builds = dict(baseline=Path('/tmp/mjpeg-google-bench'),
              scalar=Path('/tmp/mjpeg-entropy-opt-build/bulk-once'),
              pair8=Path('/tmp/mjpeg-multi8'), pair10=Path('/tmp/mjpeg-multi10'),
              single10=Path('/tmp/mjpeg-single10'))
if branchless:
    builds.update(pair8=Path('/tmp/mjpeg-multi8-branchless'),
                  pair10=Path('/tmp/mjpeg-multi10-branchless'))
sources = {name: (root if name == 'baseline' else
                 Path('/tmp/mjpeg-entropy-opt-src/bulk-once') if name == 'scalar' else
                 Path('/tmp/mjpeg-multisymbol-src')) for name in builds}
if branchless:
    sources.update(pair8=Path('/tmp/mjpeg-multisymbol-branchless-src'),
                   pair10=Path('/tmp/mjpeg-multisymbol-branchless-src'))
def run(cmd, **kwargs):
    return subprocess.run(list(map(str, cmd)), check=True, capture_output=True, **kwargs)

frames = sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
assert len(frames) == 120
for name, build in builds.items():
    run(['c++', '-O3', '-g', '-std=c++17', '-Wall', '-Wextra', '-I'+str(build),
         '-I'+str(sources[name]/'src'), '-I'+str(root/'benchmarks'),
         root/'test/webcam/cache-profile/driver.cc',
         '/tmp/mjpeg-google-bench/benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o',
         build/'libjpeg.a', '-lm', '-o', here/('driver-'+name)])
    for tool, source in [('verify', root/'test/webcam/verify.c'),
                         ('guarded', root/'test/webcam/entropy-opt/guarded_source.c')]:
        run(['cc', '-O3', '-Wall', '-Wextra', '-I'+str(build), '-I'+str(sources[name]/'src'),
             source, build/'libjpeg.a', '-lm', '-o', here/(tool+'-'+name)])
    if name not in ('baseline', 'scalar') and not (branchless and name == 'single10'):
        result = run(['ctest', '--test-dir', build, '-j', '6', '--output-on-failure'], text=True)
        (here/(name+'-ctest.log')).write_text(result.stdout+result.stderr)
        print(name, 'CTest passed', flush=True)
for frame in frames:
    reference = run([builds['baseline']/'djpeg-static', frame])
    assert not reference.stderr
    for name in ('pair8', 'pair10', 'single10'):
        result = run([builds[name]/'djpeg-static', frame])
        assert not result.stderr and result.stdout == reference.stdout, (name,frame)
mixed = [frames[0], builds['pair8']/'testout-static_422_ifast_opt.jpg',
         builds['pair8']/'testout-static_420_islow_prog.jpg', root/'testimages/testorig.jpg', frames[-1]]
for mode in ('bgr', 'gray', 'half', 'fast-upsample', 'fast-idct'):
    sequence = frames+mixed if mode == 'bgr' else mixed
    reference = run([here/'verify-baseline', mode, *sequence])
    for name in ('pair8', 'pair10', 'single10'):
        result = run([here/('verify-'+name), mode, *sequence])
        assert result.stdout == reference.stdout and not result.stderr, (name,mode)
reference = run([here/'guarded-baseline', *mixed])
for name in ('pair8', 'pair10', 'single10'):
    result = run([here/('guarded-'+name), *mixed])
    assert result.stdout == reference.stdout and not result.stderr, name
(here/'validation.json').write_text(json.dumps(dict(camera_frames=120, variants=3,
    persistent_modes=5, guarded_frames=len(mixed), guarded_chunk_sizes=10,
    ctest_passed_each=332), indent=2)+'\n')
print('Pixel equality, persistent modes and protected source boundaries passed.', flush=True)

records=[]
with tempfile.TemporaryDirectory(prefix='mjpeg-multi-perf-') as tmp:
    ctl=Path(tmp)/'control'
    os.mkfifo(ctl); os.mkfifo(str(ctl)+'.ack')
    # Native timing first, with no profiling process running concurrently.
    for mode in ('entropy', 'full'):
        for kind in ('native', 'hardware'):
            for trial in range(5):
                names=list(builds)
                names=names[trial:]+names[:trial]
                if trial % 2: names.reverse()
                for name in names:
                    cmd=['taskset','-c','0',str(here/('driver-'+name)), mode,'100','5','0']
                    env=dict(os.environ)
                    counts={}
                    if kind=='hardware':
                        raw=here/f'{mode}-{trial}-{name}.perf.csv'
                        cmd=['perf','stat','-D','-1','--control',f'fifo:{ctl},{ctl}.ack',
                             '-x',';','-o',str(raw),'-e',
                             '{cycles:u,instructions:u,branches:u,branch-misses:u}','--',*cmd]
                        env['MJPEG_PERF_CONTROL']=str(ctl)
                    result=run(cmd,env=env,text=True,timeout=60)
                    if kind=='hardware':
                        for line in raw.read_text().splitlines():
                            fields=line.split(';')
                            if len(fields)<5 or not fields[2]: continue
                            assert fields[0].isdigit() and float(fields[4])>=99.9,line
                            counts[fields[2]]=int(fields[0])/100
                    row=json.loads(result.stdout)
                    row.update(variant=name,trial=trial,kind=kind,counts_per_frame=counts)
                    records.append(row)
                    (here/'results.json').write_text(json.dumps(records,indent=2)+'\n')
            print(mode,kind,'complete',flush=True)
summary={}
for mode in ('entropy','full'):
    summary[mode]={}
    for name in builds:
        a=[r for r in records if r['mode']==mode and r['variant']==name]
        summary[mode][name]=dict(native_ms=statistics.median(r['median_ms'] for r in a if r['kind']=='native'),
            **{event:statistics.median(r['counts_per_frame'][event] for r in a if r['kind']=='hardware')
               for event in ('cycles:u','instructions:u','branches:u','branch-misses:u')})
    assert len({r['hash'] for r in records if r['mode']==mode})==1
(here/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
