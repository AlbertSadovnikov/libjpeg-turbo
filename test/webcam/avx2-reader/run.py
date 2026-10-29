#!/usr/bin/env python3
"""Validate and time AVX2 scan windows against baseline and scalar bulk refill."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import io
import json
import os
import re
import statistics
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials',type=int,default=5)
    parser.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)))
    args=parser.parse_args()
    if args.trials<1: parser.error('positive trials required')
    assert 'avx2' in Path('/proc/cpuinfo').read_text(), 'AVX2 CPU required'
    here=Path(__file__).resolve().parent; repo=here.parents[2]
    output=here/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); output.mkdir()
    names=['scalar','avx2-codegen','avx2-32-local','avx2-32-persistent']
    builds={'baseline':Path('/tmp/mjpeg-google-bench'),
            'scalar':Path('/tmp/mjpeg-entropy-opt-build/bulk-once'),
            **{n:Path('/tmp/mjpeg-avx2-reader-build')/n for n in names[1:]}}
    sources={'baseline':repo,'scalar':Path('/tmp/mjpeg-entropy-opt-src/bulk-once'),
             **{n:Path('/tmp/mjpeg-avx2-reader-src')/n for n in names[1:]}}
    frames=sorted((repo/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
    assert len(frames)==120
    chunks=[1,31,32,33,2047,2048,2049,2079,2080,2081,3071,3072,3073,3103,3104,3105,4095,4096,4097,8192,65536]
    guard=(here.parent/'entropy-opt/guarded_source.c').read_text()
    guard,count=re.subn(r'const size_t chunks\[\] = \{[^}]+\};',
                        'const size_t chunks[] = {'+','.join(map(str,chunks))+'};',guard)
    assert count==1
    (output/'guarded_source.c').write_text(guard)
    commands=[]; helpers={}; instructions={}
    for name,build in builds.items():
        helpers[name]={}
        for tool,source in [('verify',here.parent/'verify.c'),('guarded_source',output/'guarded_source.c')]:
            binary=output/(tool+'-'+name)
            command=['cc','-O3','-Wall','-Wextra','-I'+str(build),'-I'+str(sources[name]/'src'),
                     str(source),str(build/'libjpeg.a'),'-lm','-o',str(binary)]
            subprocess.run(command,check=True); commands.append(command); helpers[name][tool]=binary
        disassembly=subprocess.run(['objdump','-d','-M','intel',str(build/'CMakeFiles/jpeg-static.dir/src/jdhuff.c.o')],capture_output=True,text=True,check=True).stdout
        (output/(name+'.asm')).write_text(disassembly)
        instructions[name]={ins:len(re.findall(r'\b'+ins+r'\b',disassembly)) for ins in ['vpcmpeqb','vpmovmskb','vzeroupper']}
        if name.startswith('avx2-32'):
            assert instructions[name]['vpcmpeqb'] and instructions[name]['vpmovmskb'],instructions[name]
    for frame in frames:
        reference=subprocess.run([str(builds['baseline']/'djpeg-static'),str(frame)],capture_output=True,check=True)
        assert not reference.stderr
        for name in names:
            candidate=subprocess.run([str(builds[name]/'djpeg-static'),str(frame)],capture_output=True,check=True)
            assert candidate.stdout==reference.stdout and not candidate.stderr,(name,frame)
    print('All 120 frames match pixel-for-pixel across all candidates.',flush=True)
    fixtures=builds['avx2-32-local']
    mixed=[frames[0],fixtures/'testout-static_422_ifast_opt.jpg',fixtures/'testout-static_420_islow_prog.jpg',repo/'testimages/testorig.jpg',frames[-1]]
    for mode in ['bgr','gray','half','fast-upsample','fast-idct']:
        sequence=frames+mixed if mode=='bgr' else mixed
        reference=subprocess.run([str(helpers['baseline']['verify']),mode,*map(str,sequence)],capture_output=True,check=True)
        assert not reference.stderr
        for name in names:
            candidate=subprocess.run([str(helpers[name]['verify']),mode,*map(str,sequence)],capture_output=True,check=True)
            assert candidate.stdout==reference.stdout and not candidate.stderr,(name,mode)
    guarded_frames=[frames[0],frames[60],frames[-1],fixtures/'testout-static_422_ifast_opt.jpg',
                    fixtures/'testout-static_420_islow.jpg',fixtures/'testout-static_420_islow_prog.jpg',repo/'testimages/testorig.jpg']
    if Path('/tmp/mjpeg-restart.jpg').exists(): guarded_frames.append(Path('/tmp/mjpeg-restart.jpg'))
    plain=subprocess.run([str(helpers['baseline']['verify']),'bgr',*map(str,guarded_frames)],capture_output=True,check=True)
    expected=list(csv.reader(io.StringIO(plain.stdout.decode())))
    reference=subprocess.run([str(helpers['baseline']['guarded_source']),*map(str,guarded_frames)],capture_output=True,check=True)
    assert not reference.stderr
    for row in csv.reader(io.StringIO(reference.stdout.decode())):
        assert row[-2:]==expected[int(row[0])][-2:],row
    for name in names:
        candidate=subprocess.run([str(helpers[name]['guarded_source']),*map(str,guarded_frames)],capture_output=True,check=True)
        assert candidate.stdout==reference.stdout and not candidate.stderr,(name,'guarded source')
        (output/('guarded-'+name+'.csv')).write_bytes(candidate.stdout)
    validation={'camera_frames':120,'persistent_modes':5,'guarded_frames':list(map(str,guarded_frames)),
                'guarded_chunk_sizes':chunks,'instructions':instructions}
    (output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print('Persistent state, 4:2:0/4:2:2, and protected-page checks passed.',flush=True)
    pattern='^MJPEG/(Libjpeg/BGR_Reused|TurboJPEG/BGR_Reused|Stages/EntropyWithStoresAndZeroing|Stages/EntropyDiscardCoefficients)$'
    records={name:[] for name in builds}
    for trial in range(args.trials):
        order=names[trial%len(names):]+names[:trial%len(names)]
        if trial%2: order.reverse()
        for index,name in enumerate(['baseline',*order,'baseline']):
            result=output/f'{trial}-{index}-{name}.json'
            command=['taskset','-c',str(args.cpu),str(builds[name]/'benchmarks/mjpeg-bench'),
                     '--benchmark_filter='+pattern,'--benchmark_min_time=0.2s',
                     '--benchmark_min_warmup_time=0.05','--benchmark_repetitions=1',
                     '--benchmark_out='+str(result),'--benchmark_out_format=json']
            p=subprocess.run(command,capture_output=True,text=True,check=True)
            (output/f'{trial}-{index}-{name}.log').write_text(p.stdout+p.stderr)
            rows=json.loads(result.read_text())['benchmarks']
            assert len(rows)==4 and not any(r.get('error_occurred') for r in rows)
            assert all(r['time_unit']=='ms' for r in rows)
            times={r['name']:r['cpu_time'] for r in rows}; commands.append(command)
            records[name].append({'trial':trial,'cpu_ms':times})
            print(f"trial {trial} {name}: BGR {times['MJPEG/Libjpeg/BGR_Reused']:.4f} ms; entropy {times['MJPEG/Stages/EntropyWithStoresAndZeroing']:.4f} ms",flush=True)
    summary={'cpu':args.cpu,'trials':args.trials,'validation':validation,'records':records,'cases':{}}
    metrics=list(records['baseline'][0]['cpu_ms'])
    for name,runs in records.items():
        summary['cases'][name]={m:{'median':statistics.median(r['cpu_ms'][m] for r in runs),
                                  'mean':statistics.mean(r['cpu_ms'][m] for r in runs)} for m in metrics}
        if name!='baseline':
            for m in metrics:
                summary['cases'][name][m]['paired_trial_reduction_percent']=[
                    100*(1-r['cpu_ms'][m]/statistics.mean(b['cpu_ms'][m] for b in records['baseline'] if b['trial']==r['trial'])) for r in runs]
    bgr='MJPEG/Libjpeg/BGR_Reused'; ent='MJPEG/Stages/EntropyWithStoresAndZeroing'
    base=summary['cases']['baseline']
    lines=['# AVX2 32-byte scan-window comparison','',
           'Median of per-run mean CPU times; one embedded frame, CPU pinned, five bracketed rounds; no low-level profiling.','',
           '| Variant | BGR ms | BGR reduction | Entropy/store ms | Entropy reduction |',
           '|---|---:|---:|---:|---:|']
    for name,c in summary['cases'].items():
        lines.append(f"| {name} | {c[bgr]['median']:.4f} | {100*(1-c[bgr]['median']/base[bgr]['median']):.2f}% | {c[ent]['median']:.4f} | {100*(1-c[ent]['median']/base[ent]['median']):.2f}% |")
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True); print('Saved:',output,flush=True)


if __name__=='__main__': main()
