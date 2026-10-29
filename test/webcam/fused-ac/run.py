#!/usr/bin/env python3
"""Validate and benchmark the prebuilt persistent combined-AC experiments."""
import argparse
import csv
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import statistics
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--trials', type=int, default=5)
    parser.add_argument('--passes', type=int, default=3)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    if args.trials < 1 or args.passes < 1:
        parser.error('positive trials and passes required')
    here = Path(__file__).resolve().parent
    webcam = here.parent
    repo = webcam.parents[1]
    frames = sorted(args.capture.resolve().glob('frame_*.jpg'))
    if not frames:
        parser.error('no captured JPEG frames')
    output = here / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir()
    spec = importlib.util.spec_from_file_location('sequence_benchmark', webcam/'benchmark.py')
    stats = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stats)
    names = ['release', 'fused10', 'fused11', 'fused12']
    binaries = {}
    commands = []
    for name in names:
        build = Path('/tmp/mjpeg-'+name)
        src = repo/'src' if name == 'release' else Path('/tmp/mjpeg-fused-src/src')
        binaries[name] = {}
        for tool in ('benchmark', 'verify'):
            binary = output/(tool+'-'+name)
            command = ['cc', '-O3', '-Wall', '-Wextra', '-I'+str(build), '-I'+str(src),
                       str(webcam/(tool+'.c')), str(build/'libturbojpeg.a'), '-lm', '-o', str(binary)]
            subprocess.run(command, check=True)
            commands.append(command)
            binaries[name][tool] = binary

    # First compare complete output bytes for every camera frame and variant.
    for frame in frames:
        baseline = subprocess.run(['/tmp/mjpeg-release/djpeg-static', str(frame)], capture_output=True, check=True)
        assert not baseline.stderr, frame
        for name in names[1:]:
            candidate = subprocess.run([f'/tmp/mjpeg-{name}/djpeg-static', str(frame)], capture_output=True, check=True)
            assert not candidate.stderr and candidate.stdout == baseline.stdout, (frame, name)
    print('All camera frames match pixel-for-pixel for all three variants.', flush=True)

    # Reuse a decoder across complete sequences and encoding/table changes.
    mixed = [frames[0], Path('/tmp/mjpeg-sample.jpg'), Path('/tmp/mjpeg-opt-huff.jpg'),
             Path('/tmp/mjpeg-sample.jpg'), frames[60],
             Path('/tmp/mjpeg-fused10/testout-static_420_islow_prog.jpg'),
             Path('/tmp/mjpeg-restart.jpg'), frames[-1], repo/'testimages/testorig.jpg', frames[0]]
    validation = {}
    for mode in ('bgr', 'gray', 'half', 'fast-upsample', 'fast-idct'):
        sequence = frames + mixed if mode == 'bgr' else mixed
        reference = subprocess.run([str(binaries['release']['verify']), mode, *map(str, sequence)],
                                   capture_output=True, check=True)
        assert not reference.stderr
        for name in names[1:]:
            env = dict(os.environ, MJPEG_FUSED_TRACE='1')
            candidate = subprocess.run([str(binaries[name]['verify']), mode, *map(str, sequence)],
                                       capture_output=True, check=True, env=env)
            assert candidate.stdout == reference.stdout, (mode, name)
            (output/f'cache-trace-{name}-{mode}.txt').write_bytes(candidate.stderr)
            validation[f'{name}-{mode}'] = 'persistent sequence pixel hashes match baseline'
    # The camera-only sequence must build each of its two AC tables once.
    for name in names[1:]:
        candidate = subprocess.run([str(binaries[name]['verify']), 'bgr', *map(str, frames)],
                                   capture_output=True, check=True, env=dict(os.environ, MJPEG_FUSED_TRACE='1'))
        assert len(candidate.stderr.splitlines()) == 2, candidate.stderr
        validation[f'{name}-camera-cache-builds'] = 2
    (output/'validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    print('Persistent cache reuse and table-change checks passed.', flush=True)

    measurements = {name: [] for name in names}
    trial_means = {name: [] for name in names}
    env = dict(os.environ)
    env.pop('MJPEG_FUSED_TRACE', None)
    env.pop('JSIMD_FORCENONE', None)
    for trial in range(args.trials):
        order = names[trial % len(names):] + names[:trial % len(names)]
        if trial % 2:
            order.reverse()
        for name in order:
            command = ['taskset', '-c', str(args.cpu), str(binaries[name]['benchmark']),
                       'bgr', str(args.passes), *map(str, frames)]
            run = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
            assert not run.stderr, run.stderr
            (output/f'{name}-{trial}.csv').write_text(run.stdout)
            rows = [{k: float(v) for k,v in row.items()} for row in csv.DictReader(io.StringIO(run.stdout))]
            assert len(rows) == len(frames) * args.passes
            measurements[name].extend(rows)
            mean = statistics.mean(r['total_ms'] for r in rows)
            trial_means[name].append(mean)
            commands.append(command)
            print(f'{name} trial {trial}: {mean:.4f} ms/frame', flush=True)
    summary = {'capture': str(args.capture.resolve()), 'cpu': args.cpu,
               'frames': len(frames), 'trials': args.trials, 'passes': args.passes,
               'method': 'Preloaded entire sequence; reused decoder/output; one full warmup pass per process; same CPU; rotated variant order; no instrumentation.',
               'validation': validation, 'cases': {}}
    for name, rows in measurements.items():
        summary['cases'][name] = {'total_ms': stats.describe([r['total_ms'] for r in rows]),
                                  'setup_ms': stats.describe([r['setup_ms'] for r in rows]),
                                  'trial_means_ms': trial_means[name]}
    baseline = summary['cases']['release']['total_ms']['mean']
    lines = ['# Persistent combined AC lookup experiment', '', summary['method'], '',
             f'{len(frames)} frames, {args.trials} trials x {args.passes} measured passes, CPU {args.cpu}.', '',
             '| Variant | Mean ms | Median ms | p95 ms | Time reduction |',
             '|---|---:|---:|---:|---:|']
    for name in names:
        case = summary['cases'][name]
        case['time_reduction_percent'] = 100*(1-case['total_ms']['mean']/baseline)
        case['paired_trial_reduction_percent'] = [100*(1-a/b) for a,b in zip(trial_means[name],trial_means['release'])]
        t = case['total_ms']
        lines.append(f'| {name} | {t["mean"]:.4f} | {t["median"]:.4f} | {t["p95"]:.4f} | {case["time_reduction_percent"]:.2f}% |')
    lines += ['', 'All three variants match every camera frame pixel-for-pixel. Persistent-decoder hashes match across table/geometry/progressive/restart transitions and five output configurations. Each variant builds only two AC tables across the 120-frame camera sequence.', '']
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (output/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    (output/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines), flush=True)
    print('Saved:', output, flush=True)


if __name__ == '__main__':
    main()
