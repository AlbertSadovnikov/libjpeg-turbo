#!/usr/bin/env python3
"""Combine the fusion hook with retained Clang PGO+ThinLTO codec objects."""
from pathlib import Path
import hashlib
import json
import shutil
import statistics
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-fused-chroma')
m=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())
info=m['builds']['clang-pgo-lto'];base=Path(info['build']);build=work/'pgo';build.mkdir(exist_ok=True)
google=Path('/tmp/mjpeg-google-bench')
def run(cmd):
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if result.returncode:print(result.stderr,flush=True)
    result.check_returncode();return result
isolation={}
for lib in ('libjpeg.a','libturbojpeg.a'):
    objdir=build/(lib+'-objects');objdir.mkdir(exist_ok=True);obj=objdir/'jdcoefct-8.c.o'
    extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
    # Changed control flow has no matching old profile. Preserve ThinLTO,
    # and keep the remaining codec members' original PGO profiles intact.
    run(['clang','-O3','-DNDEBUG','-mtune=znver2','-flto=thin','-I'+str(base),*extra,
         '-c',work/'source/src/wrapper/jdcoefct-8.c','-o',obj])
    shutil.copyfile(base/lib,build/lib);run(['llvm-ar-18','r',build/lib,obj]);run(['llvm-ranlib-18',build/lib])
    members=run(['llvm-ar-18','t',base/lib]).stdout.splitlines()
    changed=[]
    for member in members:
        old=subprocess.check_output(['llvm-ar-18','p',str(base/lib),member]);new=subprocess.check_output(['llvm-ar-18','p',str(build/lib),member])
        if old!=new:changed.append(member)
    assert changed==['jdcoefct-8.c.o'],changed
    isolation[lib]=dict(changed_members=changed,sha256=hashlib.sha256((build/lib).read_bytes()).hexdigest())
for name,archives in [('pgo-baseline',base),('pgo-fused',build)]:
    run(['clang++','-fuse-ld=gold',*info['flags'],work/'driver.o',work/'fusion.o',work/'exact.o',
         '/tmp/mjpeg-pgo-lto/heldout-frame.o',google/'_deps/googlebenchmark-build/src/libbenchmark.a',
         archives/'libjpeg.a',archives/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',work/name])
(here/'pgo-isolation.json').write_text(json.dumps(isolation,indent=2)+'\n')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
result=run(['taskset','-c','0',work/'pgo-fused','validate',*frames]);assert not result.stderr,result.stderr
validation=json.loads(result.stdout)
previous=json.loads((here/'validation.json').read_text())
for new,old in zip(validation['cases'],previous['cases']):
    assert new==old,(new,old)
(here/'pgo-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print('PGO integration: complete output and quality metrics match validated kernels.',flush=True)
frames=frames[30:];records=[];paired=[];summary={}
for mode in ('accurate','fast'):
    candidates=['exact','reduced'] if mode=='accurate' else ['reduced']
    for trial in range(3):
        order=candidates if trial%2==0 else candidates[::-1]
        for candidate in order:
            rows=[]
            for position,name in enumerate(('baseline',candidate,'baseline')):
                binary=work/('pgo-baseline' if name=='baseline' else 'pgo-fused');kind={'baseline':0,'exact':1,'reduced':2}[name]
                result=run(['taskset','-c','0',binary,mode,str(kind),'3',*frames]);assert not result.stderr,result.stderr
                row=json.loads(result.stdout);row.update(idct=mode,variant=name,candidate=candidate,trial=trial,position=position)
                rows.append(row);records.append(row)
            if candidate=='exact':assert len({r['hash'] for r in rows})==1
            control=statistics.mean([rows[0]['mean_ms'],rows[2]['mean_ms']]);value=rows[1]['mean_ms']
            paired.append(dict(idct=mode,variant=candidate,trial=trial,control_ms=control,candidate_ms=value,
                               time_change_percent=100*(value/control-1)))
            (here/'pgo-results.json').write_text(json.dumps(dict(paired=paired,records=records),indent=2)+'\n')
            print(paired[-1],flush=True)
    summary[mode]={}
    for candidate in candidates:
        rows=[r for r in paired if r['idct']==mode and r['variant']==candidate]
        c=statistics.mean(r['control_ms'] for r in rows);v=statistics.mean(r['candidate_ms'] for r in rows)
        summary[mode][candidate]=dict(control_ms=c,candidate_ms=v,time_change_percent=100*(v/c-1))
    (here/'pgo-summary.json').write_text(json.dumps(dict(cases=summary,paired=paired,
        method='Three baseline-candidate-baseline brackets per candidate/mode; 90 preloaded held-out frames, three passes after full warmup, CPU 0; only jdcoefct-8 rebuilt without its stale PGO profile, preserving ThinLTO and other codec profiles'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
