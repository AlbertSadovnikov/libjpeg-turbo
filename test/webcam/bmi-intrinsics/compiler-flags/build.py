#!/usr/bin/env python3
"""Full-codec compiler flag comparison, with unchanged SIMD assembly sources."""
from pathlib import Path
import json
import shutil
import subprocess

here = Path(__file__).resolve().parent
c_source = Path('/tmp/mjpeg-stb-src/threshold-pair10')
asm_source = Path('/tmp/mjpeg-assembly-src/clang-receive')
cases = {
    'clang-o2': ('clang', c_source, '-O2 -DNDEBUG'),
    'clang-tune': ('clang', c_source, '-O3 -DNDEBUG -mtune=znver2'),
    'clang-tune-receive': ('clang', asm_source, '-O3 -DNDEBUG -mtune=znver2'),
    'clang-arch-receive': ('clang', asm_source, '-O3 -DNDEBUG -march=znver2'),
    'gcc-tune': ('gcc', c_source, '-O3 -DNDEBUG -mtune=znver2'),
}
config = {'control': {'source': '/tmp/mjpeg-bmi-current-src/bmi2',
                      'build': '/tmp/mjpeg-bmi-current-build/bmi2'}, 'variants': {
    'clang-control': {'source': '/tmp/mjpeg-clang-src/clang-control',
                      'build': '/tmp/mjpeg-clang-build/clang-control'},
    'clang-receive': {'source': str(asm_source),
                      'build': '/tmp/mjpeg-assembly-build/clang-receive'}}}
metadata = {}
for name, (compiler, source, flags) in cases.items():
    tree = Path('/tmp/mjpeg-flags-src') / name
    build = Path('/tmp/mjpeg-flags-build') / name
    if tree.exists() or build.exists(): raise FileExistsError(name)
    shutil.copytree(source, tree)
    cmake = tree / 'CMakeLists.txt'
    cmake.write_text(cmake.read_text() + '\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n')
    for label, cmd in [('configure', ['cmake', '-S', tree, '-B', build,
        '-DCMAKE_C_COMPILER=' + compiler, '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_FLAGS_RELEASE=' + flags, '-DENABLE_SHARED=OFF', '-DBUILD=20261024']),
        ('build', ['cmake', '--build', build, '-j', '6'])]:
        with (here / (name + '-' + label + '.log')).open('wb') as log:
            subprocess.run(list(map(str, cmd)), check=True, stdout=log, stderr=log)
    metadata[name] = dict(compiler=compiler, flags=flags, source=str(source),
                         scope='All codec C files; -mbmi2 additionally on jdhuff.c')
    config['variants'][name] = dict(source=str(tree), build=str(build))
    (here / 'experiment.json').write_text(json.dumps(config, indent=2) + '\n')
    (here / 'build-flags.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(name, 'built', flush=True)
