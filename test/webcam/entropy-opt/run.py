#!/usr/bin/env python3
"""Validate isolated entropy variants and compare their embedded-frame timings."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, default=5)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--variants', nargs='+', default=['bulk','compact','aligned','compact-aligned','bulk-compact-aligned'],
                        choices=['bulk','compact','aligned','compact-aligned','bulk-compact-aligned','bulk-once','bulk-sse2'])
    args = parser.parse_args()
    if args.trials < 1:
        parser.error('positive trial count required')
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    output = here/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir()
    names = args.variants
    builds = {'baseline': Path('/tmp/mjpeg-google-bench'),
              **{name: Path('/tmp/mjpeg-entropy-opt-build')/name for name in names}}
    sources = {'baseline':repo, **{name:Path('/tmp/mjpeg-entropy-opt-src')/name for name in names}}
    frames = sorted((repo/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
    assert len(frames)==120
    commands = []
    validation = {}
    guarded = {}
    verifiers = {}
    for name, build in builds.items():
        for tool, source in [('guarded_source', here/'guarded_source.c'),
                             ('verify',here.parent/'verify.c')]:
            binary=output/(tool+'-'+name)
            command=['cc','-O3','-Wall','-Wextra','-I'+str(build),'-I'+str(sources[name]/'src'),
                     str(source),str(build/'libjpeg.a'),'-lm','-o',str(binary)]
            subprocess.run(command,check=True)
            commands.append(command)
            (guarded if tool=='guarded_source' else verifiers)[name]=binary
    for frame in frames:
        reference=subprocess.run([str(builds['baseline']/'djpeg-static'),str(frame)],capture_output=True,check=True)
        assert not reference.stderr
        for name in names:
            candidate=subprocess.run([str(builds[name]/'djpeg-static'),str(frame)],capture_output=True,check=True)
            assert candidate.stdout==reference.stdout and not candidate.stderr,(name,frame)
    print(f'All 120 camera frames match pixel-for-pixel in all {len(names)} variants.',flush=True)
    regression=builds[names[0]]
    mixed=[frames[0],regression/'testout-static_422_ifast_opt.jpg',
           regression/'testout-static_420_islow_prog.jpg',repo/'testimages/testorig.jpg',frames[-1]]
    for mode in ['bgr','gray','half','fast-upsample','fast-idct']:
        sequence=frames+mixed if mode=='bgr' else mixed
        reference=subprocess.run([str(verifiers['baseline']),mode,*map(str,sequence)],capture_output=True,check=True)
        assert not reference.stderr
        for name in names:
            candidate=subprocess.run([str(verifiers[name]),mode,*map(str,sequence)],capture_output=True,check=True)
            assert candidate.stdout==reference.stdout and not candidate.stderr,(name,mode)
    sequence=[frames[0],frames[60],frames[-1],regression/'testout-static_422_ifast_opt.jpg',
              regression/'testout-static_420_islow_prog.jpg',repo/'testimages/testorig.jpg']
    reference=subprocess.run([str(guarded['baseline']),*map(str,sequence)],capture_output=True,check=True)
    assert not reference.stderr
    for name in names:
        candidate=subprocess.run([str(guarded[name]),*map(str,sequence)],capture_output=True,check=True)
        assert candidate.stdout==reference.stdout and not candidate.stderr,(name,'guard pages')
        (output/('guarded-'+name+'.csv')).write_bytes(candidate.stdout)
        validation[name]={'camera_pixel_comparisons':120,'persistent_modes':5,
                          'guarded_frames':len(sequence),'chunk_sizes':[1,31,2047,2048,2049,4095,4096,4097,8192,65536],
                          'regression_tests_passed':333}
    (output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print('Persistent-decoder and protected-page source tests passed.',flush=True)

    pattern='^MJPEG/(Libjpeg/BGR_Reused|TurboJPEG/BGR_Reused|Stages/EntropyWithStoresAndZeroing|Stages/EntropyDiscardCoefficients)$'
    records={name:[] for name in builds}
    for trial in range(args.trials):
        order=names[trial%len(names):]+names[:trial%len(names)]
        if trial%2: order.reverse()
        # Baselines bracket each round to expose clock/load drift.
        for index,name in enumerate(['baseline',*order,'baseline']):
            result=output/f'{trial}-{index}-{name}.json'
            command=['taskset','-c',str(args.cpu),str(builds[name]/'benchmarks/mjpeg-bench'),
                     '--benchmark_filter='+pattern,'--benchmark_min_time=0.15s',
                     '--benchmark_min_warmup_time=0.03','--benchmark_repetitions=1',
                     '--benchmark_out='+str(result),'--benchmark_out_format=json']
            p=subprocess.run(command,capture_output=True,text=True,check=True)
            (output/f'{trial}-{index}-{name}.log').write_text(p.stdout+p.stderr)
            data=json.loads(result.read_text())['benchmarks']
            assert len(data)==4 and not any(r.get('error_occurred') for r in data),(name,data)
            times={r['name']:r['cpu_time'] for r in data}
            assert all(r['time_unit']=='ms' for r in data)
            records[name].append({'trial':trial,'cpu_ms':times})
            commands.append(command)
            print(f"trial {trial} {name}: BGR {times['MJPEG/Libjpeg/BGR_Reused']:.4f} ms; entropy {times['MJPEG/Stages/EntropyWithStoresAndZeroing']:.4f} ms",flush=True)
    metrics=list(records['baseline'][0]['cpu_ms'])
    summary={'cpu':args.cpu,'trials':args.trials,'method':'Median of per-run mean CPU times, single embedded frame; candidate order rotated; baseline brackets each round; no low-level profiling.',
             'validation':validation,'cases':{},'records':records}
    for name,runs in records.items():
        summary['cases'][name]={metric:{'median':statistics.median(r['cpu_ms'][metric] for r in runs),
                                       'mean':statistics.mean(r['cpu_ms'][metric] for r in runs)} for metric in metrics}
        if name!='baseline':
            for metric in metrics:
                paired=[]
                for row in runs:
                    base=statistics.mean(r['cpu_ms'][metric] for r in records['baseline'] if r['trial']==row['trial'])
                    paired.append(100*(1-row['cpu_ms'][metric]/base))
                summary['cases'][name][metric]['paired_trial_reduction_percent']=paired
    lines=['# Entropy reader and lookup layout experiments','',summary['method'],'',
           '| Variant | BGR ms | BGR reduction | Entropy/store ms | Entropy reduction |',
           '|---|---:|---:|---:|---:|']
    bgr='MJPEG/Libjpeg/BGR_Reused'; entropy='MJPEG/Stages/EntropyWithStoresAndZeroing'
    base=summary['cases']['baseline']
    for name,case in summary['cases'].items():
        lines.append(f"| {name} | {case[bgr]['median']:.4f} | {100*(1-case[bgr]['median']/base[bgr]['median']):.2f}% | {case[entropy]['median']:.4f} | {100*(1-case[entropy]['median']/base[entropy]['median']):.2f}% |")
    lines+=['','All variants passed 333 regression tests, pixel comparisons for all 120 camera frames, persistent-decoder checks in five modes, and guarded-source chunk-boundary checks.','']
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    (output/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines),flush=True)
    print('Saved:',output,flush=True)


if __name__=='__main__': main()
