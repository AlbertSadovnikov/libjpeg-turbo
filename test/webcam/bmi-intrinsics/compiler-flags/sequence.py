#!/usr/bin/env python3
"""Bracket promising Clang flag sets against the current GCC winner."""
from pathlib import Path
import json
import statistics
import subprocess

here = Path(__file__).resolve().parent
root = here.parents[3]
config = json.loads((here / 'experiment.json').read_text())
cases = {'gcc-control': config['control'], **{n: config['variants'][n]
         for n in ('clang-tune', 'clang-arch-receive')}}
base = Path('/tmp/mjpeg-google-bench')
binaries = {}
for name, info in cases.items():
    build = Path(info['build']); binary = Path('/tmp') / ('flags-sequence-' + name)
    subprocess.run(['c++', '-O3', '-DNDEBUG', '-std=c++17', '-I' + str(build),
        '-I' + str(Path(info['source']) / 'src'), '-I' + str(root / 'benchmarks'),
        '-I' + str(base / '_deps/googlebenchmark-src/include'),
        str(root / 'test/webcam/bmi-current/nv12_sequence.cc'),
        str(base / 'benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o'),
        str(base / '_deps/googlebenchmark-build/src/libbenchmark.a'),
        str(build / 'libjpeg.a'), str(build / 'libturbojpeg.a'),
        '-lm', '-lpthread', '-lrt', '-o', str(binary)], check=True)
    binaries[name] = binary
frames = sorted((root / 'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
assert len(frames) == 120
records = []; paired = []; summary = {}
for mode in ('accurate', 'fast'):
    for trial in range(3):
        order = ['clang-tune', 'clang-arch-receive']
        if trial % 2: order.reverse()
        for candidate in order:
            rows = []
            for position, name in enumerate(('gcc-control', candidate, 'gcc-control')):
                result = subprocess.run(['taskset', '-c', '0', str(binaries[name]), mode, '3', *map(str, frames)],
                                        check=True, capture_output=True, text=True)
                assert not result.stderr, result.stderr
                row = json.loads(result.stdout)
                row.update(mode=mode, trial=trial, position=position, variant=name, candidate=candidate)
                rows.append(row); records.append(row)
            assert len({r['hash'] for r in rows}) == 1
            c = statistics.mean([rows[0]['mean_ms'], rows[2]['mean_ms']]); v = rows[1]['mean_ms']
            paired.append(dict(mode=mode, trial=trial, variant=candidate, control_ms=c,
                               candidate_ms=v, time_change_percent=100 * (v / c - 1)))
            print(paired[-1], flush=True)
    summary[mode] = {}
    for candidate in ('clang-tune', 'clang-arch-receive'):
        rows = [r for r in paired if r['mode'] == mode and r['variant'] == candidate]
        c = statistics.mean(r['control_ms'] for r in rows); v = statistics.mean(r['candidate_ms'] for r in rows)
        summary[mode][candidate] = dict(control_ms=c, candidate_ms=v, time_change_percent=100 * (v / c - 1))
    (here / 'sequence-summary.json').write_text(json.dumps(dict(cases=summary, paired=paired, records=records,
        method='Three GCC-candidate-GCC brackets per candidate and IDCT mode, candidate order rotated; 120 preloaded frames, three measured passes after full warmup; CPU 0'), indent=2) + '\n')
print(json.dumps(summary, indent=2))
