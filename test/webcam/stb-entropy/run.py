#!/usr/bin/env python3
"""Validate stb-inspired variants, then compare NV12, entropy time and PMU events."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

here=Path(__file__).resolve().parent
root=here.parents[2]
spec=importlib.util.spec_from_file_location('nv12_run',here.parent/'nv12/run.py')
nv12=importlib.util.module_from_spec(spec); spec.loader.exec_module(nv12)
names=['baseline','scalar','pair10','compact9','compact-pair10','threshold-pair10']
new=names[3:]
for name in new:
    nv12.variants[name]=Path('/tmp/mjpeg-stb-build')/name
    nv12.sources[name]=Path('/tmp/mjpeg-stb-src')/name
def run(cmd,**kw):
    return subprocess.run(list(map(str,cmd)),check=True,capture_output=True,**kw)

frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
assert len(frames)==120
validation={}
for name in new:
    result=run(['ctest','--test-dir',nv12.variants[name],'-j','6','--output-on-failure'],text=True)
    (here/(name+'-ctest.log')).write_text(result.stdout+result.stderr)
    count=int(re.search(r'0 tests failed out of (\d+)',result.stdout).group(1))
    validation[name]=dict(ctest_passed=count,camera_pixel_comparisons=120,persistent_modes=5,
                          guarded_frames=5,guarded_chunk_sizes=10)
    print(name,'CTest',count,flush=True)
for frame in frames:
    ref=run([nv12.variants['baseline']/'djpeg-static',frame])
    assert not ref.stderr
    for name in new:
        result=run([nv12.variants[name]/'djpeg-static',frame])
        assert not result.stderr and result.stdout==ref.stdout,(name,frame)
mixed=[frames[0],nv12.variants[new[0]]/'testout-static_422_ifast_opt.jpg',
       nv12.variants[new[0]]/'testout-static_420_islow_prog.jpg',root/'testimages/testorig.jpg',frames[-1]]
for name in ['baseline',*new]:
    for tool,source in [('verify',root/'test/webcam/verify.c'),
                        ('guarded',root/'test/webcam/entropy-opt/guarded_source.c')]:
        run(['cc','-O3','-Wall','-Wextra','-I'+str(nv12.variants[name]),
             '-I'+str(nv12.sources[name]/'src'),source,nv12.variants[name]/'libjpeg.a','-lm',
             '-o',Path('/tmp')/('stb-'+tool+'-'+name)])
for mode in ('bgr','gray','half','fast-upsample','fast-idct'):
    sequence=frames+mixed if mode=='bgr' else mixed
    ref=run(['/tmp/stb-verify-baseline',mode,*sequence])
    for name in new:
        actual=run(['/tmp/stb-verify-'+name,mode,*sequence])
        assert actual.stdout==ref.stdout and not actual.stderr,(name,mode)
ref=run(['/tmp/stb-guarded-baseline',*mixed])
for name in new:
    actual=run(['/tmp/stb-guarded-'+name,*mixed])
    assert actual.stdout==ref.stdout and not actual.stderr,name
(here/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print('All pixel, persistent and guarded checks passed.',flush=True)

binaries={name:nv12.compile_driver(name) for name in names}
nv12.variants['stb']=nv12.variants['baseline']; nv12.sources['stb']=root
binaries['stb']=nv12.compile_driver('stb',extra_flags=['-DMJPEG_STB_REFERENCE'])
build=nv12.build
drivers={}
for name in names:
    drivers[name]=Path('/tmp')/('stb-entropy-'+name)
    run(['c++','-O3','-g','-std=c++17','-I'+str(nv12.variants[name]),
         '-I'+str(nv12.sources[name]/'src'),'-I'+str(root/'benchmarks'),
         root/'test/webcam/cache-profile/driver.cc',
         build/'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o',
         nv12.variants[name]/'libjpeg.a','-lm','-o',drivers[name]])

records=[]
for trial in range(5):
    order=names[trial:]+names[:trial]
    if trial%2: order.reverse()
    # STB position rotates with the complete list in its NV12 comparison.
    all_names=names+['stb']; all_names=all_names[trial:]+all_names[:trial]
    if trial%2: all_names.reverse()
    for name in all_names:
        output=here/f'{trial}-{name}.json'
        pattern='^MJPEG/STB/' if name=='stb' else '^MJPEG/NV12/(Accurate|FastIDCT)/(PlanarThenPack|RawStrips_SIMD)$'
        result=run(['taskset','-c','0',binaries[name],'--benchmark_filter='+pattern,
                    '--benchmark_min_time=0.2s','--benchmark_min_warmup_time=0.03',
                    '--benchmark_out='+str(output),'--benchmark_out_format=json'],text=True)
        (here/f'{trial}-{name}.log').write_text(result.stdout+result.stderr)
        rows=json.loads(output.read_text())['benchmarks']
        assert len(rows)==(1 if name=='stb' else 4) and not any(r.get('error_occurred') for r in rows)
        records.append(dict(trial=trial,variant=name,kind='nv12',cpu_ms={r['name']:r['cpu_time'] for r in rows}))
    for name in order:
        row=json.loads(run(['taskset','-c','0',drivers[name],'entropy','100','5','0'],text=True).stdout)
        row.update(trial=trial,variant=name,kind='entropy-native')
        records.append(row)
    print('Native round',trial,'complete',flush=True)
    (here/'results.json').write_text(json.dumps(records,indent=2)+'\n')

with tempfile.TemporaryDirectory(prefix='stb-perf-') as tmp:
    ctl=Path(tmp)/'control'; os.mkfifo(ctl); os.mkfifo(str(ctl)+'.ack')
    for trial in range(5):
        order=names[trial:]+names[:trial]
        if trial%2: order.reverse()
        for name in order:
            raw=here/f'{trial}-{name}.perf.csv'
            result=run(['perf','stat','-D','-1','--control',f'fifo:{ctl},{ctl}.ack',
                        '-x',';','-o',raw,'-e','{cycles:u,instructions:u,branches:u,branch-misses:u}',
                        '--','taskset','-c','0',drivers[name],'entropy','100','5','0'],
                       env=dict(os.environ,MJPEG_PERF_CONTROL=str(ctl)),text=True,timeout=60)
            counts={}
            for line in raw.read_text().splitlines():
                fields=line.split(';')
                if len(fields)<5 or not fields[2]: continue
                assert fields[0].isdigit() and float(fields[4])>=99.9,line
                counts[fields[2]]=int(fields[0])/100
            row=json.loads(result.stdout)
            row.update(trial=trial,variant=name,kind='entropy-hardware',counts_per_frame=counts)
            records.append(row)
        print('Hardware round',trial,'complete',flush=True)
        (here/'results.json').write_text(json.dumps(records,indent=2)+'\n')

summary={}
for name in names+['stb']:
    a=[r for r in records if r['variant']==name]
    summary[name]={'nv12_ms':{metric:statistics.median(r['cpu_ms'][metric] for r in a if r['kind']=='nv12')
                              for metric in next(r['cpu_ms'] for r in a if r['kind']=='nv12')}}
    if name!='stb':
        summary[name]['entropy_ms']=statistics.median(r['median_ms'] for r in a if r['kind']=='entropy-native')
        summary[name]['entropy_counts_per_frame']={event:statistics.median(r['counts_per_frame'][event]
              for r in a if r['kind']=='entropy-hardware') for event in ('cycles:u','instructions:u','branches:u','branch-misses:u')}
assert len({r['hash'] for r in records if r['kind'].startswith('entropy-')})==1
(here/'summary.json').write_text(json.dumps(dict(cases=summary,method='Five rotated/reversed native rounds, then five non-multiplexed entropy PMU rounds; CPU 0; embedded frame',
                                              validation=validation),indent=2)+'\n')
print(json.dumps(summary,indent=2))
