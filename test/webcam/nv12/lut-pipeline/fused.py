#!/usr/bin/env python3
"""Check promising loop changes inside the retained fused NV12 pipeline."""
from pathlib import Path
import hashlib
import json
import shutil
import statistics
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-lut-pipeline/fused');work.mkdir(exist_ok=True)
fusion=Path('/tmp/mjpeg-fused-chroma');base=fusion/'pgo';google=Path('/tmp/mjpeg-google-bench')
info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto']
config=json.loads((here/'experiment.json').read_text())
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if r.returncode:print(r.stderr,flush=True)
    r.check_returncode();return r
sources={'no-profile':Path('/tmp/mjpeg-stb-src/threshold-pair10'),
         **{kind:Path(config['clang-'+kind]['source']) for kind in ('unroll2','metadata')}}
binaries={'best':fusion/'pgo-fused'};isolation={}
for name,source in sources.items():
    build=work/name;build.mkdir(exist_ok=True);record={}
    for lib in ('libjpeg.a','libturbojpeg.a'):
        objdir=build/(lib+'-objects');objdir.mkdir(exist_ok=True);obj=objdir/'jdhuff.c.o'
        extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
        run(['clang','-O3','-DNDEBUG','-mtune=znver2','-mbmi2','-flto=thin','-I'+info['build'],*extra,
             '-c',source/'src/jdhuff.c','-o',obj])
        shutil.copyfile(base/lib,build/lib);run(['llvm-ar-18','r',build/lib,obj]);run(['llvm-ranlib-18',build/lib])
        members=run(['llvm-ar-18','t',base/lib]).stdout.splitlines()
        changed=[m for m in members if subprocess.check_output(['llvm-ar-18','p',str(base/lib),m])!=subprocess.check_output(['llvm-ar-18','p',str(build/lib),m])]
        assert changed==['jdhuff.c.o'],changed
        record[lib]=dict(changed_members=changed,sha256=hashlib.sha256((build/lib).read_bytes()).hexdigest())
    binary=build/'nv12'
    run(['clang++','-fuse-ld=gold',*info['flags'],fusion/'driver.o',fusion/'fusion.o',fusion/'exact.o',
         '/tmp/mjpeg-pgo-lto/heldout-frame.o',google/'_deps/googlebenchmark-build/src/libbenchmark.a',
         build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
    binaries[name]=binary;isolation[name]=record
(here/'fused-isolation.json').write_text(json.dumps(isolation,indent=2)+'\n')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))[30:];assert len(frames)==90
records=[];summary={};hashes={};names=list(binaries)
for mode in ('accurate','fast'):
    for trial in range(3):
        order=names[trial:]+names[:trial]
        if trial%2:order.reverse()
        for name in order:
            result=run(['taskset','-c','0',binaries[name],mode,'2','3',*frames]);assert not result.stderr,result.stderr
            row=json.loads(result.stdout)
            if mode in hashes:assert row['hash']==hashes[mode],(name,mode)
            else:hashes[mode]=row['hash']
            row.update(mode=mode,variant=name,trial=trial);records.append(row)
            (here/'fused-results.json').write_text(json.dumps(records,indent=2)+'\n')
        print(mode,trial,'complete',flush=True)
    summary[mode]={}
    for name in names:
        summary[mode][name]=statistics.mean(r['mean_ms'] for r in records if r['mode']==mode and r['variant']==name)
(here/'fused-summary.json').write_text(json.dumps(dict(cases=summary,hashes=hashes,
    method='Three rotated/reversed rounds, fused reduced chroma; 90 held-out preloaded frames, three passes after full warmup, CPU 0; best retains PGO, other entries rebuild only jdhuff without its stale profile but with ThinLTO'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
