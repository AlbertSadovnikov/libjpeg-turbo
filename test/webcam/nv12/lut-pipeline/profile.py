#!/usr/bin/env python3
"""Fresh fused-path PGO for a fair original-versus-minimal-lookahead test."""
from pathlib import Path
import hashlib
import argparse
import json
import shutil
import statistics
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3]
work=Path('/tmp/mjpeg-lut-profile');work.mkdir(exist_ok=True)
fusion=Path('/tmp/mjpeg-fused-chroma');google=Path('/tmp/mjpeg-google-bench')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
training=frames[:30];heldout=frames[30:]
manifest_path=here/'profile-build-summary.json'
manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
parser=argparse.ArgumentParser();parser.add_argument('--unroll-control',action='store_true');args=parser.parse_args()
control_name='unroll2' if args.unroll_control else 'original'
prefix='profile-unroll-' if args.unroll_control else 'profile-'
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if r.returncode:print(r.stderr,flush=True)
    r.check_returncode();return r
def codec(name,tree,flags):
    build=work/name
    for phase,cmd in [('configure',['cmake','-S',tree,'-B',build,'-DCMAKE_C_COMPILER=clang',
        '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS_RELEASE='+' '.join(flags),
        '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=gold','-DCMAKE_AR=/usr/bin/llvm-ar-18',
        '-DCMAKE_RANLIB=/usr/bin/llvm-ranlib-18','-DENABLE_SHARED=OFF','-DWITH_BENCHMARKS=OFF','-DWITH_TESTS=OFF','-DBUILD=20261024']),
        ('build',['cmake','--build',build,'--target','jpeg-static','turbojpeg-static','-j','6'])]:
        with (here/(name+'-'+phase+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),check=True,stdout=log,stderr=log)
    return build
def link(build,flags,out):
    run(['clang++','-fuse-ld=gold',*flags,fusion/'driver.o',fusion/'fusion.o',fusion/'exact.o',
        '/tmp/mjpeg-pgo-lto/heldout-frame.o',google/'_deps/googlebenchmark-build/src/libbenchmark.a',
        build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',out])

baseline_flags=['-O3','-DNDEBUG','-mtune=znver2','-flto=thin']
for name in (control_name,'metadata'):
    if manifest.get(name,{}).get('complete'):continue
    tree=work/(name+'-source')
    if not tree.exists():
        shutil.copytree(fusion/'source',tree)
        if name!='original':shutil.copyfile('/tmp/mjpeg-lut-pipeline/clang-'+name+'-source/src/jdhuff.c',tree/'src/jdhuff.c')
        cmake=tree/'CMakeLists.txt';cmake.write_text(cmake.read_text()+'\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n')
    profile=work/(name+'-profile');profile.mkdir(exist_ok=True)
    gen_flags=baseline_flags+['-fprofile-instr-generate='+str(profile/'raw-%m-%p.profraw')]
    generated=codec(name+'-generate',tree,gen_flags);binary=work/(name+'-train');link(generated,gen_flags,binary)
    for mode in ('accurate','fast'):
        r=run(['taskset','-c','0',binary,mode,'2','1',*training]);assert not r.stderr,r.stderr
    raw=list(profile.glob('*.profraw'));assert raw
    run(['llvm-profdata-18','merge','-o',profile/'merged.profdata',*raw])
    flags=baseline_flags+['-fprofile-instr-use='+str(profile/'merged.profdata')]
    build=codec(name,tree,flags);binary=work/(name+'-nv12');link(build,flags,binary)
    r=run(['taskset','-c','0',binary,'validate',*frames]);assert not r.stderr,r.stderr
    validation=json.loads(r.stdout)
    expected=json.loads((root/'test/webcam/nv12/fused-chroma/pgo-validation.json').read_text())
    assert validation==expected,(name,'NV12 validation changed')
    manifest[name]=dict(complete=True,source=str(tree),build=str(build),binary=str(binary),flags=flags,
        profile_sha256=hashlib.sha256((profile/'merged.profdata').read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),validation=validation)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n');print(name,'trained and validated',flush=True)

fixture_validation={}
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
for mode in ('accurate','fast'):
    fixture_validation[mode]={}
    for fixture in fixtures:
        outputs=[]
        for name in (control_name,'metadata'):
            r=run(['taskset','-c','0',manifest[name]['binary'],mode,'2','1',fixture,fixture]);assert not r.stderr,r.stderr
            outputs.append(json.loads(r.stdout)['hash'])
        assert outputs[0]==outputs[1],(mode,fixture)
        fixture_validation[mode][fixture.stem]=outputs[0]
(here/(prefix+'fixture-validation.json')).write_text(json.dumps(fixture_validation,indent=2)+'\n')
records=[];paired=[];summary={}
for mode in ('accurate','fast'):
    for trial in range(3):
        rows=[]
        for position,name in enumerate((control_name,'metadata',control_name)):
            r=run(['taskset','-c','0',manifest[name]['binary'],mode,'2','3',*heldout]);assert not r.stderr,r.stderr
            row=json.loads(r.stdout);row.update(mode=mode,variant=name,trial=trial,position=position);records.append(row);rows.append(row)
        assert len({r['hash'] for r in rows})==1
        control=statistics.mean([rows[0]['mean_ms'],rows[2]['mean_ms']]);candidate=rows[1]['mean_ms']
        paired.append(dict(mode=mode,trial=trial,original_ms=control,metadata_ms=candidate,time_change_percent=100*(candidate/control-1)))
        (here/(prefix+'results.json')).write_text(json.dumps(dict(control=control_name,paired=paired,records=records),indent=2)+'\n');print(paired[-1],flush=True)
    rows=[r for r in paired if r['mode']==mode];a=statistics.mean(r['original_ms'] for r in rows);b=statistics.mean(r['metadata_ms'] for r in rows)
    summary[mode]=dict(original_ms=a,metadata_ms=b,time_change_percent=100*(b/a-1))
    (here/(prefix+'summary.json')).write_text(json.dumps(dict(control=control_name,cases=summary,paired=paired,
        method='Independent front-end PGO+ThinLTO training for each source on 30 frames, both IDCT modes with fused reduced chroma; three '+control_name+'-metadata-'+control_name+' brackets on 90 held-out preloaded frames, three passes after warmup, CPU 0; identical NV12 output'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
