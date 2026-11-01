#!/usr/bin/env python3
"""Full Clang builds, then matched archives to isolate entropy changes."""
from pathlib import Path
import collections
import difflib
import hashlib
import json
import re
import shutil
import subprocess

here = Path(__file__).resolve().parent
root = here.parents[3]
sources = {
    'clang-control': Path('/tmp/mjpeg-stb-src/threshold-pair10'),
    'clang-explicit': Path('/tmp/mjpeg-intrinsics-src/explicit-shifts'),
    'clang-bzhi': Path('/tmp/mjpeg-intrinsics-src/bzhi-mask'),
}
def run(cmd):
    return subprocess.run(list(map(str, cmd)), check=True, capture_output=True)
def sha(data):
    return hashlib.sha256(data).hexdigest()

evidence = {'compiler': run(['clang', '--version']).stdout.decode(), 'variants': {}}
config = {'control': {'source': '/tmp/mjpeg-bmi-current-src/bmi2',
                      'build': '/tmp/mjpeg-bmi-current-build/bmi2'}, 'variants': {}}
base = Path('/tmp/mjpeg-clang-build/clang-control')
for name, original in sources.items():
    tree = Path('/tmp/mjpeg-clang-src') / name
    build = Path('/tmp/mjpeg-clang-build') / name
    if tree.exists() or build.exists():
        raise FileExistsError(f'{tree} or {build}')
    shutil.copytree(original, tree)
    # The source clones may already specify -mbmi2; repetition is harmless.
    cmake = tree / 'CMakeLists.txt'
    cmake.write_text(cmake.read_text() + '\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mbmi2)\n')
    for label, cmd in [
        ('configure', ['cmake', '-S', tree, '-B', build, '-DCMAKE_C_COMPILER=clang',
                       '-DCMAKE_BUILD_TYPE=Release', '-DENABLE_SHARED=OFF', '-DBUILD=20261024']),
        ('build', ['cmake', '--build', build, '-j', '6']),
    ]:
        with (here / f'{name}-{label}.log').open('wb') as log:
            subprocess.run(list(map(str, cmd)), stdout=log, stderr=log, check=True)
    entry = {'archives': {}}
    for lib in ('libjpeg.a', 'libturbojpeg.a'):
        objdir = build / ('matched-' + lib)
        objdir.mkdir()
        obj = objdir / 'jdhuff.c.o'
        extra = [] if lib == 'libjpeg.a' else ['-DBMP_SUPPORTED', '-DPNG_SUPPORTED', '-DSPNG_STATIC', '-DPPM_SUPPORTED']
        run(['clang', '-I' + str(base), '-O3', '-DNDEBUG', *extra, '-mbmi2',
             '-c', tree / 'src/jdhuff.c', '-o', obj])
        # All members except jdhuff come from the same full Clang control.
        reference = base / lib
        members = run(['ar', 't', reference]).stdout.decode().splitlines()
        hashes = {m: sha(run(['ar', 'p', reference, m]).stdout) for m in members}
        if name != 'clang-control':
            shutil.copyfile(reference, build / lib)
        run(['ar', 'r', build / lib, obj])
        run(['ranlib', build / lib])
        assert members == run(['ar', 't', build / lib]).stdout.decode().splitlines()
        changed = [m for m in members if hashes[m] != sha(run(['ar', 'p', build / lib, m]).stdout)]
        assert set(changed) <= {'jdhuff.c.o'}, changed
        entry['archives'][lib] = {'changed_members': changed, 'sha256': sha((build / lib).read_bytes())}
    with (here / f'{name}-relink.log').open('wb') as log:
        subprocess.run(['cmake', '--build', str(build), '-j', '6'], stdout=log, stderr=log, check=True)
    for lib, record in entry['archives'].items():
        assert sha((build / lib).read_bytes()) == record['sha256']

    # Map instruction sites using a debug object with identical executable text.
    obj = build / 'matched-libjpeg.a/jdhuff.c.o'
    debug = build / 'audit.o'
    run(['clang', '-I' + str(base), '-O3', '-g', '-DNDEBUG', '-mbmi2',
         '-c', tree / 'src/jdhuff.c', '-o', debug])
    def text_bytes(file):
        dest = build / (file.name + '.text')
        run(['objcopy', '-O', 'binary', '--only-section=.text', file, dest])
        return dest.read_bytes()
    entry['debug_text_identical'] = text_bytes(obj) == text_bytes(debug)
    entry['text_sha256'] = sha(text_bytes(obj))
    assert entry['debug_text_identical'], name
    assembly = run(['objdump', '-d', '--no-show-raw-insn', '-Mintel', obj]).stdout.decode()
    (here / f'{name}.asm').write_text(assembly)
    (here / f'{name}-source.asm').write_bytes(run(['objdump', '-dlS', '--no-show-raw-insn', debug]).stdout)
    sites = []; counts = collections.defaultdict(collections.Counter); function = ''
    decode_counts = collections.Counter(); decode_instruction_sites = 0
    for line in assembly.splitlines():
        m = re.match(r'^[0-9a-f]+ <([^>]+)>:', line)
        if m: function = m[1]
        insn = re.match(r'^\s*[0-9a-f]+:\s+([a-z][a-z0-9]*)', line)
        if function.startswith('decode_mcu') and insn:
            decode_instruction_sites += 1
            if insn[1] in ('shrx', 'shlx', 'sarx', 'bzhi', 'bextr'):
                decode_counts[insn[1]] += 1
        m = re.match(r'^\s*([0-9a-f]+):\s+(shrx|shlx|sarx|bzhi|bextr|andn|lzcnt|tzcnt)\s+(.*)', line)
        if not m: continue
        address, op, operands = m.groups()
        stack = run(['addr2line', '-f', '-i', '-e', debug, '0x' + address]).stdout.decode().splitlines()
        category = 'fast MCU' if 'decode_mcu_fast' in stack else 'slow MCU' if 'decode_mcu_slow' in stack else function
        counts[category][op] += 1
        sites.append({'address': address, 'op': op, 'operands': operands, 'category': category, 'stack': stack})
    entry['counts_by_path'] = {k: dict(v) for k, v in counts.items()}
    entry['decode_mcu_static_sites'] = dict(decode_counts)
    entry['decode_mcu_all_instruction_sites'] = decode_instruction_sites
    entry['sites'] = sites
    evidence['variants'][name] = entry
    config['variants'][name] = {'source': str(tree), 'build': str(build)}
    (here / 'isolation.json').write_text(json.dumps(evidence, indent=2) + '\n')
    (here / 'experiment.json').write_text(json.dumps(config, indent=2) + '\n')
    print(name, entry['counts_by_path'], flush=True)

control = (here / 'clang-control.asm').read_text().splitlines(True)
for name in ('clang-explicit', 'clang-bzhi'):
    candidate = (here / (name + '.asm')).read_text().splitlines(True)
    (here / (name + '.diff')).write_text(''.join(difflib.unified_diff(control, candidate,
                                                    fromfile='clang-control.asm', tofile=name + '.asm')))
