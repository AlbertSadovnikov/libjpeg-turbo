#!/usr/bin/env python3
"""Matched compiler baselines plus PGO/LTO factorial, with held-out capture."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

here = Path(__file__).resolve().parent
root = here.parents[3]
work = Path('/tmp/mjpeg-pgo-lto')
source = Path('/tmp/mjpeg-stb-src/threshold-pair10')
google = Path('/tmp/mjpeg-google-bench')
parser = argparse.ArgumentParser()
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
if work.exists() and not args.resume: raise FileExistsError(work)
work.mkdir(exist_ok=True)
manifest_path = here / 'build-summary.json'
manifest = json.loads(manifest_path.read_text()) if args.resume and manifest_path.exists() else {}

def run(cmd, **kwargs):
    return subprocess.run(list(map(str, cmd)), check=True, capture_output=True, **kwargs)
def save():
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

frames = sorted((root / 'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
assert len(frames) == 120
training, heldout = frames[:30], frames[30:]
assert not set(training) & set(heldout)
manifest['split'] = dict(training=[str(p) for p in training], heldout=[str(p) for p in heldout],
                         training_modes=['accurate', 'fast'], entropy_frame=str(heldout[30]))
manifest.setdefault('builds', {})
manifest.setdefault('training', {})
save()

# The C++ measurement driver is compiled once, without PGO or LTO. Only codec
# objects participate in those optimizations. Both compilers link with gold.
common_flags = ['-O3', '-DNDEBUG', '-std=c++17', '-I/tmp/mjpeg-bmi-current-build/bmi2',
    '-I' + str(source / 'src'), '-I' + str(root / 'benchmarks'),
    '-I' + str(google / '_deps/googlebenchmark-src/include')]
for label, src in [('sequence', root / 'test/webcam/bmi-current/nv12_sequence.cc')]:
    obj = work / (label + '.o')
    if not obj.exists(): run(['g++', *common_flags, '-c', src, '-o', obj])
embed = work / 'heldout-frame.cc'
if not embed.exists():
    run(['cmake', '-DINPUT=' + str(heldout[30]), '-DOUTPUT=' + str(embed),
         '-P', root / 'benchmarks/embed_frame.cmake'])
if not (work / 'heldout-frame.o').exists():
    run(['g++', '-O3', '-I' + str(root / 'benchmarks'), '-c', embed, '-o', work / 'heldout-frame.o'])
manifest['driver'] = {name: sha(work / (name + '.o')) for name in ('sequence', 'heldout-frame')}

def link(compiler, build, mode, out, extra=(), train=False):
    cxx = 'g++' if compiler == 'gcc' else 'clang++'
    embedded = google / 'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o' if train else work / 'heldout-frame.o'
    cmd = [cxx, '-fuse-ld=gold', *extra, work / (mode + '.o'), embedded]
    if mode == 'sequence': cmd += [google / '_deps/googlebenchmark-build/src/libbenchmark.a']
    cmd += [build / 'libjpeg.a']
    if mode == 'sequence': cmd += [build / 'libturbojpeg.a']
    run([*cmd, '-lm', '-lpthread', '-lrt', '-o', out])

def build_codec(compiler, name, flags, training_build=False):
    tree = work / (compiler + '-source')
    if not tree.exists():
        shutil.copytree(source, tree)
        cmake = tree / 'CMakeLists.txt'
        cmake.write_text(cmake.read_text() + '\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n')
    build = work / name
    commands = [('configure', ['cmake', '-S', tree, '-B', build,
        '-DCMAKE_C_COMPILER=' + compiler, '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_FLAGS_RELEASE=' + ' '.join(flags), '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=gold',
        '-DCMAKE_AR=' + ('/usr/bin/gcc-ar' if compiler == 'gcc' else '/usr/bin/llvm-ar-18'),
        '-DCMAKE_RANLIB=' + ('/usr/bin/gcc-ranlib' if compiler == 'gcc' else '/usr/bin/llvm-ranlib-18'),
        '-DENABLE_SHARED=OFF', '-DBUILD=20261024']),
        ('build', ['cmake', '--build', build, '-j', '6'] +
                   ['--target', 'jpeg-static', 'turbojpeg-static'])]
    for label, cmd in commands:
        with (here / (name + '-' + label + '.log')).open('wb') as log:
            subprocess.run(list(map(str, cmd)), check=True, stdout=log, stderr=log)
    return tree, build

for compiler in ('gcc', 'clang'):
    base_flags = ['-O3', '-DNDEBUG'] + (['-mtune=znver2'] if compiler == 'clang' else [])
    for pgo, lto in [(False, False), (False, True), (True, False), (True, True)]:
        tier = 'pgo-lto' if pgo and lto else 'pgo' if pgo else 'lto' if lto else 'base'
        name = compiler + '-' + tier
        if manifest['builds'].get(name, {}).get('complete'):
            print(name, 'already complete', flush=True); continue
        flags = base_flags + (['-flto' if compiler == 'gcc' else '-flto=thin'] if lto else [])
        profile_flags = []
        if pgo:
            profile = work / (name + '-profile'); profile.mkdir(exist_ok=True)
            gen_name = name + '-generate'; gen_build = work / gen_name
            if compiler == 'gcc':
                gen_flags = ['-fprofile-generate=' + str(profile), '-fprofile-prefix-path=' + str(gen_build)]
                profile_flags = ['-fprofile-use=' + str(profile), '-fprofile-prefix-path=' + str(work / name)]
            else:
                gen_flags = ['-fprofile-instr-generate=' + str(profile / 'raw-%m-%p.profraw')]
                profile_flags = ['-fprofile-instr-use=' + str(profile / 'merged.profdata')]
            if not manifest['training'].get(name, {}).get('complete'):
                _, generated = build_codec(compiler, gen_name, flags + gen_flags, True)
                binary = work / (gen_name + '-sequence')
                link(compiler, generated, 'sequence', binary, flags + gen_flags, True)
                records = []
                for mode in ('accurate', 'fast'):
                    result = run(['taskset', '-c', '0', binary, mode, '1', *training], text=True)
                    assert not result.stderr, result.stderr
                    records.append(json.loads(result.stdout))
                if compiler == 'clang':
                    raw = sorted(profile.glob('*.profraw')); assert raw
                    run(['llvm-profdata-18', 'merge', '-o', profile / 'merged.profdata', *raw])
                else:
                    assert list(profile.glob('*jdhuff*.gcda')), list(profile.iterdir())
                manifest['training'][name] = dict(complete=True, flags=flags + gen_flags, records=records,
                    profile_files={p.name: sha(p) for p in sorted(profile.iterdir()) if p.is_file()})
                save(); print(name, 'trained', flush=True)
        tree, build = build_codec(compiler, name, flags + profile_flags)
        # Profile-load diagnostics are retained. Missing cold/unused TU profiles
        # are distinct from missing/mismatched hot entropy profiles.
        log = (here / (name + '-build.log')).read_text()
        diagnostics = [line for line in log.splitlines() if 'warning:' in line and
                       ('profile' in line.lower() or 'coverage' in line.lower())]
        record = dict(compiler=compiler, pgo=pgo, lto=lto, flags=flags + profile_flags,
                      source=str(tree), build=str(build), profile_diagnostics=diagnostics)
        for mode in ('sequence',):
            binary = work / (name + '-' + mode)
            link(compiler, build, mode, binary, flags + profile_flags)
            record[mode + '_binary'] = str(binary)
        record['validation_scope'] = 'JPEG to NV12; output hashes checked by run.py'
        record['archives'] = {lib: sha(build / lib) for lib in ('libjpeg.a', 'libturbojpeg.a')}
        record['complete'] = True
        manifest['builds'][name] = record; save()
        print(name, 'codec and NV12 driver ready', flush=True)
