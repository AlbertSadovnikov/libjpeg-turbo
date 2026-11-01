#!/usr/bin/env python3
"""Build receive-only and receive+pair assembly against GCC/Clang controls."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import shutil
import subprocess

here = Path(__file__).resolve().parent
source = Path('/tmp/mjpeg-stb-src/threshold-pair10')
original = (source / 'src/jdhuff.c').read_text()
kernels = (here / 'kernels.h').read_text()
def run(cmd):
    return subprocess.run(list(map(str, cmd)), check=True, capture_output=True)
def sha(data):
    return hashlib.sha256(data).hexdigest()

config = {'control': {'source': '/tmp/mjpeg-bmi-current-src/bmi2',
                      'build': '/tmp/mjpeg-bmi-current-build/bmi2'}, 'variants': {
    'clang-control': {'source': '/tmp/mjpeg-clang-src/clang-control',
                      'build': '/tmp/mjpeg-clang-build/clang-control'}}}
evidence = {}
for compiler in ('gcc', 'clang'):
    control = config['control'] if compiler == 'gcc' else config['variants']['clang-control']
    base = Path(control['build'])
    for kind in ('receive', 'pair'):
        name = compiler + '-' + kind
        tree = Path('/tmp/mjpeg-assembly-src') / name
        build = Path('/tmp/mjpeg-assembly-build') / name
        if tree.exists() or build.exists(): raise FileExistsError(name)
        shutil.copytree(source, tree)
        c = original.replace('} multi_entry;', '} multi_entry;\n' +
                             ('#define MJPEG_ASM_PAIR 1\n' if kind == 'pair' else '') + kernels, 1)
        start = c.index('LOCAL(boolean)\ndecode_mcu_fast')
        before, fast = c[:start], c[start:]
        # 'register' forbids taking a local's address, even when an inline
        # helper eliminates that address entirely. Its placement is advisory.
        fast = fast.replace('  BITREAD_STATE_VARS;',
                            '  bit_buf_type get_buffer; int bits_left; bitread_working_state br_state;', 1)
        fast = fast.replace('    register int s, k, r, l;', '    int s, k, r, l;', 1)
        old = 'r = GET_BITS(s);\n      s = HUFF_EXTEND(r, s);'
        assert fast.count(old) == 1
        fast = fast.replace(old, 's = mjpeg_receive_asm(get_buffer, &bits_left, s);')
        old = 'r = GET_BITS(s);\n          s = HUFF_EXTEND(r, s);'
        assert fast.count(old) == 1
        fast = fast.replace(old, 's = mjpeg_receive_asm(get_buffer, &bits_left, s);')
        if kind == 'pair':
            begin = fast.index('        e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];')
            end = fast.index('        HUFF_DECODE_FAST(s, l, actbl);', begin)
            fast = fast[:begin] + '''        if (mjpeg_pair_asm(get_buffer, &bits_left, &k, *block, fused))
          continue;
''' + fast[end:]
            fast = fast.replace('        multi_entry e;\n', '', 1)
        c = before + fast
        (tree / 'src/jdhuff.c').write_text(c)
        (here / (name + '.patch')).write_text(''.join(difflib.unified_diff(
            original.splitlines(True), c.splitlines(True), fromfile='a/src/jdhuff.c', tofile='b/src/jdhuff.c')))
        cmake = tree / 'CMakeLists.txt'
        cmake.write_text(cmake.read_text() + '\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n')
        for label, cmd in [('configure', ['cmake', '-S', tree, '-B', build, '-DCMAKE_C_COMPILER=' + compiler,
                                         '-DCMAKE_BUILD_TYPE=Release', '-DENABLE_SHARED=OFF', '-DBUILD=20261024']),
                           ('build', ['cmake', '--build', build, '-j', '6'])]:
            with (here / (name + '-' + label + '.log')).open('wb') as log:
                subprocess.run(list(map(str, cmd)), stdout=log, stderr=log, check=True)
        record = {'archives': {}}
        for lib in ('libjpeg.a', 'libturbojpeg.a'):
            objdir = build / ('matched-' + lib); objdir.mkdir()
            obj = objdir / 'jdhuff.c.o'
            extra = [] if lib == 'libjpeg.a' else ['-DBMP_SUPPORTED', '-DPNG_SUPPORTED', '-DSPNG_STATIC', '-DPPM_SUPPORTED']
            run([compiler, '-O3', '-DNDEBUG', '-mbmi2', '-I' + str(base), *extra,
                 '-c', tree / 'src/jdhuff.c', '-o', obj])
            members = run(['ar', 't', base / lib]).stdout.decode().splitlines()
            hashes = {m: sha(run(['ar', 'p', base / lib, m]).stdout) for m in members}
            shutil.copyfile(base / lib, build / lib)
            run(['ar', 'r', build / lib, obj]); run(['ranlib', build / lib])
            assert members == run(['ar', 't', build / lib]).stdout.decode().splitlines()
            changed = [m for m in members if hashes[m] != sha(run(['ar', 'p', build / lib, m]).stdout)]
            assert changed == ['jdhuff.c.o'], changed
            record['archives'][lib] = {'changed_members': changed, 'sha256': sha((build / lib).read_bytes())}
        with (here / (name + '-relink.log')).open('wb') as log:
            subprocess.run(['cmake', '--build', str(build), '-j', '6'], stdout=log, stderr=log, check=True)
        for lib, item in record['archives'].items():
            assert sha((build / lib).read_bytes()) == item['sha256']
        obj = build / 'matched-libjpeg.a/jdhuff.c.o'
        assembly = run(['objdump', '-d', '--no-show-raw-insn', '-Mintel', obj]).stdout.decode()
        (here / (name + '.asm')).write_text(assembly)
        ctrl = run(['objdump', '-d', '--no-show-raw-insn', '-Mintel',
                    base / 'matched-libjpeg.a/jdhuff.c.o']).stdout.decode()
        (here / (name + '.diff')).write_text(''.join(difflib.unified_diff(
            ctrl.splitlines(True), assembly.splitlines(True), fromfile=compiler + '-control', tofile=name)))
        evidence[name] = record
        config['variants'][name] = {'source': str(tree), 'build': str(build)}
        (here / 'isolation.json').write_text(json.dumps(evidence, indent=2) + '\n')
        (here / 'experiment.json').write_text(json.dumps(config, indent=2) + '\n')
        print(name, 'built', flush=True)
