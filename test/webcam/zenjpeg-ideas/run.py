#!/usr/bin/env python3
"""Correctness + fixed-frame native/PMU comparisons of zenjpeg-inspired ideas."""
from pathlib import Path
import json
import os
import re
import statistics
import subprocess
import tempfile
import sys

here=Path(__file__).resolve().parent
root=here.parents[2]
base=Path('/tmp/mjpeg-google-bench')
new=['defer-drop','left64','variable-refill','prefix4','dc-dispatch','dc-lite']
if '--only' in sys.argv:
    selected=sys.argv[sys.argv.index('--only')+1:]
    new=[name for name in new if name in selected]
    assert new
    here=here/('confirmation-'+'-'.join(new)); here.mkdir(exist_ok=True)
names=['control',*new]
builds={'control':Path('/tmp/mjpeg-stb-build/threshold-pair10'),
        **{name:Path('/tmp/mjpeg-zen-build')/name for name in new}}
sources={'control':Path('/tmp/mjpeg-stb-src/threshold-pair10'),
         **{name:Path('/tmp/mjpeg-zen-src')/name for name in new}}
if '--config' in sys.argv:
    config_path=Path(sys.argv[sys.argv.index('--config')+1]).resolve()
    config=json.loads(config_path.read_text())
    here=config_path.parent
    new=list(config['variants'])
    names=['control',*new]
    builds={'control':Path(config['control']['build']),
            **{name:Path(info['build']) for name,info in config['variants'].items()}}
    sources={'control':Path(config['control']['source']),
             **{name:Path(info['source']) for name,info in config['variants'].items()}}
def run(cmd,**kw): return subprocess.run(list(map(str,cmd)),check=True,capture_output=True,**kw)
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
assert len(frames)==120
validation={}
for name in new:
    r=run(['ctest','--test-dir',builds[name],'-j','6','--output-on-failure'],text=True)
    (here/f'{name}-ctest.log').write_text(r.stdout+r.stderr)
    count=int(re.search(r'0 tests failed out of (\d+)',r.stdout).group(1))
    validation[name]=dict(ctest_passed=count,camera_frames=120,persistent_modes=5,
                          guarded_frames=5,guarded_chunk_sizes=10)
    print(name,'CTest',count,flush=True)
for frame in frames:
    reference=run([base/'djpeg-static',frame]); assert not reference.stderr
    for name in new:
        actual=run([builds[name]/'djpeg-static',frame])
        assert actual.stdout==reference.stdout and not actual.stderr,(name,frame)
mixed=[frames[0],builds[new[0]]/'testout-static_422_ifast_opt.jpg',
       builds[new[0]]/'testout-static_420_islow_prog.jpg',root/'testimages/testorig.jpg',frames[-1]]
for name in names:
    for tool,source in [('verify',root/'test/webcam/verify.c'),
                         ('guarded',root/'test/webcam/entropy-opt/guarded_source.c')]:
        run(['cc','-O3','-Wall','-Wextra','-I'+str(builds[name]),'-I'+str(sources[name]/'src'),
             source,builds[name]/'libjpeg.a','-lm','-o',Path('/tmp')/('zen-'+tool+'-'+name)])
for mode in ('bgr','gray','half','fast-upsample','fast-idct'):
    sequence=frames+mixed if mode=='bgr' else mixed
    ref=run(['/tmp/zen-verify-control',mode,*sequence]); assert not ref.stderr
    for name in new:
        actual=run(['/tmp/zen-verify-'+name,mode,*sequence])
        assert actual.stdout==ref.stdout and not actual.stderr,(name,mode)
ref=run(['/tmp/zen-guarded-control',*mixed]); assert not ref.stderr
for name in new:
    actual=run(['/tmp/zen-guarded-'+name,*mixed])
    assert actual.stdout==ref.stdout and not actual.stderr,(name,'guarded')
(here/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print('All 120-frame, persistent and guarded checks passed.',flush=True)

drivers={}
for name in names:
    drivers[name]={}
    for kind,source in [('nv12',root/'test/webcam/stb-entropy/nv12_hardware.cc'),
                         ('entropy',root/'test/webcam/cache-profile/driver.cc')]:
        binary=Path('/tmp')/('zen-'+kind+'-'+name)
        cmd=['c++','-O3','-g','-DNDEBUG','-std=c++17','-I'+str(builds[name]),
             '-I'+str(sources[name]/'src'),'-I'+str(root/'benchmarks'),
             '-I'+str(base/'_deps/googlebenchmark-src/include'),str(source),
             str(base/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o')]
        if kind=='nv12': cmd+=[str(base/'_deps/googlebenchmark-build/src/libbenchmark.a')]
        cmd += [str(builds[name]/'libjpeg.a')]
        if kind=='nv12': cmd += [str(builds[name]/'libturbojpeg.a')]
        cmd += ['-lm','-lpthread','-lrt','-o',str(binary)]
        run(cmd); drivers[name][kind]=binary

records=[]
with tempfile.TemporaryDirectory(prefix='zen-ideas-perf-') as tmp:
    ctl=Path(tmp)/'control'; os.mkfifo(ctl); os.mkfifo(str(ctl)+'.ack')
    for kind in ('native','hardware'):
        for mode in ('entropy','accurate','fast'):
            for trial in range(5):
                order=names[trial:]+names[:trial]
                if trial%2: order.reverse()
                for name in order:
                    binary=drivers[name]['entropy' if mode=='entropy' else 'nv12']
                    args=[mode,'100','5','0'] if mode=='entropy' else [mode,'100']
                    cmd=['taskset','-c','0',str(binary),*args]
                    env=dict(os.environ)
                    if kind=='hardware':
                        raw=here/f'{mode}-{trial}-{name}.perf.csv'
                        cmd=['perf','stat','-D','-1','--control',f'fifo:{ctl},{ctl}.ack',
                             '-x',';','-o',str(raw),'-e','{cycles:u,instructions:u,branches:u,branch-misses:u}',
                             '--',*cmd]
                        env['MJPEG_PERF_CONTROL']=str(ctl)
                    r=run(cmd,env=env,text=True,timeout=60)
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
                print(kind,mode,trial,'complete',flush=True)
                (here/'results.json').write_text(json.dumps(records,indent=2)+'\n')
summary={}
for mode in ('entropy','accurate','fast'):
    assert len({r['hash'] for r in records if r['mode']==mode})==1,(mode,'output hashes differ')
    summary[mode]={}
    for name in names:
        a=[r for r in records if r['mode']==mode and r['variant']==name]
        summary[mode][name]=dict(native_ms=statistics.median(r['median_ms'] for r in a if r['kind']=='native'),
             hardware_per_frame={event:statistics.median(r['counts_per_frame'][event] for r in a if r['kind']=='hardware')
                                 for event in ('cycles:u','instructions:u','branches:u','branch-misses:u')})
(here/'summary.json').write_text(json.dumps(dict(cases=summary,validation=validation,
        method='Five rotated/reversed 100-frame native rounds, then five gated non-multiplexed PMU rounds; CPU 0; embedded frame'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
