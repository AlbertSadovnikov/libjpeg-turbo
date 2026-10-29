#!/usr/bin/env python3
"""Run the sequence benchmark against the experimental builds in /tmp."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess


def describe(values):
    values = sorted(values)
    def percentile(p):
        x = (len(values) - 1) * p
        lo = int(x)
        return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (x - lo)
    return dict(mean=statistics.mean(values), median=statistics.median(values),
                p95=percentile(.95), p99=percentile(.99), min=values[0], max=values[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--passes', type=int, default=3)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    if args.passes < 1 or args.trials < 1:
        parser.error('passes and trials must be positive')
    frames = sorted(args.capture.resolve().glob('frame_*.jpg'))
    if not frames:
        parser.error('no frames found')
    output = args.capture / ('timings-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    output.mkdir()
    source = Path(__file__).with_suffix('.c').resolve()
    repo = source.parents[2]
    builds = {'release': (Path('/tmp/mjpeg-release'), repo/'src'),
              'profile': (Path('/tmp/mjpeg-profile'), repo/'src'),
              'lookahead10': (Path('/tmp/mjpeg-lookahead10'), Path('/tmp/mjpeg-entropy-src/src'))}
    binaries = {}
    commands = []
    for name, (build, src) in builds.items():
        binary = (output / ('benchmark-' + name)).resolve()
        command = ['cc', '-O3', '-Wall', '-Wextra', '-I'+str(build), '-I'+str(src),
                   str(source), str(build/'libturbojpeg.a'), '-lm', '-o', str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[name] = binary

    cases = {'bgr': ('release', 'bgr'), 'lookahead10': ('lookahead10', 'bgr'),
             'fast-upsample': ('release', 'fast-upsample'),
             'fast-idct': ('release', 'fast-idct'), 'half': ('release', 'half'),
             'gray': ('release', 'gray'), 'no-simd': ('release', 'bgr'),
             'profile': ('profile', 'bgr')}
    all_rows = {name: [] for name in cases}
    for trial in range(args.trials):
        order = list(cases)
        if trial % 2:
            order.reverse()
        for name in order:
            build, mode = cases[name]
            command = ['taskset', '-c', str(args.cpu), str(binaries[build]),
                       mode, str(args.passes), *map(str, frames)]
            env = dict(os.environ)
            env.pop('JSIMD_FORCENONE', None)
            if name == 'no-simd':
                env['JSIMD_FORCENONE'] = '1'
            run = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
            (output/f'{name}-{trial}.csv').write_text(run.stdout)
            (output/f'{name}-{trial}.stderr').write_text(run.stderr)
            rows = [{k: float(v) for k,v in row.items()} for row in csv.DictReader(io.StringIO(run.stdout))]
            assert len(rows) == args.passes * len(frames)
            all_rows[name].extend(rows)
            print(f'{name} trial {trial}: {statistics.mean(r["total_ms"] for r in rows):.3f} ms/frame', flush=True)
            commands.append(command)

    # Compare actual output bytes for every camera frame, outside timed regions.
    for frame in frames:
        decoded = [subprocess.run([f'/tmp/{build}/djpeg-static', str(frame)],
                                  capture_output=True, check=True)
                   for build in ('mjpeg-release', 'mjpeg-lookahead10')]
        assert not any(p.stderr for p in decoded), frame
        assert decoded[0].stdout == decoded[1].stdout, frame

    summary = {'capture': str(args.capture.resolve()), 'cpu': args.cpu,
               'machine': platform.platform(), 'frames': len(frames),
               'passes_per_trial': args.passes, 'trials': args.trials,
               'method': 'Preload complete sequence, reuse decoder and output, one full warmup pass per process; CLOCK_MONOTONIC per-frame timing; single pinned CPU; no disk/capture time. Stage timers use the separate WITH_PROFILE build.',
               'lookahead10_pixel_validation': f'All {len(frames)} frames matched exactly without decoder warnings.',
               'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'cases': {}}
    for name, rows in all_rows.items():
        stats = {key: describe([r[key] for r in rows]) for key in rows[0] if key.endswith('_ms')}
        stats['fps_from_mean'] = 1000/stats['total_ms']['mean']
        stats['trial_mean_ms'] = [statistics.mean(r['total_ms'] for r in rows[i:i+args.passes*len(frames)])
                                 for i in range(0,len(rows),args.passes*len(frames))]
        stats['per_frame_mean_ms'] = [statistics.mean(r['total_ms'] for r in rows if r['frame']==i)
                                      for i in range(len(frames))]
        summary['cases'][name] = stats
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (output/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    lines = ['# Webcam sequence decode timings', '', summary['method'], '',
             f'{len(frames)} frames, {args.trials} trials x {args.passes} measured passes; CPU {args.cpu}.', '',
             '| Configuration | Mean ms | Median ms | p95 ms | p99 ms | FPS |',
             '|---|---:|---:|---:|---:|---:|']
    for name, stats in summary['cases'].items():
        t=stats['total_ms']
        lines.append(f'| {name} | {t["mean"]:.3f} | {t["median"]:.3f} | {t["p95"]:.3f} | {t["p99"]:.3f} | {stats["fps_from_mean"]:.1f} |')
    lines += ['', 'Profile timings include instrumentation overhead and must not be treated as a decomposition of uninstrumented latency.', '',
              '| Instrumented stage | Mean ms |', '|---|---:|']
    for key in ('header_ms','setup_ms','entropy_ms','idct_ms','upsample_ms','color_ms','finish_ms'):
        lines.append(f'| {key} | {summary["cases"]["profile"][key]["mean"]:.4f} |')
    lines += ['', summary['lookahead10_pixel_validation'], '']
    (output/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines), flush=True)
    print('Saved:', output.resolve(), flush=True)


if __name__ == '__main__':
    main()
