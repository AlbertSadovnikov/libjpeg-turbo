#!/usr/bin/env python3
"""Validate builds, then time only held-out frames using common driver objects."""
from pathlib import Path
import hashlib
import json
import statistics
import subprocess

here = Path(__file__).resolve().parent
root = here.parents[3]
work = Path('/tmp/mjpeg-pgo-lto')
google = Path('/tmp/mjpeg-google-bench')
manifest = json.loads((here / 'build-summary.json').read_text())
names = [compiler + '-' + tier for compiler in ('gcc', 'clang') for tier in ('base', 'lto', 'pgo', 'pgo-lto')]
builds = manifest['builds']
assert all(builds.get(n, {}).get('complete') for n in names)
training = [Path(p) for p in manifest['split']['training']]
heldout = [Path(p) for p in manifest['split']['heldout']]
assert len(training) == 30 and len(heldout) == 90 and not set(training) & set(heldout)

def run(cmd, **kwargs):
    return subprocess.run(list(map(str, cmd)), check=True, capture_output=True, **kwargs)

# Re-link with the complete compile/link flag set, including profile use for
# GCC LTO's backend. The measurement driver objects themselves are ordinary
# native GCC objects and do not participate in LTO or PGO.
def link(name, mode, extra_objects=()):
    info = builds[name]; build = Path(info['build'])
    compiler = 'g++' if info['compiler'] == 'gcc' else 'clang++'
    binary = work / (name + '-' + mode)
    cmd = [compiler, '-fuse-ld=gold', *info['flags'], work / (mode + '.o'), *extra_objects]
    if mode == 'sequence': cmd += [google / '_deps/googlebenchmark-build/src/libbenchmark.a']
    cmd += [build / 'libjpeg.a']
    if mode == 'sequence': cmd += [build / 'libturbojpeg.a']
    run([*cmd, '-lm', '-lpthread', '-lrt', '-o', binary])
    return binary

validation = {}; binaries = {}
for name in names:
    binary = link(name, 'sequence', [work / 'heldout-frame.o'])
    binaries[name] = {'sequence': binary}
    validation[name] = dict(scope='JPEG to NV12',
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())

records = []; hashes = {}
def keep(row):
    mode = row['mode']
    if mode in hashes: assert hashes[mode] == row['hash'], (mode, row)
    else: hashes[mode] = row['hash']
    records.append(row)
    (here / 'results.json').write_text(json.dumps(records, indent=2) + '\n')
def order(trial):
    result = names[trial:] + names[:trial]
    return list(reversed(result)) if trial % 2 else result

# Matrix screening on the complete held-out sequence. Timers exclude loading,
# allocation and hashing. Each process has a full warmup pass before 3 passes.
for mode in ('accurate', 'fast'):
    for trial in range(3):
        for name in order(trial):
            result = run(['taskset', '-c', '0', binaries[name]['sequence'], mode, '3', *heldout], text=True)
            assert not result.stderr, result.stderr
            row = json.loads(result.stdout); row.update(kind='sequence', mode=mode, trial=trial, variant=name)
            keep(row)
        print('heldout', mode, trial, 'complete', flush=True)

summary = {}
for name in names:
    current = [r for r in records if r['variant'] == name]
    summary[name] = {mode + '_ms': statistics.mean(r['mean_ms'] for r in current if r['kind'] == 'sequence' and r['mode'] == mode)
                     for mode in ('accurate', 'fast')}
(here / 'summary.json').write_text(json.dumps(dict(cases=summary, validation=validation,
    method='Three rotated/reversed rounds; JPEG to NV12 on 90 held-out preloaded frames, 3 passes after full warmup; CPU 0; matching output hashes'), indent=2) + '\n')
print(json.dumps(summary, indent=2))
