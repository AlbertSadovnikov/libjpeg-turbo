#!/usr/bin/env python3
"""Confirm Clang receive assembly using preloaded full capture, bracketed."""
from pathlib import Path
import json
import statistics
import subprocess
import argparse

here = Path(__file__).resolve().parent
root = here.parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('--best', action='store_true', help='Compare best GCC and Clang candidates directly')
args = parser.parse_args()
experiment = json.loads((here / 'experiment.json').read_text())
config = experiment['variants']
control_name = 'gcc-best' if args.best else 'clang-control'
if args.best:
    config['gcc-best'] = experiment['control']
candidate_name = 'clang-receive'
trials = 4 if args.best else 3
output = 'best-sequence-summary.json' if args.best else 'sequence-summary.json'
base = Path('/tmp/mjpeg-google-bench')
binaries = {}
for name in (control_name, candidate_name):
    info = config[name]; build = Path(info['build'])
    binary = Path('/tmp') / ('assembly-sequence-' + name)
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
    for trial in range(trials):
        rows = []
        order = (control_name, candidate_name, control_name)
        if args.best and trial % 2:
            order = (candidate_name, control_name, candidate_name)
        for position, name in enumerate(order):
            result = subprocess.run(['taskset', '-c', '0', str(binaries[name]), mode, '3', *map(str, frames)],
                                    check=True, capture_output=True, text=True)
            assert not result.stderr, result.stderr
            row = json.loads(result.stdout)
            row.update(mode=mode, trial=trial, position=position, variant=name)
            rows.append(row); records.append(row)
        assert len({r['hash'] for r in rows}) == 1
        control = statistics.mean(r['mean_ms'] for r in rows if r['variant'] == control_name)
        candidate = statistics.mean(r['mean_ms'] for r in rows if r['variant'] == candidate_name)
        paired.append(dict(mode=mode, trial=trial, control_ms=control, candidate_ms=candidate,
                           time_change_percent=100 * (candidate / control - 1)))
        print(paired[-1], flush=True)
    rows = [r for r in paired if r['mode'] == mode]
    c = statistics.mean(r['control_ms'] for r in rows)
    v = statistics.mean(r['candidate_ms'] for r in rows)
    summary[mode] = dict(control_ms=c, candidate_ms=v, time_change_percent=100 * (v / c - 1))
    (here / output).write_text(json.dumps(dict(cases=summary, paired=paired,
        records=records, control=control_name, candidate=candidate_name,
        method=f'{trials} brackets per IDCT mode; ' + ('alternating GCC-Clang-GCC and Clang-GCC-Clang; ' if args.best else 'control-candidate-control; ') +
        '120 preloaded frames, three passes after full warmup, CPU 0'), indent=2) + '\n')
print(json.dumps(summary, indent=2))
