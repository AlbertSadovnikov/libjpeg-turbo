#!/usr/bin/env python3
"""Compare generic and Huffman-only BMI1/BMI2 builds on captured frames."""
import argparse
import collections
import csv
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
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
        parser.error('no frames found')
    output = here / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir()
    spec = importlib.util.spec_from_file_location('sequence_benchmark', webcam/'benchmark.py')
    stats = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stats)
    builds = {'release': Path('/tmp/mjpeg-release'), 'bmi2': Path('/tmp/mjpeg-bmi2')}
    # NASM records source paths in object metadata.  Start with the original
    # archives and replace only the separately compiled BMI Huffman object.
    # This makes the isolation check exact, including every other object's
    # metadata, without relying on machine-code normalization.
    libraries = {'release': builds['release'], 'bmi2': output}
    for library in ('libjpeg.a', 'libturbojpeg.a'):
        shutil.copyfile(builds['release']/library, output/library)
        target = 'jpeg-static' if library == 'libjpeg.a' else 'turbojpeg-static'
        huffman = builds['bmi2']/f'CMakeFiles/{target}.dir/src/jdhuff.c.o'
        subprocess.run(['ar','r',str(output/library),str(huffman)],check=True)
    commands, binaries, assembly = [], {}, {}
    for name, build in builds.items():
        src = repo/'src' if name == 'release' else Path('/tmp/mjpeg-bmi2-src/src')
        binaries[name] = {}
        for tool in ('benchmark', 'verify'):
            binary = output/(tool+'-'+name)
            command = ['cc', '-O3', '-Wall', '-Wextra', '-I'+str(build), '-I'+str(src),
                       str(webcam/(tool+'.c')), str(libraries[name]/'libturbojpeg.a'), '-lm', '-o', str(binary)]
            subprocess.run(command, check=True)
            commands.append(command)
            binaries[name][tool] = binary
        disassembly = subprocess.run(['objdump','-d','-M','intel',str(build/'CMakeFiles/turbojpeg-static.dir/src/jdhuff.c.o')],
                                     capture_output=True,text=True,check=True).stdout
        (output/f'jdhuff-{name}.asm').write_text(disassembly)
        assembly[name] = dict(collections.Counter(re.findall(r'\b(shrx|shlx|sarx|bzhi|bextr|pext|pdep|lzcnt|tzcnt)\b',disassembly)))
    # Confirm which archive objects changed, rather than assuming flags isolation.
    changed = {}
    for library in ('libjpeg.a','libturbojpeg.a'):
        members = [subprocess.run(['ar','t',str(build/library)],capture_output=True,text=True,check=True).stdout.splitlines()
                   for build in libraries.values()]
        assert members[0] == members[1]
        different = []
        for member in members[0]:
            contents = [subprocess.run(['ar','p',str(build/library),member],capture_output=True,check=True).stdout
                        for build in libraries.values()]
            if contents[0] != contents[1]:
                different.append(member)
        changed[library] = different
    print('Changed archive members:',changed,flush=True)
    assert all(v == ['jdhuff.c.o'] for v in changed.values()),changed
    for frame in frames:
        decoded = [subprocess.run([str(build/'djpeg-static'),str(frame)],capture_output=True,check=True)
                   for build in builds.values()]
        assert not any(p.stderr for p in decoded)
        assert decoded[0].stdout == decoded[1].stdout,frame
    mixed = frames + [Path('/tmp/mjpeg-bmi2/testout-static_422_ifast_opt.jpg'),
                      Path('/tmp/mjpeg-bmi2/testout-static_420_islow_prog.jpg'),
                      repo/'testimages/testorig.jpg',frames[0]]
    validation = {}
    for mode in ('bgr','gray','half','fast-upsample','fast-idct'):
        sequence = mixed if mode == 'bgr' else mixed[-4:]
        decoded = [subprocess.run([str(binaries[name]['verify']),mode,*map(str,sequence)],capture_output=True,check=True)
                   for name in builds]
        assert not any(p.stderr for p in decoded)
        assert decoded[0].stdout == decoded[1].stdout,mode
        validation[mode] = 'persistent decoder pixel hashes match'
    print('All 120 frames match pixel-for-pixel; persistent sequence checks passed.',flush=True)
    rows = {name: [] for name in builds}
    trial_means = {name: [] for name in builds}
    env = dict(os.environ)
    env.pop('JSIMD_FORCENONE',None)
    for trial in range(args.trials):
        for name in (list(builds) if trial%2==0 else list(reversed(builds))):
            command = ['taskset','-c',str(args.cpu),str(binaries[name]['benchmark']),
                       'bgr',str(args.passes),*map(str,frames)]
            result = subprocess.run(command,capture_output=True,text=True,check=True,env=env)
            assert not result.stderr,result.stderr
            (output/f'{name}-{trial}.csv').write_text(result.stdout)
            measured = [{k:float(v) for k,v in r.items()} for r in csv.DictReader(io.StringIO(result.stdout))]
            assert len(measured) == len(frames)*args.passes
            rows[name].extend(measured)
            mean = statistics.mean(r['total_ms'] for r in measured)
            trial_means[name].append(mean)
            commands.append(command)
            print(f'{name} trial {trial}: {mean:.4f} ms/frame',flush=True)
    summary = {'capture':str(args.capture.resolve()),'cpu':args.cpu,'frames':len(frames),
               'trials':args.trials,'passes':args.passes,'changed_archive_members':changed,
               'bit_instruction_counts':assembly,'validation':validation,'cases':{}}
    for name in builds:
        summary['cases'][name] = {'total_ms':stats.describe([r['total_ms'] for r in rows[name]]),
                                 'trial_means_ms':trial_means[name]}
    base = summary['cases']['release']['total_ms']['mean']
    bmi = summary['cases']['bmi2']['total_ms']['mean']
    summary['time_reduction_percent'] = 100*(1-bmi/base)
    summary['paired_trial_reduction_percent'] = [100*(1-a/b) for a,b in zip(trial_means['bmi2'],trial_means['release'])]
    lines = ['# Huffman-only BMI1/BMI2 experiment','','Only `jdhuff.c.o` differs in each library archive. All other object files match byte-for-byte.','',
             f'120 preloaded frames; {args.trials} trials x {args.passes} measured passes; CPU {args.cpu}; one full warmup pass per process; reused decoder and output; alternating build order.','',
             '| Build | Mean ms | Median ms | p95 ms | p99 ms |','|---|---:|---:|---:|---:|']
    for name in builds:
        t=summary['cases'][name]['total_ms']
        lines.append(f'| {name} | {t["mean"]:.4f} | {t["median"]:.4f} | {t["p95"]:.4f} | {t["p99"]:.4f} |')
    lines += ['',f'Mean time reduction: {summary["time_reduction_percent"]:.2f}%.','',
              'All camera frames match pixel-for-pixel. Persistent-decoder checks pass for five output configurations and mixed encodings.','']
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    (output/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines),flush=True)
    print('Saved:',output,flush=True)


if __name__ == '__main__':
    main()
